import logging
from datetime import datetime
from typing import Dict, List, Optional

import discord
from aws.dynamodb import DynamoDbManager
from aws.s3 import S3ClientManager
from cogs.constants import COLOR_EMBED, JOIN_MATCH_2V2_TIMEOUT_SEC, ROLE_ADMIN, ROLE_MOD
from discord.ext import commands, tasks
from helpers import get_guild, get_ping_channel
from matchmaking.match_queues.matchmaking_manager import MatchmakingManager
from matchmaking.matches.active_match import ActiveMatch
from matchmaking.matches.completed_match import CompletedMatch
from matchmaking.matches.team_2v2 import Team2v2, Teams2v2
from models.player_profile import PlayerProfile


class MonitorMatchmakingManager(commands.Cog):
    """
    Cog monitoring the matchmaking queue and determining when to ping players.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.matchmaking_manager = MatchmakingManager()
        self.ddb_manager = DynamoDbManager()
        self.s3_manager = S3ClientManager()

        # Maps bot_match_id -> channel for active matches
        self.active_match_channels: Dict[int, discord.TextChannel] = {}

    def cog_load(self):
        logging.info("Matchmaking Manager Monitor loading...")
        self.check_for_new_matches.start()
        self.check_for_completed_matches.start()
        self.check_for_new_first_players_joined_queue.start()

    def cog_unload(self):
        """Stop the task when the cog is unloaded."""
        logging.info("Matchmaking Manager Monitor unloading...")
        self.check_for_new_matches.cancel()
        self.check_for_completed_matches.cancel()
        self.check_for_new_first_players_joined_queue.cancel()

    async def create_active_match_channel(
        self, active_match: ActiveMatch
    ) -> Optional[discord.TextChannel]:
        """Creates an active match channel and adds all match players.

        Args:
            active_match (ActiveMatch): The match to create a channel for.

        Returns:
            discord.TextChannel: The discord channel for the match.
        """

        async def maybe_return_bot_ping_channel_id() -> Optional[discord.TextChannel]:
            ping_channel = await get_ping_channel(self.bot, self.s3_manager)
            if not ping_channel:
                logging.warning(
                    f"No bot ping channel either. Players won't get any indication of their match starting."
                )
                return None
            return ping_channel

        category_id = active_match.match_queue.category_id
        if category_id is None:
            logging.warning(
                f"No category ID found for match {active_match}, using generic bot pings channel."
            )
            return await maybe_return_bot_ping_channel_id()

        # Get the category to create channel in
        guild = get_guild(self.bot)
        category: Optional[discord.CategoryChannel] = discord.utils.get(
            guild.categories, id=category_id
        )
        if not category:
            logging.warning(
                f"No category found in channel with id {category_id}, using generic bot pings channel."
            )
            return await maybe_return_bot_ping_channel_id()

        # Overwrite permissions so only players in the match (and mods+) can see it
        overwrites = {}
        overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
        for player in active_match.participants():
            member = guild.get_member(player.discord_account_id)
            if member:
                overwrites[member] = discord.PermissionOverwrite(view_channel=True)
        overwrites[discord.utils.get(guild.roles, name=ROLE_MOD)] = (
            discord.PermissionOverwrite(view_channel=True)
        )
        overwrites[discord.utils.get(guild.roles, name=ROLE_ADMIN)] = (
            discord.PermissionOverwrite(view_channel=True)
        )
        overwrites[guild.me] = discord.PermissionOverwrite(
            view_channel=True,  # Needed to get responses
            send_messages=True,  # Obviously
            manage_channels=True,  # Needed to delete channel
            manage_messages=True,
            embed_links=True,  # Needed to send embeds
            use_application_commands=True,  # Needed for buttons
            read_messages=True,
            read_message_history=True,
        )

        channel = await guild.create_text_channel(
            name=f"BMM - #{active_match.bot_match_id}",
            category=category,
            overwrites=overwrites,
        )

        # Add to active channels to be tracked until completion
        self.active_match_channels[active_match.bot_match_id] = channel

        logging.info(f"Created channel for match {active_match.bot_match_id}.")
        return channel

    async def delete_active_match_channel(
        self, completed_match: CompletedMatch
    ) -> None:
        """Deletes an active match channel after the match has finished.

        Args:
            completed_match (CompletedMatch): The match to delete the channel for.
        """
        channel = self.active_match_channels.pop(
            completed_match.active_match.bot_match_id, None
        )
        if channel:
            await channel.delete()
            logging.info(
                f"Deleted channel for match {completed_match.active_match.bot_match_id}."
            )
        else:
            logging.error(
                f"Channel for match {completed_match.active_match.bot_match_id} not found. Not deleting."
            )

    async def send_players_match_start_notification(
        self,
        players: List[PlayerProfile],
        bot_match_id: int,
        channel: discord.TextChannel,
    ) -> None:
        try:
            embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())
            embed.add_field(
                name="❗ Match Found",
                value=f'Pinged players, join the Better Matchmaking club and click activity "BMM - #{bot_match_id}"!',
            )

            content = ""
            for player in players:
                content += f"<@{player.discord_account_id}> "

            await channel.send(content=content, embed=embed)  # type: ignore
        except Exception as e:
            logging.error(f"Error sending message for match start to players: {e}")

    async def send_2v2_players_match_start_notification(
        self,
        teams: Teams2v2,
        bot_match_id: int,
        match_channel: discord.TextChannel,
    ) -> None:
        # This is a unique work-around of a Nadeo bug where we ping players Blue-Red-Blue-Red to ensure they join in the right order.

        try:
            player_join_order = [
                teams.team_a.player_a,
                teams.team_b.player_a,
                teams.team_a.player_b,
                teams.team_b.player_b,
            ]

            for player in player_join_order:
                # Add match joined ack button
                button = discord.ui.Button(
                    label="I joined the Server", style=discord.ButtonStyle.green
                )
                view = discord.ui.View(timeout=JOIN_MATCH_2V2_TIMEOUT_SEC)
                view.add_item(button)

                # Corouting to await button interaction
                def check(interaction: discord.Interaction):
                    return (
                        interaction.user.id == player.discord_account_id
                        and interaction.channel.id == match_channel.id  # type: ignore
                    )

                message = await match_channel.send(
                    content=f"<@{player.discord_account_id}> Your 2v2 match is ready. Please join BMM - #{bot_match_id} in-game **then click the button** once you're in.",
                    view=view,
                )

                try:
                    # Wait for player ack
                    interaction = await self.bot.wait_for(
                        "interaction", check=check, timeout=JOIN_MATCH_2V2_TIMEOUT_SEC
                    )
                    await interaction.response.send_message(
                        f"<@{player.discord_account_id}> joined match, pinging next player.",
                        ephemeral=True,
                    )
                except:
                    logging.warning(
                        f"Player {player.discord_account_id} did not join in time."
                    )
                    await match_channel.send(
                        content=f"<@{player.discord_account_id}> did not join in time for BMM - #{bot_match_id}, please ping for a Mod.",
                    )
                    return

            # Match is ready to go
            embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())
            embed.add_field(
                name="❗ Match Ready",
                value=f"All players have joined BMM - #{bot_match_id}, starting match.",
            )

            await match_channel.send(embed=embed)

        except Exception as e:
            logging.error(f"Error sending message for match start to players: {e}")

    async def send_players_match_complete_notification(
        self,
        bot_match_id: int,
        player_profile_to_leaderboard_elo_update_and_diff_map: Dict[
            PlayerProfile, Dict[str, tuple[int, int]]
        ],
    ) -> None:
        """Sends players from a match the complete notification with their updated elo and difference for each leaderboard the match queue is in.

        Args:
            bot_match_id (int): The bot match ID completed.
            player_profile_to_leaderboard_elo_update_and_diff_map (Dict[PlayerProfile, Dict[str, tuple[int, int]]]): A dictionary mapping players to a map of leaderboard ID to a tuple of player elo and elo difference.
        """
        try:
            ping_channel = await get_ping_channel(self.bot, self.s3_manager)

            if not ping_channel:
                logging.warning("No ping channel found.")
                return

            players = list(player_profile_to_leaderboard_elo_update_and_diff_map.keys())
            content = ""
            for player in players:
                content += f"<@{player.discord_account_id}> "

            value = "Updated elos have been calculated:\n"
            value += f"-----------------------------------------\n"
            for (
                player,
                leaderboard_to_elos,
            ) in player_profile_to_leaderboard_elo_update_and_diff_map.items():
                value += f"<@{player.discord_account_id}>\n"
                for leaderboard, (updated_elo, elo_diff) in leaderboard_to_elos.items():
                    elo_diff_prefix = "+" if elo_diff >= 0 else ""
                    value += (
                        f"{leaderboard}: {updated_elo} ({elo_diff_prefix}{elo_diff})\n"
                    )
                value += f"-----------------------------------------\n"

            embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())
            embed.add_field(name=f"❗ Match Finished - #{bot_match_id}", value=value)

            await ping_channel.send(content=content, embed=embed)
        except Exception as e:
            logging.error(f"Error sending message to {player.discord_account_id}: {e}")

    @tasks.loop(seconds=3)  # Run every 3 seconds
    async def check_for_new_matches(self):
        """Periodically checks if new matches have been created."""
        logging.debug(f"Bot checking for new matches...")
        new_matches = self.matchmaking_manager.process_new_active_matches_monitor()

        for match in new_matches:
            logging.info(f"New match {match.match_id}, notifying players.")
            bot_match_id = match.bot_match_id

            match_channel = await self.create_active_match_channel(match)
            if not match_channel:
                logging.error(f"Failed to create channel for match {match.match_id}.")
                continue

            # Notify the players in the match
            if isinstance(match.player_profiles, List):
                self.bot.loop.create_task(
                    self.send_players_match_start_notification(
                        match.player_profiles, bot_match_id, match_channel
                    )
                )
            else:
                self.bot.loop.create_task(
                    self.send_2v2_players_match_start_notification(
                        match.player_profiles, bot_match_id, match_channel
                    )
                )

    @tasks.loop(seconds=3)
    async def check_for_new_first_players_joined_queue(self):
        """Periodically checks for new players to took intiative to join an empty queue."""
        logging.debug(f"Bot checking for players joining an empty queue...")
        players_in_queues = self.matchmaking_manager.process_first_player_joined_queue()
        if len(players_in_queues) == 0:
            return

        for player, queue in players_in_queues:
            ping_role_id = queue.queue.ping_role_id

            if not ping_role_id:
                logging.debug(
                    f"First player joined queue {queue.queue.queue_id} but no role to ping found."
                )
                continue

            # NOTE we are operating under the assumption this bot is only connected to one server
            guild = get_guild(self.bot)
            ping_role = guild.get_role(ping_role_id)

            if not ping_role:
                logging.warning(f"Role {ping_role_id} not found in the guild {guild}.")
                continue

            ping_channel = self.bot.get_channel(queue.queue.channel_id)
            if ping_channel is None:
                logging.error(
                    f"Ping channel not found with ID {queue.queue.channel_id}."
                )
                continue

            if not isinstance(ping_channel, discord.TextChannel):
                logging.error(
                    f"Channel {queue.queue.channel_id} is not a text channel."
                )
                continue

            embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())
            embed.add_field(
                name="❗ Queue Activated",
                value=f"{queue.queue.queue_id} queue started by <@{player.discord_account_id}>.",
                inline=True,
            )
            msg = await ping_channel.send(content=f"{ping_role.mention}", embed=embed)

            # Delete the message after 60 seconds
            await msg.delete(delay=60)

    async def upload_match_results_and_cleanup_event(
        self, match: CompletedMatch
    ) -> None:
        logging.debug(
            f"Uploading match results for match {match.active_match.match_id} and deleting event {match.active_match.event_id}..."
        )

        self.ddb_manager.put_match_results(
            match.active_match.bot_match_id,
            match.active_match.match_queue.queue_id,
            match.active_match.match_id,
            match.active_match.match_live_id,
            match.time_completed,
            match.match_results.__str__(),
        )

        for player in match.active_match.player_profiles:
            if isinstance(player, Team2v2):
                logging.debug("Not implemented to count matches complete for teams...")
                continue

            self.ddb_manager.update_player_matches_complete(player.tm_account_id)

        match.cleanup()

    async def calculate_elos_and_upload(
        self, match: CompletedMatch
    ) -> Dict[PlayerProfile, Dict[str, tuple[int, int]]]:
        if isinstance(match.active_match.player_profiles, List):
            match_players = match.active_match.player_profiles
        else:
            match_players = match.active_match.player_profiles.players()

        # Create a mapping from player profile -> dict of leaderboard id -> (updated elo, elo diff)
        player_profile_to_leaderboard_elo_update_and_diff_map: Dict[
            PlayerProfile, Dict[str, tuple[int, int]]
        ] = {}

        for player_profile in match_players:
            leaderboards_to_elo_update_and_diff_map: Dict[str, tuple[int, int]] = {}
            for leaderboard_id in match.active_match.match_queue.leaderboard_ids:  # type: ignore
                # Find the updated elo rating for this player on this leaderboard
                updated_elo = None
                for updated_elo_rating in match.updated_elo_ratings:
                    if (
                        updated_elo_rating.tm_account_id == player_profile.tm_account_id
                        and updated_elo_rating.leaderboard_id == leaderboard_id
                    ):
                        updated_elo = updated_elo_rating.elo
                elo_diff = None
                for elo_diff_rating in match.elo_differences:
                    if (
                        elo_diff_rating.tm_account_id == player_profile.tm_account_id
                        and elo_diff_rating.leaderboard_id == leaderboard_id
                    ):
                        elo_diff = elo_diff_rating.elo

                if updated_elo is None or elo_diff is None:
                    logging.error(
                        f"Could not find updated elo or elo diff for player {player_profile.tm_account_id} on leaderboard {leaderboard_id}"
                    )
                    continue
                leaderboards_to_elo_update_and_diff_map[leaderboard_id] = (
                    updated_elo,
                    elo_diff,
                )

            # Add all the leaderboards' updated elos and differences to the map
            player_profile_to_leaderboard_elo_update_and_diff_map[player_profile] = (
                leaderboards_to_elo_update_and_diff_map
            )

        # Now add the updated elos back to the elo table for each leaderboard
        for (
            player_profile,
            updated_elos_by_leaderboard_id,
        ) in player_profile_to_leaderboard_elo_update_and_diff_map.items():
            for leaderboard_id, (
                updated_elo,
                elo_diff,
            ) in updated_elos_by_leaderboard_id.items():
                self.ddb_manager.update_player_elo(
                    player_profile.tm_account_id, leaderboard_id, updated_elo
                )

        return player_profile_to_leaderboard_elo_update_and_diff_map

    async def update_player_rank_role(
        self,
        player_profile: PlayerProfile,
        updated_elos_by_leaderboard_id: Dict[str, tuple[int, int]],
        global_leaderboard: str,
    ) -> None:
        """Updates a player's rank role in discord if they have surpassed a new minimum elo or dropped below a previous minimum elo.

        Args:
            player_profile (PlayerProfile): Player to update the rank role for.
            updated_elos_by_leaderboard_id (Dict[str, tuple[int, int]]): A mapping of leaderboard IDs to a player's updated elo and elo diff from the latest match.
        """
        try:
            # NOTE we are operating under the assumption this bot is only connected to one server
            guild = get_guild(self.bot)
            member = guild.get_member(player_profile.discord_account_id)

            if not member:
                logging.error(
                    f"Could not find member with ID {player_profile.discord_account_id} in any of the guilds the bot is connected to."
                )
                return

            member_roles = member.roles
        except Exception as e:
            logging.error(f"Error getting member roles: {e}")
            return

        player_elo_update = updated_elos_by_leaderboard_id.get(global_leaderboard)  # type: ignore
        if player_elo_update is None:
            logging.error(
                f"Could not find player elo for global leaderboard {global_leaderboard}"
            )
            return

        player_elo = player_elo_update[0]
        rank_roles = self.ddb_manager.get_rank_roles()

        # Find the rank role the user should have now
        new_rank_role = None
        distance_above_min_elo = 0
        for role in rank_roles:
            if player_elo - role.min_elo > distance_above_min_elo:
                distance_above_min_elo = player_elo - role.min_elo
                new_rank_role = role

        # Remove user's discord roles which correspond to a rank role
        rank_role_ids = [role.rank_role_id for role in rank_roles]
        for role in member_roles:
            if role.id in rank_role_ids:  # type: ignore
                await member.remove_roles(role)

        # Add the new role to the user
        await member.add_roles(guild.get_role(new_rank_role.rank_role_id))  # type: ignore
        logging.info(f"Updated rank role for user {player_profile.discord_account_id} to {new_rank_role.display_name}")  # type: ignore

    @tasks.loop(seconds=3)  # Run every 10 seconds
    async def check_for_completed_matches(self):
        """Periodically checks if matches have been completed."""
        logging.debug(f"Bot checking for completed matches...")
        completed_matches = self.matchmaking_manager.process_completed_matches_monitor()

        for match in completed_matches:
            logging.info(
                f"Match {match.active_match.match_id} is completed, processing..."
            )
            await self.upload_match_results_and_cleanup_event(match)
            player_profile_to_leaderboard_elo_update_and_diff_map = (
                await self.calculate_elos_and_upload(match)
            )

            configs = self.s3_manager.get_configs()
            global_leaderboard = configs.global_leaderboard_id

            if global_leaderboard is None:
                logging.info(
                    "No global leaderboard found, not updating player rank role."
                )

            await self.send_players_match_complete_notification(
                match.active_match.bot_match_id,
                player_profile_to_leaderboard_elo_update_and_diff_map,
            )

            # Delete the active match channel
            await self.delete_active_match_channel(match)

            for (
                player_profile,
                updated_elos_by_leaderboard_id,
            ) in player_profile_to_leaderboard_elo_update_and_diff_map.items():
                if global_leaderboard is not None:
                    await self.update_player_rank_role(
                        player_profile,
                        updated_elos_by_leaderboard_id,
                        global_leaderboard,
                    )

    @check_for_new_matches.before_loop
    async def before_check_for_new_matches(self):
        """Wait until the bot is ready before starting the loop."""
        await self.bot.wait_until_ready()

    @check_for_completed_matches.before_loop
    async def before_check_for_completed_matches(self):
        """Wait until the bot is ready before starting the loop."""
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(MonitorMatchmakingManager(bot))

import logging
from datetime import datetime
from typing import Dict, List, Optional

import discord
from aws.dynamodb import DynamoDbManager
from aws.s3 import S3ClientManager
from cogs.constants import COLOR_EMBED, ROLE_ADMIN, ROLE_MOD
from matchmaking.matches.completed_match import CompletedMatch
from matchmaking.mm_event_bus import EventType, MatchmakingManagerEventBus
from cogs.matchmaking_manager_v2 import get_matchmaking_manager_v2
from cogs.party_manager import get_party_manager
from discord import TextChannel, ui
from discord.ext import commands, tasks
from helpers import get_guild, get_ping_channel, get_rank_for_player
from matchmaking.matches.active_match import ActiveMatch
from models.leaderboard_rank import LeaderboardRank
from models.player_profile import PlayerProfile


class MatchQueueView(ui.View):
    """
    A view for joining and leaving a matchmaking queue, plus the players in the queue and active queues.
    """

    def __init__(self, bot: commands.Bot, queue_id: str, queue_channel: TextChannel):
        super().__init__(timeout=None)
        self.bot = bot
        self.ddb_manager = DynamoDbManager()
        self.s3_manager = S3ClientManager()

        mm_manager = get_matchmaking_manager_v2()
        if mm_manager is None:
            raise ValueError(
                "Matchmaking manager, a fatally dependent resource, not found."
            )
        self.mm_manager = mm_manager
        self.mm_event_bus = MatchmakingManagerEventBus()

        self.queue_id = queue_id
        self.queue_channel = queue_channel
        self.active_match_messages: Dict[int, discord.message.Message] = {}

        # Maps bot_match_id -> channel for active matches
        self.active_match_channels: Dict[int, discord.TextChannel] = {}

        self.prev_num_queued_players: int = -1

        self.new_active_match_sub = self.mm_event_bus.subscribe(
            EventType.NEW_ACTIVE_MATCH
        )
        self.new_compeleted_match_sub = self.mm_event_bus.subscribe(
            EventType.NEW_COMPLETED_MATCH
        )
        self.queue_started_sub = self.mm_event_bus.subscribe(EventType.QUEUE_STARTED)

    async def start_task(self, message: discord.message.Message):
        self.active_queue_message = message
        self.update_queue_embed.start()
        self.process_active_matches.start()
        self.process_completed_matches.start()
        self.ping_queue_started_event.start()

    async def stop_task(self):
        await self.active_queue_message.delete()
        self.update_queue_embed.stop()
        self.process_active_matches.stop()
        self.process_completed_matches.stop()
        self.ping_queue_started_event.stop()
        for _, message in self.active_match_messages.items():
            await message.delete()

    @ui.button(label="Join Queue", style=discord.ButtonStyle.green)
    async def join_queue(self, interaction: discord.Interaction, button: ui.Button):
        user = interaction.user

        logging.info(
            f"Processing button pressed to join queue {self.queue_id} for user {user.name}"
        )

        player_profile = self.ddb_manager.query_player_profile_for_discord_account_id(
            user.id
        )

        if not player_profile:
            await interaction.response.send_message(
                "You have not registered your account yet.", ephemeral=True
            )
            return

        if self.mm_manager.is_player_in_match(player_profile):
            await interaction.response.send_message(
                "You are already in a match.", ephemeral=True
            )
            return

        with_teammate: Optional[PlayerProfile] = None

        # Handle partied players joining queue.
        party_manager = get_party_manager()
        if party_manager:
            player_party = party_manager.get_player_party(player_profile)
        if player_party is not None:
            # Update this party's inactivity expiration date
            party_manager.update_party_activity(player_party)  # type: ignore

            queue = self.mm_manager.get_queue(self.queue_id)
            if not queue:
                logging.warning(
                    f"Unexpectedly could not find queue with ID {self.queue_id} in mm manager."
                )
                return

            # If this is a solo queue, do not allow player to join
            if not queue.queue.type.is_2v2():
                await interaction.response.send_message(
                    "This queue does not allowed partied players. Use /unparty first!",
                    ephemeral=True,
                )
                return

            # If their teammate is in a match, warn them and do not allow them to join
            teammate = player_party.teammate(player_profile)
            if self.mm_manager.is_player_in_match(teammate):
                await interaction.response.send_message(
                    f"Your teammate <@{teammate.discord_account_id}> is still in a match.",
                    ephemeral=True,
                )
                return

            added_queue = self.mm_manager.add_party_to_queue(
                player_party.players(), self.queue_id
            )
            with_teammate = teammate

        # Otherwise solo queueing
        else:
            added_queue = self.mm_manager.add_party_to_queue(
                [player_profile], self.queue_id
            )

        if not added_queue:
            await interaction.response.send_message(
                f"Failed to join queue {self.queue_id}.", ephemeral=True
            )
            return

        with_teammate_msg = (
            f" with <@{with_teammate.discord_account_id}>" if with_teammate else ""
        )
        await interaction.response.send_message(
            f"Joined queue {self.queue_id}{with_teammate_msg}.", ephemeral=True
        )

        await self.update_queue_embed()

    @ui.button(label="Leave Queue", style=discord.ButtonStyle.red)
    async def leave_queue(self, interaction: discord.Interaction, button: ui.Button):
        user = interaction.user

        logging.info(
            f"Processing button pressed to leave queue {self.queue_id} for user {user.name}"
        )

        player_profile = self.ddb_manager.query_player_profile_for_discord_account_id(
            user.id
        )

        if not player_profile:
            # Don't tell the user anything, they probably aren't registered
            return

        requested_queue = self.mm_manager.get_queue(self.queue_id)

        if not requested_queue:
            logging.error(
                f"When attempting to leave queue {self.queue_id}, queue was not found."
            )
            return

        player_profiles = []
        for party in requested_queue.player_parties:
            for player in party.players():
                player_profiles.append(player)

        if player_profile not in player_profiles:
            await interaction.response.send_message(
                f"You are not in queue {self.queue_id}.", ephemeral=True
            )
            return

        party_manager = get_party_manager()
        if party_manager:
            player_party = party_manager.get_player_party(player_profile)
        if player_party is not None:
            self.mm_manager.remove_party_from_queue(
                player_party.players(), self.queue_id
            )
        else:
            self.mm_manager.remove_party_from_queue([player_profile], self.queue_id)

        await interaction.response.send_message(
            f"Left queue {self.queue_id}.", ephemeral=True
        )

        await self.update_queue_embed()

    @tasks.loop(seconds=15)
    async def update_queue_embed(self) -> None:
        logging.debug(f"Updating embed for queue {self.queue_id}.")

        queue = self.mm_manager.get_queue(self.queue_id)

        if queue is None:
            logging.error(
                f"When updating MatchQueueView embed, queue {self.queue_id} was not found."
            )
            raise ValueError(f"Queue {self.queue_id} not found.")

        num_players = 0
        for party in queue.player_parties:
            num_players += len(party.players())

        # If the number of players hasn't changed, don't bother updating the queue.
        if num_players == self.prev_num_queued_players:
            logging.debug(
                f"Number of players in queue {self.queue_id} has not changed, skipping update."
            )
            return
        self.prev_num_queued_players = num_players

        queue_name = (
            queue.queue.display_name
            if queue.queue.display_name
            else queue.queue.queue_id
        )
        embed = discord.Embed(
            title=f"Better Matchmaking Queue - {queue_name}",
            color=COLOR_EMBED,
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text="Last updated")

        leaderboard_id = queue.queue.primary_leaderboard_id
        if leaderboard_id is None or num_players == 0:
            embed.add_field(name="Players:", value=num_players)
        else:
            leaderboard_ranks = (
                self.ddb_manager.get_ranks_for_leaderboard_by_min_elo_descending(
                    leaderboard_id
                )
            )
            ranks_to_count: Dict[LeaderboardRank, int] = {}
            for party in queue.player_parties:
                for player in party.players():
                    player_elo = self.ddb_manager.get_or_create_player_elo(
                        player.tm_account_id,
                        leaderboard_id,
                    )
                    rank = get_rank_for_player(
                        player_elo.elo, leaderboard_id, leaderboard_ranks
                    )
                    if rank is None:
                        logging.error(
                            f"Failed to get rank for player {player_elo.tm_account_id} "
                            f"with elo {player_elo.elo} on leaderboard {leaderboard_id}."
                        )
                        continue
                    if ranks_to_count.get(rank) is None:
                        ranks_to_count[rank] = 1
                    else:
                        ranks_to_count[rank] += 1

            value = ""
            for rank in leaderboard_ranks:
                if ranks_to_count.get(rank) is None:
                    continue
                value += f"{rank.display_name}: {ranks_to_count[rank]}\n"

            embed.add_field(name="Players:", value=value)
        try:
            await self.active_queue_message.edit(embed=embed)
        except Exception as e:
            logging.warning(f"Failed to update queue {queue_name} embed: {e}")

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
                    "No bot ping channel provided. Players won't get any indication of their match starting."
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
        match_channel: TextChannel,
    ) -> None:
        """Sends a ping to all match players in discord that their match has started.

        Args:
            players (List[PlayerProfile]): The players in the match to ping.
            bot_match_id (int): The bot match ID of the match starting.
            match_channel (TextChannel): The channel in which to ping for the new match.
        """
        try:
            embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())
            embed.add_field(
                name="❗ Match Found",
                value=f'Pinged players, join the Better Matchmaking club and click activity "BMM - #{bot_match_id}"!',
            )

            content = ""
            for player in players:
                content += f"<@{player.discord_account_id}> "

            await match_channel.send(content=content, embed=embed)
        except Exception as e:
            logging.error(
                f"Error sending message for match start to players {players}: {e}"
            )

    async def process_new_active_match(
        self, active_match: ActiveMatch, match_channel: TextChannel
    ) -> None:
        # Handle solo match specific cases
        if isinstance(active_match.player_profiles, List):
            # Create an embed to put in the queue channel to display the ongoing match
            players = active_match.player_profiles

            value = ""
            for player in players:
                value += f"<@{player.discord_account_id}>\n"

            embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())
            embed.add_field(
                name=f"🏎️ Match #{active_match.bot_match_id} in progress...", value=value
            )

            message = await self.queue_channel.send(embed=embed)
        # Handle 2v2 match specific cases
        else:
            # Create an embed to put in the queue channel to display the ongoing match
            embed = discord.Embed(
                title=f"🏎️ Match #{active_match.bot_match_id} in progress...",
                color=COLOR_EMBED,
                timestamp=datetime.utcnow(),
            )

            team_a = active_match.player_profiles.team_a
            embed.add_field(
                name="Blue Team",
                value=f"<@{team_a.player_a.discord_account_id}> & <@{team_a.player_b.discord_account_id}>",
            )

            team_b = active_match.player_profiles.team_b
            embed.add_field(
                name="Red Team",
                value=f"<@{team_b.player_a.discord_account_id}> & <@{team_b.player_b.discord_account_id}>",
            )

            message = await self.queue_channel.send(embed=embed)

        self.active_match_messages[active_match.bot_match_id] = message

        # Ping players
        await self.send_players_match_start_notification(
            active_match.participants(), active_match.bot_match_id, match_channel
        )

    @tasks.loop(seconds=5)
    async def process_active_matches(self) -> None:
        """
        Adds a message to the queue channel containing active match info.
        Creates a new discord channel with the match players, handling pings
        if necessary (2v2 workaround).
        """
        logging.debug(
            f"Match Queue Cog checking for new active matches to process for queue {self.queue_id}"
        )

        # Get new active matches and send the messages for them.
        active_match = self.mm_event_bus.get_new_active_match(self.new_active_match_sub)
        if active_match is not None:
            # Ignore if it doesn't belong to this queue
            if active_match.match_queue.queue_id != self.queue_id:
                return

            processed = True

            match_channel = await self.create_active_match_channel(active_match)
            if not match_channel:
                logging.error(
                    f"Failed to create channel for match {active_match.bot_match_id}."
                )
                return

            self.bot.loop.create_task(
                self.process_new_active_match(active_match, match_channel)
            )

            if processed:
                logging.info(
                    f"New match with bot match ID {active_match.bot_match_id} added to queue view {self.queue_id}"
                )

    @tasks.loop(seconds=5)
    async def process_completed_matches(self) -> None:
        """
        Deletes the message for the active match of new completed matches.
        Deletes the channel for that specific match.
        """
        logging.debug(
            f"Match Queue Cog checking for new completed matches to process for queue {self.queue_id}"
        )

        # Get completed matches and delete the messages for them.
        completed_match = self.mm_event_bus.get_new_completed_match(
            self.new_compeleted_match_sub
        )
        if completed_match is not None:
            # Ignore if it doesn't belong to this queue
            if completed_match.active_match.match_queue.queue_id != self.queue_id:
                return

            try:
                message = self.active_match_messages.pop(
                    completed_match.active_match.bot_match_id
                )

                await message.delete()

                await self.delete_active_match_channel(completed_match)

                logging.info(
                    f"Completed match with bot match ID {completed_match.active_match.bot_match_id} "
                    f"removed from queue view {self.queue_id}"
                )
            except Exception as e:
                logging.error(
                    f"Failed to delete message for completed match with bot match ID "
                    f"{completed_match.active_match.bot_match_id} in queue view {self.queue_id}: {e}"
                )

    @tasks.loop(seconds=5)
    async def ping_queue_started_event(self) -> None:
        """Sends a ping to the queue's channel if a QUEUE_STARTED event has been received."""
        logging.debug(f"Checking for new QUEUE_STARTED event for queue {self.queue_id}")

        queue_started = self.mm_event_bus.get_new_queue_started(self.queue_started_sub)
        if queue_started is None:
            return

        # Ignore if it isn't for this queue
        if queue_started.queue_id != self.queue_id:
            return

        queue = self.mm_manager.get_queue(self.queue_id)
        if not queue:
            logging.warning(
                f"Queue {self.queue_id} not found. It's either inactive or not being tracked."
            )
            return

        queue_ping_role_id = queue.queue.ping_role_id
        if not queue_ping_role_id:
            logging.warning(f"No ping role configured for queue {self.queue_id}")
            return

        # NOTE we are operating under the assumption that this bot is only connected to one server
        guild = self.bot.guilds[0]
        queue_ping_role = guild.get_role(queue_ping_role_id)
        if not queue_ping_role:
            logging.warning(f"Role {queue_ping_role_id} not found in guild {guild}")
            return

        embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())
        embed.add_field(
            name="❗ Queue Activated",
            value=f"{self.queue_id} queue has active players.",
            inline=True,
        )
        msg = await self.queue_channel.send(
            content=f"{queue_ping_role.mention}", embed=embed
        )

        # Delete the message after 60 seconds
        await msg.delete(delay=60)

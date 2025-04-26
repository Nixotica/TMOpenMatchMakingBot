import logging
from datetime import datetime

import discord
from aws.dynamodb import DynamoDbManager
from aws.s3 import S3ClientManager
from cogs.constants import COLOR_EMBED, ROLE_ADMIN, ROLE_MOD
from discord.ext import commands
from cogs.matchmaking_manager_v2 import get_matchmaking_manager_v2
from helpers import get_profile_channel, get_rank_for_player


class General(commands.Cog):
    """
    General bot commands for managing configs and discord integration.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.s3_manager = S3ClientManager()
        self.ddb_manager = DynamoDbManager()

        mm_manager = get_matchmaking_manager_v2()
        if mm_manager is None:
            raise ValueError(
                "Matchmaking manager, a fatally dependent resource, not found."
            )
        self.mm_manager = mm_manager

    @commands.hybrid_command(
        name="ping",
        description="Check if the bot is alive by seeing a response in the bot messages channel.",
    )
    @commands.has_role(ROLE_ADMIN)
    async def ping(self, ctx: commands.Context) -> None:
        logging.info(f"Processing command to ping from user {ctx.message.author.name}.")

        configs = self.s3_manager.get_configs()
        if configs.bot_messages_channel_id is None:
            await ctx.send("Bot messages channel not set. But PONG anyway!")
            return

        ping_channel = self.bot.get_channel(configs.bot_messages_channel_id)

        pong_embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())
        pong_embed.add_field(name="⚠️", value="Pong!", inline=True)

        await ping_channel.send(embed=pong_embed)  # type: ignore
        await ctx.send("Pinged the bot messages channel.", ephemeral=True)

    @commands.hybrid_command(
        name="set_bot_messages_channel",
        description="Set the channel for bot messages",
    )
    @commands.has_role(ROLE_ADMIN)
    async def set_bot_messages_channel(
        self,
        ctx: commands.Context,
        channel_id: str,  # Cannot be int - too long for discord bot
    ) -> None:
        logging.info(
            f"Processing command to set bot messages channel from user {ctx.message.author.name}."
        )

        channel_id = eval(channel_id)
        if not isinstance(channel_id, int):
            await ctx.send(f"Invalid channel ID: {channel_id}.")
            return

        configs = self.s3_manager.get_configs()
        configs.bot_messages_channel_id = channel_id
        self.s3_manager.update_config(configs)

        await ctx.send(f"Bot messages channel set to {channel_id}.", ephemeral=True)

    @commands.hybrid_command(
        name="link_pings_role",
        description="Link a role to a pingable role used by the bot instead of @everyone",
    )
    @commands.has_role(ROLE_ADMIN)
    async def link_pings_role(self, ctx: commands.Context, role: discord.Role) -> None:
        logging.info(
            f"Processing command to link pings role from user {ctx.message.author.name}."
        )

        configs = self.s3_manager.get_configs()
        configs.pings_role_id = role.id
        self.s3_manager.update_config(configs)

        await ctx.send(f"Pings role set to {role.name}.", ephemeral=True)

    @commands.hybrid_command(
        name="cancel_match",
        description="Cancel an onging match by providing the bot match ID",
    )
    @commands.has_role(ROLE_MOD)
    async def cancel_match(self, ctx: commands.Context, bot_match_id: int) -> None:
        logging.info(
            f"Processing command to cancel match from user {ctx.message.author.name}."
        )

        canceled_match = self.mm_manager.cancel_match(bot_match_id)

        if not canceled_match:
            await ctx.send(
                f"Failed to cancel match {bot_match_id}. Is it already finished?",
                ephemeral=True,
            )
            return

        players = canceled_match.participants()
        player_discord_ids_str = ""
        for player in players:
            player_discord_ids_str += f"<@{player.discord_account_id}> "

        await ctx.send(
            f"Match {bot_match_id} cancelled. Affected players: {player_discord_ids_str}.",
            ephemeral=True,
        )

    @commands.hybrid_command(name="profile", description="See your profile")
    async def profile(
        self,
        ctx: commands.Context,
        member: discord.Member,
    ) -> None:
        logging.info(
            f"Processing command to see profile for user {member.name} from {ctx.message.author.name}."
        )

        player_profile = self.ddb_manager.query_player_profile_for_discord_account_id(
            member.id
        )

        if not player_profile:
            await ctx.send("No profile found.", ephemeral=True)
            return

        player_elos = self.ddb_manager.get_player_elo_on_all_leaderboards(
            player_profile.tm_account_id
        )

        profile_title = "Player Profile"
        matches_played = self.ddb_manager.get_matches_played(
            player_profile.tm_account_id
        )

        total_matches_played = 0
        total_matches_won = 0
        most_played_queue_id = None
        most_played_queue_matches = 0
        for match in matches_played:
            total_matches_played += match.matches_played
            total_matches_won += match.matches_won

            if match.matches_played > most_played_queue_matches:
                most_played_queue_id = match.queue_id
                most_played_queue_matches = match.matches_played

        # TODO - move to a fake queue with id "legacy" in matches played table for all players
        total_matches_played += player_profile.matches_played

        total_matches_played_name = "Total Matches Played"
        total_matches_played_value = (
            f"{total_matches_played} played | {total_matches_won} won"
        )

        embed = discord.Embed(
            title=profile_title,
            color=COLOR_EMBED,
            timestamp=datetime.utcnow(),
            description=member.mention,
        )
        embed.add_field(
            name=total_matches_played_name, value=total_matches_played_value
        )

        most_played_queue_name = "Most Played Queue"
        most_played_queue_value = (
            f"{most_played_queue_id} ({most_played_queue_matches} matches)"
            if most_played_queue_id is not None
            else "N/A"
        )
        embed.add_field(name=most_played_queue_name, value=most_played_queue_value)

        leaderboard_section_name = "Leaderboards"
        leaderboard_section_value = ""
        for player_elo in player_elos:
            leaderboard = self.ddb_manager.get_leaderboard(player_elo.leaderboard_id)
            if not leaderboard:
                logging.warning(
                    f"Leaderboard {player_elo.leaderboard_id} not found. Skipping."
                )
                continue
            if leaderboard.active is False:
                continue

            leaderboard_id = player_elo.leaderboard_id
            leaderboard_ranks = (
                self.ddb_manager.get_ranks_for_leaderboard_by_min_elo_descending(
                    leaderboard_id
                )
            )

            leaderboard_name = (
                leaderboard.display_name
                if leaderboard.display_name is not None
                else leaderboard_id
            )
            player_rank = get_rank_for_player(
                player_elo.elo, leaderboard_id, leaderboard_ranks
            )

            if player_rank is not None:
                leaderboard_elo = f"{player_rank.display_name} {player_elo.elo} elo"
            else:
                leaderboard_elo = f"{player_elo.elo} elo"

            leaderboard_section_value += f"{leaderboard_name} ({leaderboard_elo})\n"

        embed.add_field(
            name=leaderboard_section_name, value=leaderboard_section_value, inline=False
        )

        # Send to profile channel, if set, and make it non-ephemeral
        profile_channel = await get_profile_channel(self.bot, self.s3_manager)
        if profile_channel is not None:
            await profile_channel.send(embed=embed)
            await ctx.send("Profile sent to profile channel.", ephemeral=True)
        else:
            await ctx.send(embed=embed, ephemeral=True)

        return

    @commands.hybrid_command(
        name="set_profile_channel",
        description="Set the channel that displays player profiles",
    )
    @commands.has_role(ROLE_ADMIN)
    async def set_profile_channel(
        self,
        ctx: commands.Context,
        channel_id: str,  # Cannot be int - too long for discord bot
    ) -> None:
        logging.info(
            f"Processing command to set profile channel from user {ctx.message.author.name}."
        )

        channel_id = eval(channel_id)
        if not isinstance(channel_id, int):
            await ctx.send(f"Invalid channel ID: {channel_id}.")
            return

        configs = self.s3_manager.get_configs()
        configs.profile_channel_id = channel_id
        self.s3_manager.update_config(configs)

        await ctx.send(f"Profile channel set to {channel_id}.", ephemeral=True)

    @commands.hybrid_command(
        name="fake_join_queue",
        description="Fake a player joining a queue. Only works on simulated queue types.",
    )
    @commands.has_role(ROLE_ADMIN)
    async def fake_join_queue(
        self, ctx: commands.Context, queue_id: str, member: discord.Member
    ) -> None:
        logging.info(
            f"Processing command to fake join queue {queue_id} for {member.name} from {ctx.message.author.name}."
        )

        player_profile = self.ddb_manager.query_player_profile_for_discord_account_id(
            member.id
        )

        if not player_profile:
            await ctx.send("Player not found.", ephemeral=True)
            return

        active_queue = self.mm_manager.get_queue(queue_id)

        if active_queue is None:
            await ctx.send(f"Could not find queue {queue_id}", ephemeral=True)
            return

        if not active_queue.queue.type.is_simulated():
            await ctx.send(
                f"Queue {queue_id} is not a simulated queue. You can't fake join it.",
                ephemeral=True,
            )
            return

        added_party = active_queue.add_party([player_profile])
        if not added_party:
            await ctx.send(f"Failed to add player to queue {queue_id}", ephemeral=True)
            return

        await ctx.send(
            f"Successfully faked player {member.name} joining queue {queue_id}",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))

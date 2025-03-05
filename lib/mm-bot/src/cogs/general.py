import logging
from datetime import datetime

import discord
from aws.dynamodb import DynamoDbManager
from aws.s3 import S3ClientManager
from cogs.constants import COLOR_EMBED, ROLE_ADMIN, ROLE_MOD
from discord.ext import commands
from helpers import get_rank_for_player
from matchmaking.match_queues.matchmaking_manager import MatchmakingManager


class General(commands.Cog):
    """
    General bot commands for managing configs and discord integration.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mm_manager = MatchmakingManager()
        self.s3_manager = S3ClientManager()
        self.ddb_manager = DynamoDbManager()

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
                f"Failed to cancel match {bot_match_id}. Is it already finished?"
            )
            return

        players = canceled_match.player_profiles
        player_discord_ids_str = ""
        if isinstance(players, list):
            for player in players:
                player_discord_ids_str += f"<@{player.discord_account_id}> "

        await ctx.send(
            f"Match {bot_match_id} cancelled. Affected players: {player_discord_ids_str}."
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
            await ctx.send("No profile found.")
            return

        player_elos = self.ddb_manager.get_player_elo_on_all_leaderboards(
            player_profile.tm_account_id
        )

        profile_title = "Player Profile"

        matches_played_name = "Matches Played"
        matches_played_value = player_profile.matches_played

        embed = discord.Embed(
            title=profile_title,
            color=COLOR_EMBED,
            timestamp=datetime.utcnow(),
            description=member.mention,
        )
        embed.add_field(name=matches_played_name, value=matches_played_value)

        for player_elo in player_elos:
            leaderboard_id = player_elo.leaderboard_id
            leaderboard_ranks = (
                self.ddb_manager.get_ranks_for_leaderboard_by_min_elo_descending(
                    leaderboard_id
                )
            )

            leaderboard_name = f"{leaderboard_id} Leaderboard"
            player_rank = get_rank_for_player(
                player_elo.elo, leaderboard_id, leaderboard_ranks
            )

            if player_rank is not None:
                leaderboard_value = f"{player_rank.display_name} {player_elo.elo} elo"
            else:
                leaderboard_value = f"{player_elo.elo} elo"

            embed.add_field(name=leaderboard_name, value=leaderboard_value)

        await ctx.send(embed=embed, ephemeral=True)
        return


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))

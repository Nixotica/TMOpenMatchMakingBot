import logging
from typing import List
import discord
from discord.ext import commands
from aws.dynamodb import DynamoDbManager
from aws.s3 import S3ClientManager
from views.leaderboard import LeaderboardView
from models.leaderboard import Leaderboard
from cogs.constants import ROLE_ADMIN


class LeaderboardViewBuilder(commands.Cog):
    """
    Generates the leaderboard views for the global leaderboard and queue-specific leaderboards (TBD).
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ddb_manager = DynamoDbManager()
        self.s3_manager = S3ClientManager()
        self.views: List[LeaderboardView] = []

    async def cog_load(self) -> None:
        logging.info("Leaderboard View Builder loading...")
        await self.setup_leaderboards()

    async def cog_unload(self) -> None:
        logging.info("Leaderboard View Builder unloading...")
        for view in self.views:
            await view.stop_task()
            logging.info(f"Unloading view for Leaderboard ID {view.leaderboard_id}.")
        logging.info("All Leaderboard Views have been unloaded.")

    async def add_leaderboard_view(self, leaderboard: Leaderboard) -> None:
        # If view is already setup, ignore (this will sometimes run multiple times on startup...)
        if any(
            view.leaderboard_id == leaderboard.leaderboard_id for view in self.views
        ):
            return

        channel_id = leaderboard.channel_id
        channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(
            channel_id
        )  # Caching work-around

        if not channel:
            logging.error(f"Channel {channel_id} not found.")
            raise ValueError(f"Channel {channel_id} not found.")

        if not isinstance(channel, discord.TextChannel):
            logging.error(f"Channel {channel_id} is not a text channel.")
            raise ValueError(f"Channel {channel_id} is not a text channel.")

        logging.info(f"Sending global leaderboard view to channel {channel_id}.")

        view = LeaderboardView(self.bot, leaderboard.leaderboard_id)

        self.views.append(view)

        embed = discord.Embed(title="Pending leaderboard setup...")

        message = await channel.send(embed=embed, view=view)

        await view.start_task(message)

        await view.update_embed()

    async def setup_leaderboards(self) -> None:
        leaderboards = self.ddb_manager.get_leaderboards()

        for leaderboard in leaderboards:
            await self.add_leaderboard_view(leaderboard)

    @commands.hybrid_command(
        name="create_leaderboard",
        description="Create a new leaderboard",
    )
    @commands.has_role(ROLE_ADMIN)
    async def create_leaderboard(
        self,
        ctx: commands.Context,
        leaderboard_id: str,
        channel_id: str,  # Cannot be int - too long for discord bot
    ) -> None:
        logging.info(
            f"Processing command to create leaderboard {leaderboard_id} from user {ctx.message.author.name}."
        )

        channel_id = eval(channel_id)
        if not isinstance(channel_id, int):
            await ctx.send(f"Invalid channel ID: {channel_id}.")
            return

        leaderboard = Leaderboard(
            leaderboard_id=leaderboard_id,
            channel_id=channel_id,
        )

        success = self.ddb_manager.create_leaderboard(leaderboard)

        if success:
            await self.add_leaderboard_view(leaderboard)
            await ctx.send(f"Leaderboard {leaderboard_id} created.")
        else:
            await ctx.send(
                f"Failed to create leaderboard {leaderboard_id}, unknown error."
            )

    @commands.hybrid_command(
        name="list_leaderboards",
        description="List all leaderboards",
    )
    @commands.has_role(ROLE_ADMIN)
    async def list_leaderboards(
        self,
        ctx: commands.Context,
    ) -> None:
        logging.info(
            f"Processing command to list leaderboards from user {ctx.message.author.name}."
        )

        leaderboards = self.ddb_manager.get_leaderboards()

        if not leaderboards:
            await ctx.send("No leaderboards found.")
            return

        embed = discord.Embed(title="Leaderboards")

        for leaderboard in leaderboards:
            embed.add_field(
                name=leaderboard.leaderboard_id, value=leaderboard.channel_id
            )

        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(
        name="set_main_leaderboard",
        description="Set the main leaderboard for which ranks are assigned",
    )
    @commands.has_role(ROLE_ADMIN)
    async def set_main_leaderboard(
        self,
        ctx: commands.Context,
        leaderboard_id: str,
    ) -> None:
        logging.info(
            f"Processing command to set main leaderboard to {leaderboard_id} from user {ctx.message.author.name}"
        )

        leaderboards = self.ddb_manager.get_leaderboards()
        leaderboard_ids = [l.leaderboard_id for l in leaderboards]

        if leaderboard_id not in leaderboard_ids:
            await ctx.send(
                "Could not find leaderboard with matching ID. Check with /list_leaderboards."
            )
            return

        configs = self.s3_manager.get_configs()
        configs.global_leaderboard_id = leaderboard_id
        self.s3_manager.update_config(configs)

        await ctx.send(f"Updated main leaderboard to {leaderboard_id}")


async def setup(bot: commands.Bot) -> None:
    leaderboard_view_builders = LeaderboardViewBuilder(bot)
    await bot.add_cog(leaderboard_view_builders)

    await leaderboard_view_builders.setup_leaderboards()

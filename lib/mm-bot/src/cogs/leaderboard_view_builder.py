import logging
from typing import List

import discord
from aws.dynamodb import DynamoDbManager
from aws.s3 import S3ClientManager
from cogs.constants import ROLE_MOD
from discord.ext import commands
from models.leaderboard import Leaderboard
from models.leaderboard_rank import LeaderboardRank
from views.leaderboard import LeaderboardView


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

        # Disabling this to avoid throttling issues on leaderboard loading
        # await view.update_embed()

    async def setup_leaderboards(self) -> None:
        leaderboards = self.ddb_manager.get_leaderboards()

        for leaderboard in leaderboards:
            try:
                await self.add_leaderboard_view(leaderboard)
            except Exception as e:
                logging.error(
                    f"Error setting up leaderboard {leaderboard.leaderboard_id}: {e}"
                )
                continue

    @commands.hybrid_command(
        name="create_leaderboard",
        description="Create a new leaderboard",
    )
    @commands.has_role(ROLE_MOD)
    async def create_leaderboard(
        self,
        ctx: commands.Context,
        leaderboard_id: str,
        display_name: str,
        channel_id: str,  # Cannot be int - too long for discord bot
    ) -> None:
        logging.info(
            f"Processing command to create leaderboard {leaderboard_id} from user {ctx.message.author.name}."
        )

        channel_id = eval(channel_id)
        if not isinstance(channel_id, int):
            await ctx.send(f"Invalid channel ID: {channel_id}.", ephemeral=True)
            return

        leaderboard = Leaderboard(
            leaderboard_id=leaderboard_id,
            channel_id=channel_id,
            display_name=display_name,
            active=True,
        )

        success = self.ddb_manager.create_leaderboard(leaderboard)

        if success:
            await self.add_leaderboard_view(leaderboard)
            await ctx.send(f"Leaderboard {leaderboard_id} created.", ephemeral=True)
        else:
            await ctx.send(
                f"Failed to create leaderboard {leaderboard_id}, unknown error.",
                ephemeral=True,
            )

    @commands.hybrid_command(
        name="list_leaderboards",
        description="List leaderboards, and optionally hide disabled leaderboards from list.",
    )
    @commands.has_role(ROLE_MOD)
    async def list_leaderboards(
        self,
        ctx: commands.Context,
        hide_disabled: bool,
    ) -> None:
        logging.info(
            f"Processing command to list leaderboards from user {ctx.message.author.name}."
        )

        leaderboards = self.ddb_manager.get_leaderboards(hide_disabled)

        if not leaderboards:
            await ctx.send("No leaderboards found.", ephemeral=True)
            return

        embed = discord.Embed(title="Leaderboards")

        for leaderboard in leaderboards:
            display_name = (
                leaderboard.display_name
                if leaderboard.display_name
                else leaderboard.leaderboard_id
            )
            active = "True" if leaderboard.active else "False"
            value = f"Channel ID: {leaderboard.channel_id}\n"
            value += f"Display Name: {display_name}\n"
            value += f"Active: {active}\n"

            ranks = self.ddb_manager.get_ranks_for_leaderboard_by_min_elo_descending(
                leaderboard.leaderboard_id
            )
            ranks_list = "Ranks:\n"
            for rank in ranks:
                ranks_list += f" - {rank.display_name} (Min Elo: {rank.min_elo})\n"
            value += ranks_list

            embed.add_field(name=leaderboard.leaderboard_id, value=value, inline=False)

        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(
        name="rename_leaderboard",
        description="Rename a leaderboard",
    )
    async def rename_leaderboard(
        self, ctx: commands.Context, leaderboard_id: str, new_name: str
    ) -> None:
        logging.info(
            f"Processing command to rename leaderboard {leaderboard_id} from user {ctx.message.author.name}."
        )

        # Check if the leaderboard exists
        leaderboard = self.ddb_manager.get_leaderboard(leaderboard_id)
        if not leaderboard:
            await ctx.send(
                f"Leaderboard {leaderboard_id} not found. Use /list_leaderboards to check which ones exist.",
                ephemeral=True,
            )
            return

        # Update the leaderboard in dynamo
        leaderboard.display_name = new_name
        self.ddb_manager.update_leaderboard(leaderboard)

        await ctx.send(
            f"Leaderboard {leaderboard_id} renamed to {new_name}.", ephemeral=True
        )

    @commands.hybrid_command(
        name="refresh_leaderboards",
        description="Refresh all leaderboards to get the latest elo and ranks",
    )
    @commands.has_role(ROLE_MOD)
    async def refresh_leaderboards(
        self,
        ctx: commands.Context,
    ) -> None:
        logging.info(
            f"Processing command to refresh leaderboards from user {ctx.message.author.name}."
        )

        for leaderboard in self.views:
            await leaderboard.update_embed()

        leaderboard_ids = [v.leaderboard_id for v in self.views]
        await ctx.send(f"Refreshed leaderboards: {leaderboard_ids}")

    @commands.hybrid_command(
        name="set_main_leaderboard",
        description="Set the main leaderboard for which rank roles are assigned",
    )
    @commands.has_role(ROLE_MOD)
    async def set_main_leaderboard(
        self,
        ctx: commands.Context,
        leaderboard_id: str,
    ) -> None:
        logging.info(
            f"Processing command to set main leaderboard to {leaderboard_id} from user {ctx.message.author.name}"
        )

        leaderboards = self.ddb_manager.get_leaderboards()
        leaderboard_ids = [leaderboard.leaderboard_id for leaderboard in leaderboards]

        if leaderboard_id not in leaderboard_ids:
            await ctx.send(
                "Could not find leaderboard with matching ID. Check with /list_leaderboards."
            )
            return

        configs = self.s3_manager.get_configs()
        configs.global_leaderboard_id = leaderboard_id
        self.s3_manager.update_config(configs)

        await ctx.send(f"Updated main leaderboard to {leaderboard_id}")

    @commands.hybrid_command(
        name="create_rank",
        description="Create a new rank for a leaderboard",
    )
    @commands.has_role(ROLE_MOD)
    async def create_rank(
        self,
        ctx: commands.Context,
        rank_id: str,
        display_name: str,
        leaderboard_id: str,
        min_elo: int,
    ) -> None:
        logging.info(
            f"Processing command to create rank {rank_id} from user {ctx.message.author.name}."
        )

        leaderboards = self.ddb_manager.get_leaderboards()
        leaderboard_ids = [leaderboard.leaderboard_id for leaderboard in leaderboards]

        if leaderboard_id not in leaderboard_ids:
            await ctx.send(
                "Could not find leaderboard with matching ID. Check with /list_leaderboards.",
                ephemeral=True,
            )
            return

        leaderboard_rank = LeaderboardRank(
            rank_id=rank_id,
            display_name=display_name,
            leaderboard_id=leaderboard_id,
            min_elo=min_elo,
        )

        try:
            self.ddb_manager.create_leaderboard_rank(leaderboard_rank)
            await ctx.send(
                f"Rank {rank_id} created for leaderboard {leaderboard_id}.",
                ephemeral=True,
            )
        except Exception as e:
            await ctx.send(
                f"Failed to create rank {rank_id}, error: {e}.", ephemeral=True
            )

    @commands.hybrid_command(
        name="list_ranks",
        description="List all ranks for a leaderboard",
    )
    @commands.has_role(ROLE_MOD)
    async def list_ranks(self, ctx: commands.Context, leaderboard_id: str) -> None:
        logging.info(
            f"Processing command to list ranks for leaderboard {leaderboard_id} from user {ctx.message.author.name}."
        )

        leaderboards = self.ddb_manager.get_leaderboards()
        leaderboard_ids = [leaderboard.leaderboard_id for leaderboard in leaderboards]

        if leaderboard_id not in leaderboard_ids:
            await ctx.send(
                "Could not find leaderboard with matching ID. Check with /list_leaderboards.",
                ephemeral=True,
            )
            return

        ranks = self.ddb_manager.get_ranks_for_leaderboard_by_min_elo_descending(
            leaderboard_id
        )

        if not ranks:
            await ctx.send(
                f"No ranks found for leaderboard {leaderboard_id}.", ephemeral=True
            )
            return

        embed = discord.Embed(title=f"Ranks for leaderboard {leaderboard_id}")

        for rank in ranks:
            value = f"Display Name: {rank.display_name}\n"
            value += f"Min Elo: {rank.min_elo}\n"

            embed.add_field(name=rank.rank_id, value=value, inline=False)

        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(
        name="disable_leaderboard",
        description="Disable a leaderboard so it no longer shows up in its channel.",
    )
    @commands.has_role(ROLE_MOD)
    async def disable_leaderboard(
        self, ctx: commands.Context, leaderboard_id: str
    ) -> None:
        logging.info(
            f"Processing command to disable leaderboard {leaderboard_id} from user {ctx.message.author.name}."
        )

        # Check if the leaderboard exists
        leaderboard = self.ddb_manager.get_leaderboard(leaderboard_id)

        if not leaderboard:
            await ctx.send(
                f"Leaderboard {leaderboard_id} not found. Use /list_leaderboards to check which ones exist.",
                ephemeral=True,
            )
            return

        # Update the leaderboard in dynamo
        leaderboard.active = False
        self.ddb_manager.update_leaderboard(leaderboard)

        # Stop the leaderboard view task and remove it
        for view in self.views:
            if view.leaderboard_id == leaderboard_id:
                await view.stop_task()
                self.views.remove(view)
                break

        await ctx.send(f"Leaderboard {leaderboard_id} disabled.", ephemeral=True)

    @commands.hybrid_command(
        name="reenable_leaderboard",
        description="Re-enable an existing leaderboard to make it appear in its channel and become joinable.",
    )
    @commands.has_role(ROLE_MOD)
    async def reenable_leaderboard(
        self, ctx: commands.Context, leaderboard_id: str
    ) -> None:
        logging.info(
            f"Processing command to re-enable leaderboard {leaderboard_id} from user {ctx.message.author.name}."
        )

        # Check if the leaderboard exists
        leaderboard = self.ddb_manager.get_leaderboard(leaderboard_id)

        if not leaderboard:
            await ctx.send(
                f"Leaderboard {leaderboard_id} not found. Use /list_leaderboards to check which ones exist.",
                ephemeral=True,
            )
            return

        # Update the leaderboard in dynamo
        leaderboard.active = True
        self.ddb_manager.update_leaderboard(leaderboard)

        # Add the leaderboard view task back
        await self.add_leaderboard_view(leaderboard)

        await ctx.send(f"Leaderboard {leaderboard_id} re-enabled.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    leaderboard_view_builders = LeaderboardViewBuilder(bot)
    await bot.add_cog(leaderboard_view_builders)

    await leaderboard_view_builders.setup_leaderboards()

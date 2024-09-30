import logging
from typing import List
import discord
from discord.ext import commands
from aws.dynamodb import DynamoDbManager
from views.leaderboard import LeaderboardView
from models.leaderboard import Leaderboard

class LeaderboardViewBuilder(commands.Cog):
    """ 
    Generates the leaderboard views for the global leaderboard and queue-specific leaderboards (TBD).
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ddb_manager = DynamoDbManager()
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
        if any(view.leaderboard_id == leaderboard.leaderboard_id for view in self.views):
            return

        channel_id = leaderboard.channel_id
        channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id) # Caching work-around

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


# TODO - command for admins to /create_leaderboard which takes a queue id and makes a new leaderboard
# would require adding leaderboards table and adding field to match queues table for leaderboard

async def setup(bot: commands.Bot) -> None:
    leaderboard_view_builders = LeaderboardViewBuilder(bot)
    await bot.add_cog(leaderboard_view_builders)
    
    await leaderboard_view_builders.setup_leaderboards()
import logging
import discord
from discord.ext import commands
from aws.dynamodb import DynamoDbManager
from views.global_leaderboard import GlobalLeaderboardView

class LeaderboardViewBuilder(commands.Cog):
    """ 
    Generates the leaderboard views for the global leaderboard and queue-specific leaderboards (TBD).
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ddb_manager = DynamoDbManager()
        self.view: GlobalLeaderboardView | None = None # TODO - store multiple base class leaderboard views

    async def cog_load(self) -> None: 
        logging.info("Leaderboard View Builder loading...")
        await self.setup_leaderboards()

    async def cog_unload(self) -> None:
        logging.info("Leaderboard View Builder unloading...")
        if self.view is not None:
            await self.view.unload()
        logging.info("All Leaderboard Views have been unloaded.")

    async def setup_leaderboards(self) -> None:
        # TODO - loop over all queues registered in mm manager and separate by leaderboard group
        
        # If view is already setup, ignore (this will sometimes run multiple times on startup...)
        if self.view is not None:
            return

        # TODO - store this in some table of leaderboards? 
        channel_id = 1287229419588419644 # test server - Leaderboards - #global
        channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id) # Caching work-around

        if not channel:
            logging.error(f"Channel {channel_id} not found.")
            raise ValueError(f"Channel {channel_id} not found.")
        
        if not isinstance(channel, discord.TextChannel):
            logging.error(f"Channel {channel_id} is not a text channel.")
            raise ValueError(f"Channel {channel_id} is not a text channel.")
        
        logging.info(f"Sending global leaderboard view to channel {channel_id}.")

        self.view = GlobalLeaderboardView(self.bot)

        embed = discord.Embed(title="Pending leaderboard setup...")

        message = await channel.send(embed=embed, view=self.view)

        await self.view.give_message(message)

        await self.view.update_embed()

# TODO - command for admins to /create_leaderboard which takes a queue id and makes a new leaderboard
# would require adding leaderboards table and adding field to match queues table for leaderboard

async def setup(bot: commands.Bot) -> None:
    leaderboard_view_builders = LeaderboardViewBuilder(bot)
    await bot.add_cog(leaderboard_view_builders)
    
    await leaderboard_view_builders.setup_leaderboards()
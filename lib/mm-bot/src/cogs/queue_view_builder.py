import logging
from typing import List
import discord
from discord.ext import commands
from views.join_queue import JoinQueueView
from matchmaking.match_queues.matchmaking_manager import MatchmakingManager

class QueueViewBuilder(commands.Cog):
    """ 
    Generates the queue views for each active queue. 
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mm_manager = MatchmakingManager()
        self.views: List[JoinQueueView] = []
    
    async def cog_load(self) -> None:
        logging.info("Queue View Builder loading...")
        await self.setup_queues()

    async def cog_unload(self) -> None:
        logging.info("Queue View Builder unloading...")
        for view in self.views:
            await view.stop_task()
            logging.info(f"Stopped view for Queue ID {view.queue_id}.")
        logging.info("All Queue Views have been stopped.")

    async def setup_queues(self) -> None:
        active_queues = self.mm_manager.active_queues

        for queue in active_queues:
            # If view is already setup, ignore (this will sometimes run multiple times on startup...)
            if any(view.queue_id == queue.queue.queue_id for view in self.views):
                continue

            channel_id = queue.queue.channel_id
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id) # Caching work-around

            if not channel:
                logging.error(f"Channel {channel_id} not found.")
                raise ValueError(f"Channel {channel_id} not found.")
            
            if not isinstance(channel, discord.TextChannel):
                logging.error(f"Channel {channel_id} is not a text channel.")
                raise ValueError(f"Channel {channel_id} is not a text channel.")
            
            logging.info(f"Sending queue view to channel {channel_id} for queue {queue.queue.queue_id}.")
        
            # TODO - based on type, different queue views (2v2 should look different...)
            view = JoinQueueView(queue.queue.queue_id)
            
            self.views.append(view)

            embed = discord.Embed(title="Pending queue setup...")

            message = await channel.send(embed=embed, view=view)

            await view.start_task(message)

async def setup(bot: commands.Bot) -> None:
    queue_view_builder = QueueViewBuilder(bot)
    await bot.add_cog(queue_view_builder)

    await queue_view_builder.setup_queues()
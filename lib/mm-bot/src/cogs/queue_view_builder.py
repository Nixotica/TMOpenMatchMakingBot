import logging
from typing import List
import discord
from discord.ext import commands
from views.join_queue import JoinQueueView
from matchmaking.match_queues.matchmaking_manager import MatchmakingManager
from matchmaking.match_queues.active_match_queue import ActiveMatchQueue
from matchmaking.match_queues.enum import QueueType
from models.match_queue import MatchQueue
from cogs.constants import ROLE_ADMIN
from aws.dynamodb import DynamoDbManager

class QueueViewBuilder(commands.Cog):
    """ 
    Generates the queue views for each active queue. 
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ddb_manager = DynamoDbManager()
        self.mm_manager = MatchmakingManager()
        self.views: List[JoinQueueView] = []
    
    async def cog_load(self) -> None:
        logging.info("Queue View Builder loading...")
        await self.setup_queues()

    async def cog_unload(self) -> None:
        logging.info("Queue View Builder unloading...")
        for view in self.views:
            await view.stop_task()
            logging.info(f"Unloading view for Queue ID {view.queue_id}.")
        logging.info("All Queue Views have been unloadded.")

    async def add_active_queue_view(self, queue: ActiveMatchQueue) -> None:
            # If view is already setup, ignore (this will sometimes run multiple times on startup...)
            if any(view.queue_id == queue.queue.queue_id for view in self.views):
                return

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

    async def setup_queues(self) -> None:
        active_queues = self.mm_manager.active_queues

        for queue in active_queues:
            await self.add_active_queue_view(queue)

    @commands.hybrid_command(
        name="create_queue",
        description="Create a new matchmaking queue",
    )
    @commands.has_role(ROLE_ADMIN)
    async def create_queue(
        self, 
        ctx: commands.Context, 
        queue_id: str,
        campaign_club_id: int, 
        campaign_id: int,
        match_club_id: int,
        channel_id: str, # Cannot be int - too long for discord bot
        type: str,
    ) -> None:
        logging.info(f"Processing command to create queue {queue_id} from user {ctx.message.author.name}.")

        try:
            queue_type = QueueType.from_str(type)
        except ValueError:
            await ctx.send(f"Invalid queue type: {type}.")
            return
        
        channel_id = eval(channel_id)
        if not isinstance(channel_id, int):
            await ctx.send(f"Invalid channel ID: {channel_id}.")
            return

        queue = MatchQueue(
            queue_id=queue_id,
            campaign_club_id=campaign_club_id,
            campaign_id=campaign_id,
            match_club_id=match_club_id,
            channel_id=channel_id,
            type=queue_type,
            active=True,
            leaderboard_ids=[], # Currently requires admin to add leaderboards
        )

        # Add a new queue to the matchmaking manager to activate it
        active_queue = self.mm_manager.add_queue(queue)

        # Add the view to discord 
        await self.add_active_queue_view(active_queue)

        # Add to dynamo table so it will load automatically next time bot starts up
        success = self.ddb_manager.create_queue(queue=queue)

        if success:
            await ctx.send(f"Queue {queue_id} created successfully.")
        else: 
            await ctx.send(f"Failed to create queue {queue_id}, unknown error.")


    @commands.hybrid_command(
        name="add_queue_to_leaderboard",
        description="Add a queue to a leaderboard. Elo is shared among queues for a single leaderboard",
    )
    @commands.has_role(ROLE_ADMIN)
    async def add_queue_to_leaderboard(
        self,
        ctx: commands.Context,
        queue_id: str,
        leaderboard_id: str,
    ) -> None:
        logging.info(f"Processing command to add queue {queue_id} to leaderboard {leaderboard_id} from user {ctx.message.author.name}.")

        leaderboards = self.ddb_manager.get_leaderboards()
        if leaderboard_id not in [leaderboard.leaderboard_id for leaderboard in leaderboards]:
            await ctx.send(f"Leaderboard {leaderboard_id} not found.")
            return
        
        queues = self.ddb_manager.get_active_match_queues()
        if queue_id not in [queue.queue_id for queue in queues]:
            await ctx.send(f"Queue {queue_id} not found.")
            return
        
        # Update the ddb table
        self.ddb_manager.add_leaderboard_to_match_queue(queue_id, leaderboard_id)

        # Update the active match
        self.mm_manager.add_leaderboard_to_active_queue(queue_id, leaderboard_id)

        await ctx.send(f"Queue {queue_id} added to leaderboard {leaderboard_id}. Verify with /list_queues.")

    @commands.hybrid_command(
        name="list_queues",
        description="List all active matchmaking queues",
    )
    @commands.has_role(ROLE_ADMIN)
    async def list_queues(self, ctx: commands.Context) -> None:
        logging.info(f"Processing command to list queues from user {ctx.message.author.name}.")

        # Assume MM manager is up to date
        queues = self.mm_manager.active_queues

        if not queues:
            await ctx.send("No active queues found.")
            return

        embed = discord.Embed(title="Active Queues")

        for queue in queues:
            embed.add_field(name=queue.queue.queue_id, value=f"Channel ID: {queue.queue.channel_id}")

        await ctx.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    queue_view_builder = QueueViewBuilder(bot)
    await bot.add_cog(queue_view_builder)

    await queue_view_builder.setup_queues()
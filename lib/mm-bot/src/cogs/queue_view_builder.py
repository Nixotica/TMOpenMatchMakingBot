import logging
from typing import List
import discord
from discord.ext import commands
from views.join_queue import MatchQueueView
from matchmaking.match_queues.matchmaking_manager import MatchmakingManager
from matchmaking.match_queues.active_match_queue import ActiveMatchQueue
from matchmaking.match_queues.enum import QueueType
from models.match_queue import MatchQueue
from cogs.constants import ROLE_ADMIN, ROLE_MOD
from aws.dynamodb import DynamoDbManager


class QueueViewBuilder(commands.Cog):
    """
    Generates the queue views for each active queue.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ddb_manager = DynamoDbManager()
        self.mm_manager = MatchmakingManager()
        self.views: List[MatchQueueView] = []

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
        channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(
            channel_id
        )  # Caching work-around

        if not channel:
            logging.error(f"Channel {channel_id} not found.")
            raise ValueError(f"Channel {channel_id} not found.")

        if not isinstance(channel, discord.TextChannel):
            logging.error(f"Channel {channel_id} is not a text channel.")
            raise ValueError(f"Channel {channel_id} is not a text channel.")

        logging.info(
            f"Sending queue view to channel {channel_id} for queue {queue.queue.queue_id}."
        )

        # TODO - based on type, different queue views (2v2 should look different...)
        view = MatchQueueView(queue.queue.queue_id, channel)

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
    @commands.has_role(ROLE_MOD)
    async def create_queue(
        self,
        ctx: commands.Context,
        queue_id: str,
        display_name: str,
        campaign_club_id: int,
        campaign_id: int,
        match_club_id: int,
        channel_id: str,  # Cannot be int - too long for discord bot
        type: str,
    ) -> None:
        logging.info(
            f"Processing command to create queue {queue_id} from user {ctx.message.author.name}."
        )

        try:
            queue_type = QueueType.from_str(type)
        except ValueError:
            await ctx.send(f"Invalid queue type: {type}. Possible: {[q.value for q in QueueType]}", ephemeral=True)
            return

        channel_id = eval(channel_id)
        if not isinstance(channel_id, int):
            await ctx.send(f"Invalid channel ID: {channel_id}.", ephemeral=True)
            return

        queue = MatchQueue(
            queue_id=queue_id,
            campaign_club_id=campaign_club_id,
            campaign_id=campaign_id,
            match_club_id=match_club_id,
            channel_id=channel_id,
            type=queue_type,
            active=True,
            leaderboard_ids=[],  # Currently requires admin to add leaderboards
            primary_leaderboard_id=None,  # Currently requires admin to add primary leaderboard
            ping_role_id=None,  # Currently requires admin to add ping role
            display_name=display_name,
        )

        # Add to dynamo table so it will load automatically next time bot starts up
        success = self.ddb_manager.create_queue(queue=queue)

        if success:
            await ctx.send(f"Queue {queue_id} created successfully.")
        else:
            await ctx.send(f"Failed to create queue {queue_id}, unknown error.")
            return

        # Add a new queue to the matchmaking manager to activate it
        active_queue = self.mm_manager.add_queue(queue)

        # Add the view to discord
        await self.add_active_queue_view(active_queue)

    @commands.hybrid_command(
        name="add_queue_to_leaderboard",
        description="Add a queue to a leaderboard. Elo is shared among queues for a single leaderboard",
    )
    @commands.has_role(ROLE_MOD)
    async def add_queue_to_leaderboard(
        self,
        ctx: commands.Context,
        queue_id: str,
        leaderboard_id: str,
    ) -> None:
        logging.info(
            f"Processing command to add queue {queue_id} to leaderboard {leaderboard_id} from user {ctx.message.author.name}."
        )

        # TODO - this is making pointless scans on dynamo
        leaderboards = self.ddb_manager.get_leaderboards()
        if leaderboard_id not in [
            leaderboard.leaderboard_id for leaderboard in leaderboards
        ]:
            await ctx.send(f"Leaderboard {leaderboard_id} not found.", ephemeral=True)
            return

        queues = self.ddb_manager.get_active_match_queues()
        if queue_id not in [queue.queue_id for queue in queues]:
            await ctx.send(f"Queue {queue_id} not found.", ephemeral=True)
            return

        # Update the ddb table
        self.ddb_manager.add_leaderboard_to_match_queue(queue_id, leaderboard_id)

        # Update the active match
        self.mm_manager.add_leaderboard_to_active_queue(queue_id, leaderboard_id)

        await ctx.send(
            f"Queue {queue_id} added to leaderboard {leaderboard_id}. Verify with /list_queues.",
            ephemeral=True,
        )

    @commands.hybrid_command(
        name="list_queues",
        description="List all active matchmaking queues",
    )
    @commands.has_role(ROLE_MOD)
    async def list_queues(self, ctx: commands.Context) -> None:
        logging.info(
            f"Processing command to list queues from user {ctx.message.author.name}."
        )

        # Assume MM manager is up to date
        queues = self.mm_manager.active_queues

        if not queues:
            await ctx.send("No active queues found.")
            return

        embed = discord.Embed(title="Active Queues")

        for queue in queues:
            value = f"Channel ID: {queue.queue.channel_id}\n"
            value += f"Display Name: {queue.queue.display_name if queue.queue.display_name else queue.queue.queue_id}\n"
            value += f"Campaign Link: https://trackmania.io/#/campaigns/{queue.queue.campaign_club_id}/{queue.queue.campaign_id}\n"

            embed.add_field(
                name=queue.queue.queue_id, value=value, inline=False,
            )

        await ctx.send(embed=embed, ephemeral=True)


    @commands.hybrid_command(
        name="link_ping_role_to_queue",
        description="Link a role to a queue used for general pings like players activating the queue."
    )
    @commands.has_role(ROLE_ADMIN)
    async def link_ping_role_to_queue(self, ctx: commands.Context, queue_id: str, role: discord.Role) -> None:
        logging.info(
            f"Processing command to link ping role {role.name} to queue {queue_id} from user {ctx.message.author.name}."
        )

        # Check if the queue exists
        queue = self.ddb_manager.get_match_queue(queue_id)
        if not queue:
            await ctx.send(f"Queue {queue_id} not found. Use /list_queues to check which ones exist.", ephemeral=True)
            return
        
        queue.ping_role_id = role.id

        # Update the ddb table
        self.ddb_manager.update_match_queue(queue)

        # Update the active match
        active_queue = self.mm_manager.get_active_queue_by_id(queue.queue_id)
        if active_queue:
            active_queue.queue.ping_role_id = role.id

        await ctx.send(f"Role {role.name} linked to queue {queue_id}.", ephemeral=True)

    
    @commands.hybrid_command(
        name="set_queue_primary_leaderboard",
        description="Set the primary leaderboard for a queue, used when displaying rank counts in queue."
    )
    @commands.has_role(ROLE_MOD)
    async def set_primary_leaderboard_for_queue(self, ctx: commands.Context, queue_id: str, leaderboard_id: str) -> None:
        logging.info(
            f"Processing command to set primary leaderboard {leaderboard_id} for queue {queue_id} from user {ctx.message.author.name}."
        )
        
        # Check if the queue exists
        queue = self.ddb_manager.get_match_queue(queue_id)
        if not queue:
            await ctx.send(f"Queue {queue_id} not found. Use /list_queues to check which ones exist.")
            return
        
        # TODO - this is making pointless scans on dynamo
        leaderboards = self.ddb_manager.get_leaderboards()
        if leaderboard_id not in [
            leaderboard.leaderboard_id for leaderboard in leaderboards
        ]:
            await ctx.send(f"Leaderboard {leaderboard_id} not found.", ephemeral=True)
            return
        
        queue.primary_leaderboard_id = leaderboard_id
        self.ddb_manager.update_match_queue(queue)

        # Also update it in the matchmaking manager
        active_queue = self.mm_manager.get_active_queue_by_id(queue.queue_id)

        if active_queue is not None:
            active_queue.queue.primary_leaderboard_id = leaderboard_id

        await ctx.send(f"Primary leaderboard for queue {queue_id} set to {leaderboard_id}.", ephemeral=True)


    @commands.hybrid_command(
        name="rename_queue",
        description="Rename a queue by giving it a new display field."
    )
    @commands.has_role(ROLE_MOD)
    async def rename_queue(self, ctx: commands.Context, queue_id: str, new_name: str) -> None:
        logging.info(
            f"Processing command to rename queue {queue_id} to {new_name} from user {ctx.message.author.name}."
        )

        # Check if the queue exists
        queue = self.ddb_manager.get_match_queue(queue_id)

        if not queue:
            await ctx.send(f"Queue {queue_id} not found. Use /list_queues to check which ones exist.", ephemeral=True)
            return
        
        # Update the queue in dynamo
        queue.display_name = new_name
        self.ddb_manager.update_match_queue(queue)

        # Update the queue in the bot
        active_queue = self.mm_manager.get_active_queue_by_id(queue.queue_id)

        if not active_queue:
            logging.warning(
                f"Queue {queue_id} not found in active queues while renaming."
            )
        else:
            active_queue.queue.display_name = new_name

        await ctx.send(f"Queue {queue_id} renamed to {new_name}.", ephemeral=True)


    @commands.hybrid_command(
        name="edit_queue_maps",
        description="Edit the maps used for a queue."
    )
    @commands.has_role(ROLE_MOD)
    async def edit_queue_maps(
        self, 
        ctx: commands.Context, 
        queue_id: str, 
        club_id: int, 
        campaign_id: int, 
    ) -> None:
        logging.info(
            f"Processing command to edit maps for queue {queue_id} from user {ctx.message.author.name}."
        )

        # Check if the queue exists
        queue = self.ddb_manager.get_match_queue(queue_id)

        if not queue:
            await ctx.send(f"Queue {queue_id} not found. Use /list_queues to check which ones exist.", ephemeral=True)
            return
        
        # Update the queue in dynamo
        queue.campaign_id = campaign_id
        queue.campaign_club_id = club_id
        self.ddb_manager.update_match_queue(queue)

        # Update the queue in the bot
        active_queue = self.mm_manager.get_active_queue_by_id(queue.queue_id)

        if not active_queue:
            logging.warning(
                f"Queue {queue_id} not found in active queues while editing maps."
            )
        else:
            active_queue.queue.campaign_id = campaign_id
            active_queue.queue.campaign_club_id = club_id

        await ctx.send(f"Queue {queue_id} maps updated to campaign {campaign_id} and club {club_id}.", ephemeral=True)


    @commands.hybrid_command(
        name="disable_queue",
        description="Disable a queue so it can no longer be joined nor shows up in its channel."
    )
    @commands.has_role(ROLE_MOD)
    async def disable_queue(self, ctx: commands.Context, queue_id: str) -> None:
        logging.info(
            f"Processing command to disable queue {queue_id} from user {ctx.message.author.name}."
        )

        # Check if the queue exists
        queue = self.ddb_manager.get_match_queue(queue_id)

        if not queue:
            await ctx.send(f"Queue {queue_id} not found. Use /list_queues to check which ones exist.", ephemeral=True)
            return

        # Update the queue in dynamo
        queue.active = False
        self.ddb_manager.update_match_queue(queue)

        # Remove the queue from the mm manager
        removed = self.mm_manager.remove_queue(queue.queue_id)

        if not removed:
            logging.warning(
                f"Queue {queue_id} not found in active queues while disabling."
            )

        # Stop the queue view task and remove it 
        for view in self.views:
            if view.queue_id == queue_id:
                await view.stop_task()
                self.views.remove(view)
                break

        await ctx.send(f"Queue {queue_id} disabled.", ephemeral=True)


    @commands.hybrid_command(
        name="reenable_queue",
        description="Re-enable an existing queue to make it appear in its channel and becoming joinable."
    )
    @commands.has_role(ROLE_MOD)
    async def reenable_queue(self, ctx: commands.Context, queue_id: str) -> None:
        logging.info(
            f"Processing command to re-enable queue {queue_id} from user {ctx.message.author.name}."
        )

        # Check if the queue exists
        queue = self.ddb_manager.get_match_queue(queue_id)

        if not queue:
            await ctx.send(f"Queue {queue_id} not found. Use /list_queues to check which ones exist or use /create_queue to make a new one.", ephemeral=True)
            return
        
        # Update the queue in dynamo
        queue.active = True
        self.ddb_manager.update_match_queue(queue)

        # Add the queue to the mm manager
        active_queue = self.mm_manager.add_queue(queue)

        # Add the queue view to discord
        await self.add_active_queue_view(active_queue)

        await ctx.send(f"Queue {queue_id} re-enabled.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    queue_view_builder = QueueViewBuilder(bot)
    await bot.add_cog(queue_view_builder)

    await queue_view_builder.setup_queues()

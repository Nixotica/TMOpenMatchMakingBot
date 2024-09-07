import logging
from discord.ext import commands
from matchmaking.match_queues.matchmaking_manager import MatchmakingManager
from aws.dynamodb import DynamoDbManager

class JoinQueue(commands.Cog, name="join"):
    """
    Command for a player to join a matchmaking queue. 
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mm_manager = MatchmakingManager()
        self.ddb_manager = DynamoDbManager()

    @commands.hybrid_command(
        name="join",
        description="Join a queue for matchmaking."
    )
    async def join(self, ctx: commands.Context, queue_id: str) -> None: 
        logging.info(f"Processing command to join queue {queue_id} for user {ctx.message.author.name}.")

        player_profile = DynamoDbManager().query_player_profile_for_discord_account_id(ctx.message.author.id)

        added_queue = self.mm_manager.add_player_to_queue(player_profile, queue_id) # type: ignore

        if not added_queue:
            await ctx.send(f"Failed to join queue {queue_id}.")
            return
        await ctx.send(f"Joined queue {queue_id} along with {len(added_queue.players) - 1} others.")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(JoinQueue(bot))
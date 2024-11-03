import logging
from discord.ext import commands

from aws.dynamodb import DynamoDbManager
from aws.s3 import S3ClientManager


class Roles(commands.Cog, name="roles"):
    """
    Commands and management for creating and managing user roles.
    Includes the process of updating elo-based ranks.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ddb_manager = DynamoDbManager()
        self.s3_manager = S3ClientManager()

    @commands.hybrid_command(
        name="create_rank_role",
        description="Create a role associated with an elo on the 'global' leaderboard.",
    )
    async def create_rank_role(
        self, ctx: commands.Context, role_name: str, min_elo: int
    ) -> None:
        logging.info(
            f"Processing command to create rank role {role_name} from user {ctx.message.author.name}"
        )

        # TODO
        await ctx.send("This command is not yet implemented.")

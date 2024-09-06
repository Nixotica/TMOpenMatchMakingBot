import logging

from discord.ext import commands
from aws.dynamodb import DynamoDbManager


class Register(commands.Cog, name="register"):
    """
    Command for a player to register their Ubisoft account to their
    Discord account.

    Currently it does not do any auth flow, so malicious users could attempt
    to take another person's account. For now, it will be manually enforced.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ddb_manager = DynamoDbManager()

    @commands.hybrid_command(
        name="register",
        description="Register your Trackmania account ID to your Discord account. You can find it on trackmania.io",
    )
    async def register(self, ctx: commands.Context, tm_account_id: str) -> None:
        logging.info(f"Processing command to register TM account {tm_account_id} to user {ctx.message.author.name} with id {ctx.message.author.id}.")
        # TODO check that the requested account ID actually exists via TM API

        existing_player_profile = self.ddb_manager.query_player_profile_for_tm_account_id(tm_account_id)
        
        if existing_player_profile is not None:
            await ctx.send(f"Account {tm_account_id} is already registered to a Discord account.")
            return
        
        success = self.ddb_manager.create_player_profile_for_tm_account_id(tm_account_id, ctx.message.author.id)
        if success:
            await ctx.send(f"Account {tm_account_id} has been registered to your Discord account.")
        else:
            await ctx.send(f"Failed to register account {tm_account_id} to your Discord account.")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Register(bot))

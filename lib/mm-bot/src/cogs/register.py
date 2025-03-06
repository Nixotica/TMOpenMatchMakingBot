import logging
import re

from aws.dynamodb import DynamoDbManager
from discord.ext import commands


class Register(commands.Cog):
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
        logging.info(
            f"Processing command to register TM account {tm_account_id} to user "
            f"{ctx.message.author.name} with id {ctx.message.author.id}."
        )
        UUID_REGEX = re.compile(
            r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$", re.I
        )
        if not bool(UUID_REGEX.match(tm_account_id)):
            await ctx.send(
                f"Invalid Trackmania account ID: {tm_account_id}. Must be a UUID."
            )
            return

        existing_tm_account_link = (
            self.ddb_manager.query_player_profile_for_tm_account_id(tm_account_id)
        )
        existing_discord_account_link = (
            self.ddb_manager.query_player_profile_for_discord_account_id(
                ctx.message.author.id
            )
        )

        if existing_tm_account_link is not None:
            await ctx.send(
                f"Account {tm_account_id} is already registered to a Discord account: "
                f"<@{existing_tm_account_link.discord_account_id}>."
            )
            return
        if existing_discord_account_link is not None:
            await ctx.send(
                f"Your Discord account is already registered to a Trackmania account: "
                f"{existing_discord_account_link.tm_account_id}."
            )
            return

        success = self.ddb_manager.create_player_profile_for_tm_account_id(
            tm_account_id, ctx.message.author.id
        )
        if success:
            await ctx.send(
                f"Account {tm_account_id} has been registered to your Discord account."
            )
        else:
            await ctx.send(
                f"Failed to register account {tm_account_id} to your Discord account."
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Register(bot))

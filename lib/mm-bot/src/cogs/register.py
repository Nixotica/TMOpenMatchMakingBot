import logging

from discord.ext import commands


class Register(commands.Cog, name="register"):
    """
    Command for a player to register their Ubisoft account to their
    Discord account.

    Currently it does not do any auth flow, so malicious users could attempt
    to take another person's account. For now, it will be manually enforced.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="register",
        description="Register your Trackmania account ID to your Discord account. You can find it on trackmania.io",
    )
    async def register(self, ctx: commands.Context, tm_account_id: str) -> None:
        # TODO - verify account ID exists and doesn't exist in DDB, then add to table
        await ctx.send(f"Register called with: {tm_account_id}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Register(bot))

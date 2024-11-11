from datetime import datetime
import logging
import discord
from discord.ext import commands

from aws.s3 import S3ClientManager
from cogs.constants import COLOR_EMBED, ROLE_ADMIN


class General(commands.Cog, name="general"):
    """ 
    General bot commands for managing configs and discord integration.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.s3_manager = S3ClientManager()

    @commands.hybrid_command(
        name="ping",
        description="Check if the bot is alive by seeing a response in the bot messages channel."
    )
    @commands.has_role(ROLE_ADMIN)
    async def ping(self, ctx: commands.Context) -> None:
        logging.info(
            f"Processing command to ping from user {ctx.message.author.name}."
        )

        configs = self.s3_manager.get_configs()
        if configs.bot_messages_channel_id is None:
            await ctx.send("Bot messages channel not set. But PONG anyway!")
            return

        ping_channel = self.bot.get_channel(configs.bot_messages_channel_id) 

        pong_embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())
        pong_embed.add_field(name="⚠️", value="Pong!", inline=True)

        await ping_channel.send(embed=pong_embed) # type: ignore
        await ctx.send("Pinged the bot messages channel.", ephemeral=True)

    @commands.hybrid_command(
        name="set_bot_messages_channel",
        description="Set the channel for bot messages",
    )
    @commands.has_role(ROLE_ADMIN)
    async def set_bot_messages_channel(
        self, ctx: commands.Context, channel_id: str # Cannot be int - too long for discord bot
    ) -> None:
        logging.info(
            f"Processing command to set bot messages channel from user {ctx.message.author.name}."
        )

        channel_id = eval(channel_id)
        if not isinstance(channel_id, int):
            await ctx.send(f"Invalid channel ID: {channel_id}.")
            return

        configs = self.s3_manager.get_configs()
        configs.bot_messages_channel_id = channel_id
        self.s3_manager.update_config(configs)

        await ctx.send(f"Bot messages channel set to {channel_id}.")
        
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
from discord import Intents
from discord.ext import commands
from aws.s3 import S3

s3 = S3()
secrets = s3.get_secrets()

bot = commands.Bot(command_prefix="/", intents=Intents.all())


@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("Pong!")


bot.run(secrets.discord_bot_token)

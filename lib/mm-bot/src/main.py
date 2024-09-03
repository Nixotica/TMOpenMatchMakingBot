import logging
import os
import platform
from typing import Any, Dict

import discord
from aws.s3 import S3ClientManager
from discord import Intents
from discord.ext.commands import Bot
from models.bot_secrets import Secrets

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Retrieve secrets from S3
secrets: Secrets = S3ClientManager().get_secrets()


# Define bot
class DiscordBot(Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix="/",
            intents=Intents.all(),
        )

    async def load_cogs(self) -> None:
        """
        Loads all cogs in this package.
        """
        for file in os.listdir(f"{os.path.realpath(os.path.dirname(__file__))}/cogs"):
            if file.endswith(".py") and "__init__" not in file:
                extension = file[:-3]
                try:
                    await self.load_extension(f"cogs.{extension}")
                    logging.info(f"Loaded extension '{extension}'")
                except Exception as e:
                    exception = f"{type(e).__name__}: {e}"
                    logging.error(f"Failed to load extension {extension}\n{exception}")

    async def setup_hook(self) -> None:
        """
        Executed when the bot starts for first time.
        """
        logging.info(f"Logged in as {self.user.name}")  # type: ignore
        logging.info(f"discord.py API version: {discord.__version__}")
        logging.info(f"Python version: {platform.python_version()}")
        logging.info(
            f"Running on: {platform.system()} {platform.release()} ({os.name})"
        )
        logging.info("-------------------")

        await self.load_cogs()
        await self.tree.sync()


# Set up and run bot
bot = DiscordBot()
bot.run(secrets.discord_bot_token)

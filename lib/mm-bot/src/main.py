import asyncio
from importlib.util import spec_from_file_location, module_from_spec
import logging
import os
import platform
import signal
from typing import Any, Dict

import discord
from aws.s3 import S3ClientManager
from aws.dynamodb import DynamoDbManager
from discord import Intents
from discord.ext.commands import Bot
from health_check import start_health_check_in_thread
from models.bot_secrets import Secrets
from matchmaking.match_queues.matchmaking_manager import MatchmakingManager


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

    async def shutdown(self):
        """Gracefully shutdown the bot."""
        logging.info("Shutting down bot gracefully...")
        await self.close()

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

        # Register signal handlers for SIGINT and SIGTERM to gracefully shutdown
        loop = asyncio.get_running_loop()
        for signal_type in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                signal_type, lambda: asyncio.create_task(self.shutdown())
            )

    async def start_bot(self, token: str):
        """Run the bot with the given token."""
        await self.start(token)


# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def main():
    # Set up health checks and run (don't do for now)
    start_health_check_in_thread()

    # Retrieve secrets from S3
    secrets: Secrets = S3ClientManager().get_secrets()

    # Set up the matchmaking manager and run
    MatchmakingManager().start_run_forever_in_thread()

    # Set up and run bot
    bot = DiscordBot()

    try:
        await bot.start_bot(secrets.discord_bot_token)
    except KeyboardInterrupt:
        logging.warn("Bot interrupted by keyboard, shutting down...")
    except Exception as e:
        logging.error(f"Got excepting during bot runtime {e}")

    await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

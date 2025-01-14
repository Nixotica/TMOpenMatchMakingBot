import asyncio
from datetime import datetime, timedelta
import logging
import threading
from typing import Dict, List, Optional

import discord
from discord.ext import commands
from aws.s3 import S3ClientManager
from helpers import get_ping_channel
from matchmaking.party.active_party import ActiveParty
from matchmaking.party.constants import PARTY_MANAGER_CHECK_STALE_PARTY_REQUESTS_SEC


class PartyManager:
    """
    The backbone of handling ongoing party request messages and active parties. 
    """

    _instance = None

    def __new__(cls, bot: Optional[commands.Bot] = None):
        if not cls._instance:
            cls._instance = super(PartyManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, bot: Optional[commands.Bot] = None):
        if not hasattr(self, "_initialized"):  # Avoid re-initializing the instance
            self._initialized = True
            
            self.bot = bot
            self.s3_manager = S3ClientManager()

            self.active_parties: List[ActiveParty] = []

            # Represented as an "active" party for which this message will party the two players.
            self.outstanding_party_request_messages: Dict[ActiveParty, discord.message.Message] = {} 

            logging.info(
                f"Instantiating party manager."
            )
        elif bot and not self.bot:
            # Handle the case where this may have been called by a dependency before the bot was passed in
            self.bot = bot

    def add_outstanding_party_request(self, active_party: ActiveParty, message: discord.message.Message) -> None:
        self.outstanding_party_request_messages[active_party] = message

        # TODO Monitor the message for reaction to see if accepted or rejected 

    async def _run_forever(self):
        """Run the party manager forever."""
        while True:
            logging.debug(f"Running Party Manager loop...")
            await self._check_for_stale_party_requests()
            await asyncio.sleep(5)

    def start_run_forever_in_thread(self):
        """Starts the run_forever method in a separate thread with its own event loop."""
        logging.info("Starting party manager in a separate thread...")
        self._thread = threading.Thread(target=self._start_event_loop, daemon=True)
        self._thread.start()

    def _start_event_loop(self):
        """Starts an event loop in the curren thread to run async methods."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._run_forever())
        loop.run_forever()

    async def _check_for_stale_party_requests(self):
        now = datetime.utcnow()
        
        for active_party, message in self.outstanding_party_request_messages.items():
            if now - timedelta(seconds=PARTY_MANAGER_CHECK_STALE_PARTY_REQUESTS_SEC) > message.created_at:
                logging.info(f"Party request for {active_party} is stale. Removing...")
                await message.delete()
                self.outstanding_party_request_messages.pop(active_party)

                if not self.bot:
                    logging.error("Bot is not initialized in party manager. Skipping pinging stale party request.")
                    continue

                ping_channel = get_ping_channel(self.bot, self.s3_manager)

                if ping_channel:
                    await ping_channel.send(
                        f"❗ <@{active_party.requester.discord_account_id}, <@{active_party.accepter.discord_account_id} did not respond to your invite in time."
                    )

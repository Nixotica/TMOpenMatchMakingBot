import asyncio
from datetime import datetime, timedelta, timezone
import logging
import threading
from typing import Dict, List, Optional

import discord
from discord import ui
from discord.ext import commands
from aws.s3 import S3ClientManager
from helpers import get_party_channel, get_ping_channel
from matchmaking.party.active_party import ActiveParty
from matchmaking.party.constants import PARTY_MANAGER_CHECK_STALE_PARTY_REQUESTS_SEC
from matchmaking.party.party_request import PartyRequest
from matchmaking.party.request_status import PartyRequestStatus
from models.player_profile import PlayerProfile
from views.party_request import PartyRequestView


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
            self.outstanding_party_request_messages: Dict[ActiveParty, PartyRequest] = {} 

            logging.info(
                f"Instantiating party manager."
            )
        elif bot and not self.bot:
            # Handle the case where this may have been called by a dependency before the bot was passed in
            self.bot = bot

    async def add_outstanding_party_request(self, requester: PlayerProfile, accepter: PlayerProfile) -> None:
        active_party = ActiveParty(requester, accepter)

        view = PartyRequestView(active_party)

        if not self.bot:
            logging.error("Bot is not initialized in party manager. Skipping sending party request.")
            return
        
        party_channel = await get_party_channel(self.bot, self.s3_manager)
        if not party_channel:
            logging.error("Party channel not found. Skipping sending party request.")
            return
        
        message = await party_channel.send(
            content=f"❗ <@{accepter.discord_account_id}>, <@{requester.discord_account_id}> has invited you to a party!",
            view=view,
        )
        
        logging.info(f"Party request sent for {active_party}.")

        self.outstanding_party_request_messages[active_party] = PartyRequest(message, view)

    def get_player_party(self, player: PlayerProfile) -> Optional[ActiveParty]:
        """Get the active party that the player is in.

        Args:
            player (PlayerProfile): The player to check.

        Returns:
            Optional[ActiveParty]: The active party that the player is in, or None if the player is not in a party.
        """
        for active_party in self.active_parties:
            if player in active_party:
                return active_party

        return None
    
    def remove_party(self, requester: PlayerProfile) -> Optional[ActiveParty]:
        """Removes a party from the active parties list given a requester as a member of that party.

        Args:
            requester (PlayerProfile): The requester to remove the party (can be either member).

        Returns:
            Optional[ActiveParty]: The active party removed if existed, None otherwise.
        """
        for active_party in self.active_parties:
            if requester in active_party:
                self.active_parties.remove(active_party)
                return active_party

        return None

    async def _run_forever(self):
        """Run the party manager forever."""
        while True:
            logging.debug(f"Running Party Manager loop...")
            await self._check_for_stale_party_requests()
            await self._check_party_requests_status()
            await asyncio.sleep(1)

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

    async def _check_party_requests_status(self):
        outstanding_party_request_messages_copy = self.outstanding_party_request_messages.copy()
        for active_party, party_request in outstanding_party_request_messages_copy.items():
            status = party_request.view.status

            if status == PartyRequestStatus.ACCEPTED:
                logging.info(f"Party request for {active_party} has been accepted.")

                self.active_parties.append(active_party)
                self.outstanding_party_request_messages.pop(active_party)

            if status == PartyRequestStatus.REJECTED:
                logging.info(f"Party request for {active_party} has been rejected.")

                self.outstanding_party_request_messages.pop(active_party)

    async def _check_for_stale_party_requests(self):
        now = datetime.now(timezone.utc)
        
        for active_party, party_request in self.outstanding_party_request_messages.items():
            if now - timedelta(seconds=PARTY_MANAGER_CHECK_STALE_PARTY_REQUESTS_SEC) > party_request.message.created_at:
                logging.info(f"Party request for {active_party} is stale. Removing...")
                await party_request.message.delete()
                self.outstanding_party_request_messages.pop(active_party)

                if not self.bot:
                    logging.error("Bot is not initialized in party manager. Skipping pinging stale party request.")
                    continue

                ping_channel = get_ping_channel(self.bot, self.s3_manager)

                if ping_channel:
                    await ping_channel.send(
                        f"❗ <@{active_party.requester.discord_account_id}, <@{active_party.accepter.discord_account_id} did not respond to your invite in time."
                    )

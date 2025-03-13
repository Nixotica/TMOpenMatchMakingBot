import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import discord
from aws.s3 import S3ClientManager
from cogs import registry
from cogs.constants import COG_PARTY_MANAGER, COLOR_EMBED
from discord.ext import commands, tasks
from helpers import get_party_channel, safe_delete_message
from matchmaking.party.active_party import ActiveParty
from matchmaking.party.constants import (
    PARTY_MANAGER_ACTIVE_PARTY_EXPIRATION_SEC,
    PARTY_MANAGER_CHECK_STALE_PARTY_REQUESTS_SEC,
)
from matchmaking.party.party_request import PartyRequest
from matchmaking.party.request_status import PartyRequestStatus
from models.player_profile import PlayerProfile
from views.party_request import PartyRequestView


class PartyManager(commands.Cog):
    """
    The backbone of handling ongoing party request messages and active parties.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.s3_manager = S3ClientManager()

        self.active_parties: List[ActiveParty] = []

        # Represented as an "active" party for which this message will party the two players.
        self.outstanding_party_request_messages: Dict[ActiveParty, PartyRequest] = {}

        registry.register_cog(COG_PARTY_MANAGER, self)

    def cog_load(self):
        logging.info("Party Manager loading...")
        self.check_party_requests_status.start()
        self.check_for_stale_party_requests.start()
        self.check_inactive_parties_to_disband.start()

    def cog_unload(self):
        logging.info("Party manager unloading...")
        self.check_party_requests_status.cancel()
        self.check_for_stale_party_requests.cancel()
        self.check_inactive_parties_to_disband.cancel()

    async def add_outstanding_party_request(
        self, requester: PlayerProfile, accepter: PlayerProfile
    ) -> None:
        active_party = ActiveParty(requester, accepter)

        view = PartyRequestView(active_party)

        if not self.bot:
            logging.error(
                "Bot is not initialized in party manager. Skipping sending party request."
            )
            return

        party_channel = await get_party_channel(self.bot, self.s3_manager)
        if not party_channel:
            logging.error("Party channel not found. Skipping sending party request.")
            return

        embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())
        embed.add_field(
            name="❗ Party System",
            value=f"<@{accepter.discord_account_id}>, <@{requester.discord_account_id}> has invited you to a party!",
        )
        message = await party_channel.send(
            content=f"<@{accepter.discord_account_id}>",
            embed=embed,
            view=view,
        )

        logging.info(f"Party request sent for {active_party}.")

        self.outstanding_party_request_messages[active_party] = PartyRequest(
            message, view
        )

    def update_party_activity(self, party: ActiveParty) -> None:
        """Updates the party activity such that it pushes back the party disband expiration.

        Args:
            party (ActiveParty): The party to update as active.
        """
        now = datetime.utcnow()
        logging.debug(f"Updating party {party} activity to now ({now})")
        party.last_activity_time = now

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

    @tasks.loop(seconds=1)
    async def check_party_requests_status(self):
        outstanding_party_request_messages_copy = (
            self.outstanding_party_request_messages.copy()
        )
        for (
            active_party,
            party_request,
        ) in outstanding_party_request_messages_copy.items():
            status = party_request.view.status

            if status == PartyRequestStatus.ACCEPTED:
                logging.info(f"Party request for {active_party} has been accepted.")

                self.active_parties.append(active_party)
                self.outstanding_party_request_messages.pop(active_party)

            if status == PartyRequestStatus.REJECTED:
                logging.info(f"Party request for {active_party} has been rejected.")

                self.outstanding_party_request_messages.pop(active_party)

    @tasks.loop(seconds=1)
    async def check_for_stale_party_requests(self):
        now = datetime.now(timezone.utc)

        outstanding_party_request_messages_copy = (
            self.outstanding_party_request_messages.copy()
        )
        for (
            active_party,
            party_request,
        ) in outstanding_party_request_messages_copy.items():
            if (
                now - timedelta(seconds=PARTY_MANAGER_CHECK_STALE_PARTY_REQUESTS_SEC)
                > party_request.message.created_at
            ):
                logging.info(f"Party request for {active_party} is stale. Removing...")

                await safe_delete_message(party_request.message)

                self.outstanding_party_request_messages.pop(active_party)

                party_channel = await get_party_channel(self.bot, self.s3_manager)

                if party_channel:
                    embed = discord.Embed(
                        color=COLOR_EMBED, timestamp=datetime.utcnow()
                    )
                    embed.add_field(
                        name="❗ Party System",
                        value=f"<@{active_party.accepter.discord_account_id}> did not respond to your invite in time.",
                    )

                    await party_channel.send(
                        content=f"<@{active_party.requester.discord_account_id}>",
                        embed=embed,
                    )

    @tasks.loop(seconds=1)
    async def check_inactive_parties_to_disband(self):
        now = datetime.utcnow()

        active_parties_copy = self.active_parties.copy()
        for party in active_parties_copy:
            if (
                now - timedelta(seconds=PARTY_MANAGER_ACTIVE_PARTY_EXPIRATION_SEC)
                > party.last_activity_time
            ):
                logging.info(f"Party {party} is inactive. Disbanding...")

                self.active_parties.remove(party)

                party_channel = await get_party_channel(self.bot, self.s3_manager)

                if party_channel:
                    embed = discord.Embed(
                        color=COLOR_EMBED, timestamp=datetime.utcnow()
                    )
                    embed.add_field(
                        name="❗ Party System",
                        value="Your party was detected as inactive and disbanded. "
                        "Use /party again if you want to play with a party again!",
                    )

                    await party_channel.send(
                        content=f"<@{party.requester.discord_account_id}> <@{party.accepter.discord_account_id}>",
                        embed=embed,
                    )

    @check_for_stale_party_requests.before_loop
    @check_for_stale_party_requests.before_loop
    @check_inactive_parties_to_disband.before_loop
    async def before_checks(self):
        """Wait until the bot is ready before starting the loop."""
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(PartyManager(bot))


def get_party_manager() -> Optional[PartyManager]:
    """Gets party manager singleton if initialized, else returns None."""
    return registry.get(COG_PARTY_MANAGER)

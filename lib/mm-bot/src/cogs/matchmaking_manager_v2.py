import logging
from typing import List
from discord.ext import commands

from aws.dynamodb import DynamoDbManager
from aws.s3 import S3ClientManager
from cogs import registry
from cogs.constants import COG_MATCHMAKING_MANAGER_V2
from matchmaking.match_queues.active_match_queue import ActiveMatchQueue
from matchmaking.match_queues.match_persistence import get_persisted_matches
from matchmaking.matches.active_match import ActiveMatch
from models.match_queue import MatchQueue
from models.player_profile import PlayerProfile


class MatchmakingManagerV2(commands.Cog):
    """
    The backbone of handling queueing, monitoring, and finishing matches.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.s3_manager = S3ClientManager()
        self.ddb_manager = DynamoDbManager()

        # Populate active queues to manage
        self.active_queues: List[ActiveMatchQueue] = []
        match_queues = self.ddb_manager.get_active_match_queues()
        logging.info(
            f"Instantiating matchmaking manager v2 with {len(match_queues)} active match queues."
        )
        for queue in match_queues:
            self.active_queues.append(ActiveMatchQueue(queue))

        # Retreive persisted matches from previous bot instance if exists
        persisted_matches = get_persisted_matches()
        logging.info(
            f"Instantiating matchmaking manager v2 with {len(persisted_matches)} persisted matches."
        )
        self.active_matches: List[ActiveMatch] = persisted_matches

        registry.register_cog(COG_MATCHMAKING_MANAGER_V2, self)

    def cog_load(self):
        logging.info("Matchmaking Manager V2 loading...")

        # TODO - start tasks

    def cog_unload(self):
        logging.info("Matchmaking Manager V2 unloading...")

        # TODO - cancel tasks

    def add_queue(self, queue: MatchQueue) -> ActiveMatchQueue:
        """Adds a new active queue to the Matchmaking manager.

        Args:
            queue (MatchQueue): The queue to add and activate.

        Returns:
            ActiveMatchQueue: ActiveMatchQueue generated from this call.
        """
        active_queue = ActiveMatchQueue(queue)
        self.active_queues.append(active_queue)
        return active_queue

    def remove_queue(self, queue_id: str) -> bool:
        """Removes an active queue from the Matchmaking manager.
        If the bot reloads and the queue is "active" in DDB, it will re-activate.

        Args:
            queue_id (str): The queue to remove and deactivate.

        Returns:
            bool: True if the queue was found and removed, False if not found.
        """
        for queue in self.active_queues:
            if queue.queue.queue_id == queue_id:
                self.active_queues.remove(queue)
                return True

        return False

    def is_player_in_match(self, player: PlayerProfile) -> bool:
        """Checks if a player is in an active match.

        Args:
            player (PlayerProfile): The player to check.

        Returns:
            bool: True if player is in an active match, False otherwise.
        """
        for match in self.active_matches:
            if match.has_player(player):
                return True

        return False


async def setup(bot: commands.Bot):
    await bot.add_cog(MatchmakingManagerV2(bot))


def get_matchmaking_manager_v2():
    """Gets matchmaking manager singleton if initialized, else returns None."""
    return registry.get(COG_MATCHMAKING_MANAGER_V2)

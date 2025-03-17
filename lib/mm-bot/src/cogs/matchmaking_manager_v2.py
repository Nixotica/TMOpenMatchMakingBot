import logging
from typing import List, Optional
from discord.ext import commands, tasks

from aws.dynamodb import DynamoDbManager
from aws.s3 import S3ClientManager
from cogs import registry
from cogs.constants import COG_MATCHMAKING_MANAGER_V2
from matchmaking.match_queues.active_match_queue import ActiveMatchQueue
from matchmaking.match_queues.match_persistence import (
    get_persisted_matches,
    persist_match,
)
from matchmaking.matches.active_match import ActiveMatch
from matchmaking.matches.completed_match import CompletedMatch
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

        # TODO MMv2 - start tasks
        self.check_queues_to_spawn_new_match.start()

    def cog_unload(self):
        logging.info("Matchmaking Manager V2 unloading...")

        # TODO MMv2 - cancel tasks
        self.check_queues_to_spawn_new_match.cancel()

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

    def get_queue(self, queue_id: str) -> Optional[ActiveMatchQueue]:
        """Gets an active queue with the given ID.

        Args:
            queue_id (str): The queue to retrieve.

        Returns:
            Optional[ActiveMatchQueue]: The active queue if exists, None otherwise.
        """
        for active_queue in self.active_queues:
            if active_queue.queue.queue_id == queue_id:
                return active_queue

        return None

    def get_active_match(self, bot_match_id: int) -> Optional[ActiveMatch]:
        """Gets an active match with the given bot match ID.

        Args:
            bot_match_id (int): The match to retrieve.

        Returns:
            Optional[ActiveMatch]: The active match if exists, None otherwise.
        """
        for active_match in self.active_matches:
            if active_match.bot_match_id == bot_match_id:
                return active_match

        return None

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

    def add_party_to_queue(
        self, players: List[PlayerProfile], queue_id: str
    ) -> Optional[ActiveMatchQueue]:
        """Adds a list of players (1+) to a queue as a party, meaning they will
            join matches together (as a team) and be removed from queue together.

        Args:
            players: (List[PlayerProfile]): The players to add as a party.
            queue_id (str): The queue to add party to.

        Returns:
            Optional[ActiveMatchQueue]: Returns the queue the party was added to, None if not.
        """
        queue = self.get_queue(queue_id)
        if queue is None:
            return None

        # Ensure none of the players are still in a match
        for player in players:
            if self.is_player_in_match(player):
                return None

        # Ensure this queue will allow this party to join
        if not queue.can_add_party(players):
            return None

        # Add party to queue
        party_added = queue.add_party_v2(players)
        if not party_added:
            return None

        # TODO MMv2 - trigger first joined notification

        return queue

    def remove_party_from_queue(
        self, players: List[PlayerProfile], queue_id: str
    ) -> None:
        """Removes a list of players (1+) from a queue, assuming they are a party.
            If they disbanded or are not a party, this method will remove all players anyway.

        Args:
            players (List[PlayerProfile]): The players to remove from the queue.
            queue_id (str): The queue to remove the players from.
        """
        queue = self.get_queue(queue_id)
        if queue is None:
            return

        queue.remove_party_v2(players)

    def cancel_match(self, bot_match_id: int) -> Optional[ActiveMatch]:
        """Cancels an active match with the given bot match ID, if one exists.

        Args:
            bot_match_id (int): The bot match ID of the match to cancel.

        Returns:
            Optional[ActiveMatch]: The canceled match if existed, None otherwise.
        """
        match = self.get_active_match(bot_match_id)
        if match is None:
            return None

        # Complete the match
        canceled_match = CompletedMatch(match, canceled=True)
        # TODO MMv2 - call something to delete the match's active message in queue view
        canceled_match.cleanup()

        return match

    def remove_player_from_all_active_queues(self, player: PlayerProfile) -> None:
        """Removes a player from all queues they are in.

        Args:
            player (PlayerProfile): The player to remove.
        """
        for active_queue in self.active_queues:
            active_queue.remove_party_v2([player])

    @tasks.loop(seconds=1)
    async def check_queues_to_spawn_new_match(self):
        """Checks all active queues and spawns a new match if appropriate."""
        for active_queue in self.active_queues:
            try:
                should_generate_match = active_queue.should_generate_match()
                if not should_generate_match:
                    continue

                bot_match_id = self.ddb_manager.get_next_bot_match_id_and_increment()
                active_match = active_queue.generate_match(bot_match_id)

                if active_match is None:
                    logging.error(
                        f"Error generating match {bot_match_id} for active queue {active_queue}."
                    )
                    continue

                logging.info(
                    f"Match generated for queue {active_queue.queue.queue_id}, match id {active_match.match_id}."
                )

                # Remove all players in this match from every other queue
                for player in active_match.players():
                    self.remove_player_from_all_active_queues(player)

                # Persist the match in the case of bot going down
                persist_match(active_match)

                # TODO MMv2 - mm monitor logic for new active match

            except Exception as e:
                logging.error(f"Error checking queues to spawn new match: {e}")

    @check_queues_to_spawn_new_match.before_loop
    async def before_checks(self):
        """Wait until the bot is ready before starting the loop."""
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(MatchmakingManagerV2(bot))


def get_matchmaking_manager_v2():
    """Gets matchmaking manager singleton if initialized, else returns None."""
    return registry.get(COG_MATCHMAKING_MANAGER_V2)

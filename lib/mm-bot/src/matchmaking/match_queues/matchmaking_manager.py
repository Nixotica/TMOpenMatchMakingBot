import asyncio
import logging
import threading
from typing import List, Optional
from models.match_queue import MatchQueue
from matchmaking.matches.active_match import ActiveMatch
from matchmaking.match_queues.active_match_queue import ActiveMatchQueue
from aws.dynamodb import DynamoDbManager
from matchmaking.match_queues.constants import QUEUE_MANAGER_CHECK_MATCH_RESULTS_INTERVAL_SEC, QUEUE_MANAGER_CHECK_QUEUES_INTERVAL_SEC
from models.player_profile import PlayerProfile
import time

class MatchmakingManager:
    """The backbone of handling queues, creating and monitoring events, and distributing points. 
    """

    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(MatchmakingManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):  # Avoid re-initializing the instance
            self._initialized = True
            self.active_queues: List[ActiveMatchQueue] = []
            match_queues = DynamoDbManager().get_active_match_queues()
            logging.info(f"Instantiating matchmaking manager with active match queues {match_queues}.")
            for queue in match_queues:
                self.active_queues.append(ActiveMatchQueue(queue))  # TODO - it should also check DDB table if this updated on some cadence
            self.active_matches: List[ActiveMatch] = []
            self.new_active_matches: List[ActiveMatch] = [] # Only new and not processed by bot
            self.completed_matches: List[ActiveMatch] = [] # Only completed and not processed by bot

            self._last_check_queues_time = 0
            self._last_check_matches_time = 0

            self._thread = None

    def add_player_to_queue(self, player: PlayerProfile, queue_id: str) -> Optional[ActiveMatchQueue]:
        """Adds a player to the given queue by ID. 

        Args:
            player (PlayerProfile): Player to add to the queue. 
            queue_id (str): The queue to add to.

        Returns:
            Optional[ActiveMatchQueue]: Returns the queue the player was added to, None if not.
        """
        for queue in self.active_queues:
            if queue.queue.queue_id == queue_id:
                queue.add_player(player)
                return queue
        logging.warn(f"Attempted to add player to a queue which doesn't exist: {queue_id}")
        return None

    def remove_player_from_queue(self, player: PlayerProfile, queue_id: str):
        """Handles a player leaving a queue by ID (not caused by new match spawning).
        """
        pass  # TODO

    def process_completed_matches(self) -> List[ActiveMatch]:
        """Returns a list of completed matches and clears the list.
        """
        completed_matches = self.completed_matches
        for match in completed_matches:
            match.cleanup()
        self.completed_matches = []
        return completed_matches
    
    def process_new_active_matches(self) -> List[ActiveMatch]:
        """Returns a list of new active matches and clears the list.
        """
        new_active_matches = self.new_active_matches
        self.new_active_matches = []
        return new_active_matches

    async def _run_forever(self):
        """Run the matchmaking manager forever. 
        """
        while True:
            logging.debug(f"Running Matchmaking Manager loop...")
            await self._check_if_should_queue_matches()
            await self._check_active_matches()
            await asyncio.sleep(5)

    def start_run_forever_in_thread(self):
        """Starts the run_forever method in a separate thread with its own event loop."""
        logging.info("Starting matchmaking manager in a separate thread...")
        self._thread = threading.Thread(target=self._start_event_loop, daemon=True)
        self._thread.start()

    def _start_event_loop(self):
        """Starts an event loop in the current thread to run async methods."""
        loop = asyncio.new_event_loop()  # Create a new event loop
        asyncio.set_event_loop(loop)  # Set this loop as the current event loop
        loop.run_until_complete(self._run_forever())  # Run the async method
        loop.run_forever()  # Keep the loop running

    async def _check_if_should_queue_matches(self):
        """Checks if the matchmaking manager should queue matches.
        """
        now = time.time()
        if now - self._last_check_queues_time > QUEUE_MANAGER_CHECK_QUEUES_INTERVAL_SEC:
            self._last_check_queues_time = now
            logging.debug("Checking queues for sufficient size to generate matches...")
            for active_queue in self.active_queues:
                active_match = active_queue.try_generate_match()
                if active_match is not None: 
                    logging.info(f"Match generated for queue {active_queue.queue.queue_id}, match id {active_match.match_id}.")
                    self.new_active_matches.append(active_match)
                    self.active_matches.append(active_match)

    async def _check_active_matches(self):
        """Checks if the matchmaking manager can get results from ongoing/completed matches.
        """
        now = time.time()
        if now - self._last_check_matches_time > QUEUE_MANAGER_CHECK_MATCH_RESULTS_INTERVAL_SEC:
            self._last_check_matches_time = now
            logging.debug("Checking matches for results...")
            for active_match in self.active_matches:
                if active_match.is_match_complete():
                    logging.info(f"Match {active_match.match_id} is complete.")
                    self.active_matches.remove(active_match)
                    self.completed_matches.append(active_match)
                    # TODO - call distribute points, etc

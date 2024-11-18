import asyncio
import logging
import threading
from typing import Dict, List, Optional
from models.match_queue import MatchQueue
from matchmaking.matches.active_match import ActiveMatch
from matchmaking.matches.completed_match import CompletedMatch
from matchmaking.match_queues.active_match_queue import ActiveMatchQueue
from aws.dynamodb import DynamoDbManager
from matchmaking.match_queues.constants import (
    QUEUE_MANAGER_CHECK_MATCH_RESULTS_INTERVAL_SEC,
    QUEUE_MANAGER_CHECK_QUEUES_INTERVAL_SEC,
    QUEUE_MANAGER_CHECK_KICK_QUEUED_PLAYERS_INTERVAL_SEC,
    QUEUE_MANAGER_MAX_TIME_IN_QUEUE_SEC,
    QUEUE_MANAGER_MIN_TIME_PING_FIRST_PLAYER_JOIN_QUEUE_SEC,
)
from models.player_profile import PlayerProfile
from models.leaderboard import Leaderboard
from models.match_queue import QueueType
from matchmaking.matches.team_2v2 import Team2v2
from nadeo_event_api.api.structure.event import Event
import time


class MatchmakingManager:
    """The backbone of handling queues, creating and monitoring events, and distributing points."""

    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(MatchmakingManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):  # Avoid re-initializing the instance
            self._initialized = True
            self.active_queues: List[ActiveMatchQueue] = []
            self.ddb_manager = DynamoDbManager()
            match_queues = self.ddb_manager.get_active_match_queues()
            logging.info(
                f"Instantiating matchmaking manager with active match queues {match_queues}."
            )
            for queue in match_queues:
                self.active_queues.append(
                    ActiveMatchQueue(queue)
                )  # TODO - it should also check DDB table if this updated on some cadence
            self.active_matches: List[ActiveMatch] = []
            self.new_active_matches: List[
                ActiveMatch
            ] = []  # Only new and not processed by bot
            self.completed_matches: List[
                CompletedMatch
            ] = []  # Only completed and not processed by bot
            self.new_first_players_joined_queue: List[
                tuple[PlayerProfile, ActiveMatchQueue]
            ] = []  # Only detected internally and not processed by bot

            self._last_check_queues_time = 0
            self._last_check_matches_time = 0
            self._last_check_kick_players_time = 0
            self._last_first_player_ping_time: Dict[str, float] = {} # queue_id : time

            self._thread = None

    def add_queue(self, queue: MatchQueue) -> ActiveMatchQueue:
        """Adds a new active queue to the Matchmaking manager.

        Args:
            queue (MatchQueue): The queue to add and activate.

        Returns:
            ActiveMatchQueue: ActiveMatchQueue generated from the queue.
        """
        active_queue = ActiveMatchQueue(queue)
        self.active_queues.append(active_queue)
        return active_queue
    
    def is_player_in_match(self, player: PlayerProfile) -> bool:
        """Checks if a player is in an active match.

        Args:
            player (PlayerProfile): The player to check.

        Returns:
            bool: True if player is in an active match, False otherwise. 
        """
        for match in self.active_matches:
            for match_player in match.player_profiles:
                if player == match_player:
                    return True
            
        return False

    def add_player_to_queue(
        self, player: PlayerProfile, queue_id: str
    ) -> Optional[ActiveMatchQueue]:
        """Adds a player to the given queue by ID.

        Args:
            player (PlayerProfile): Player to add to the queue.
            queue_id (str): The queue to add to.

        Returns:
            Optional[ActiveMatchQueue]: Returns the queue the player was added to, None if not.
        """
        for queue in self.active_queues:
            if queue.queue.queue_id == queue_id:
                if queue.queue.type == QueueType.Queue2v2.value:
                    logging.error(f"Attempted to add player to a 2v2 queue: {queue_id}")
                    # TODO - this should not be an error, we should allow free agents
                    return None
                
                if self.is_player_in_match(player):
                    logging.info(
                        f"Player {player.tm_account_id} already in an active match."
                    )
                    return None

                player_added = queue.add_player(player)
                if not player_added:
                    logging.info(
                        f"Player {player.tm_account_id} already in queue {queue_id}."
                    )
                    return None
                
                # If this was the first person to join queue, trigger a ping to the discord
                time_of_last_ping = self._last_first_player_ping_time.get(queue_id)
                now = time.time()

                if len(queue.players) == 1 and (
                    time_of_last_ping is None or
                    now - time_of_last_ping > QUEUE_MANAGER_MIN_TIME_PING_FIRST_PLAYER_JOIN_QUEUE_SEC
                ):
                    logging.info(
                        f"First player {player.tm_account_id} joined queue {queue_id}."
                    )
                    self.new_first_players_joined_queue.append(
                        (player, queue)
                    )
                    self._last_first_player_ping_time[queue_id] = now

                return queue
        logging.warning(
            f"Attempted to add player to a queue which doesn't exist: {queue_id}"
        )
        return None

    def add_team_to_queue(
        self, team: Team2v2, queue_id: str
    ) -> Optional[ActiveMatchQueue]:
        """Adds a team to the given queue by ID.

        Args:
            team (Team2v2): Team to add to the queue.
            queue_id (str): The queue to add to.

        Returns:
            Optional[ActiveMatchQueue]: Returns the queue the team was added to, None if not.
        """
        for queue in self.active_queues:
            if queue.queue.queue_id == queue_id:
                if queue.queue.type == QueueType.Queue1v1v1v1.value:
                    logging.error(
                        f"Attempt to add team {team} to single player queue {queue_id}."
                    )
                    return None
                queue.add_team(team)
                return queue
        logging.warn(
            f"Attempted to add team to a queue which doesn't exist: {queue_id}"
        )
        return None

    def remove_player_from_queue(self, player: PlayerProfile, queue_id: str) -> None:
        """Removes a player from the given queue by ID.

        Args:
            player (PlayerProfile): Player to remove from the queue.
            queue_id (str): The queue to remove from.
        """
        for queue in self.active_queues:
            if queue.queue.queue_id == queue_id:
                if queue.queue.type == QueueType.Queue2v2.value:
                    logging.error(
                        f"Attempted to remove player from a 2v2 queue: {queue_id}"
                    )
                    # TODO - this should not be an error, we should allow free agents
                    return None
                queue.remove_player(player)

    def remove_team_from_queue(self, team: Team2v2):
        pass  # TODO

    def cancel_match(self, bot_match_id: int) -> Optional[ActiveMatch]:
        """Cancels an active match, if one exists with the givne bot match ID.

        Args:
            bot_match_id (int): The bot match ID of the match to cancel.

        Returns:
            ActiveMatch: The canceled match.
        """
        for match in self.active_matches:
            if match.bot_match_id == bot_match_id:
                self.active_matches.remove(match)

            Event.delete_from_id(match.event_id)
            logging.info(f"Canceled match with bot match ID {bot_match_id} and event ID {match.event_id}.")

            return match
        return None

    def process_completed_matches(self) -> List[CompletedMatch]:
        """Returns a list of completed matches and clears the list."""
        completed_matches = self.completed_matches
        self.completed_matches = []
        return completed_matches

    def process_new_active_matches(self) -> List[ActiveMatch]:
        """Returns a list of new active matches and clears the list."""
        new_active_matches = self.new_active_matches
        self.new_active_matches = []
        return new_active_matches
    
    def process_first_player_joined_queue(self) -> List[tuple[PlayerProfile, ActiveMatchQueue]]:
        """Returns a list of players who took the initiative to join a match queue with zero players in it."""
        new_first_players_joined_queue = self.new_first_players_joined_queue
        self.new_first_players_joined_queue = []
        return new_first_players_joined_queue

    def get_active_queue_by_id(self, queue_id: str) -> Optional[ActiveMatchQueue]:
        """Returns an active queue with the given ID, else None"""
        for queue in self.active_queues:
            if queue.queue.queue_id == queue_id:
                return queue
        return None

    def add_leaderboard_to_active_queue(self, queue_id: str, leaderboard_id: str):
        """Adds a leaderboard to an active queue in the mm manager.

        Args:
            queue_id (str): The queue ID of the queue to add the leaderboard to.
            leaderboard (Leaderboard): The leaderboard to add.

        Returns:
            bool: True if successfully added the leaderboard, False otherwise.
        """
        for queue in self.active_queues:
            if queue.queue.queue_id == queue_id:
                if queue.queue.leaderboard_ids is None:
                    queue.queue.leaderboard_ids = []
                queue.queue.leaderboard_ids.append(leaderboard_id)

    async def _run_forever(self):
        """Run the matchmaking manager forever."""
        while True:
            logging.debug(f"Running Matchmaking Manager loop...")
            await self._check_if_should_queue_matches()
            await self._check_active_matches()
            await self._check_if_should_kick_idle_players_from_queue()
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
        """Checks if the matchmaking manager should queue matches."""
        now = time.time()
        if now - self._last_check_queues_time < QUEUE_MANAGER_CHECK_QUEUES_INTERVAL_SEC:
            return

        self._last_check_queues_time = now
        logging.debug("Checking queues for sufficient size to generate matches...")
        new_active_matches: List[ActiveMatch] = []
        for active_queue in self.active_queues:
            should_generate_match = active_queue.should_generate_match()
            if not should_generate_match:
                continue

            bot_match_id = self.ddb_manager.get_next_bot_match_id_and_increment()

            active_match = active_queue.generate_match(bot_match_id)

            if active_match is None:
                logging.debug(
                    f"Queue {active_queue.queue.queue_id} does not have enough players to generate a match."
                )
                continue

            logging.info(
                f"Match generated for queue {active_queue.queue.queue_id}, match id {active_match.match_id}."
            )
            new_active_matches.append(active_match)

        for active_match in new_active_matches:
            # Remove players in new active match from all queues
            for active_queue in self.active_queues:
                # Remove all independent players
                players_to_remove = active_queue.players.copy()
                for player in players_to_remove:
                    if isinstance(active_match.player_profiles, List):
                        if player.profile in active_match.player_profiles:
                            active_queue.remove_player(player)
                    else:
                        if (
                            active_match.player_profiles.team_a.player_a == player
                            or active_match.player_profiles.team_a.player_b == player
                            or active_match.player_profiles.team_b.player_a == player
                            or active_match.player_profiles.team_b.player_b == player
                        ):
                            active_queue.remove_player(player)
                # Remove all teams (joined as parties)
                for team in active_queue.teams:
                    if isinstance(active_match.player_profiles, List):
                        logging.warning(
                            "Found individual player in an active queue team, this should not happen."
                        )
                        continue
                    if (
                        team == active_match.player_profiles.team_a
                        or team == active_match.player_profiles.team_b
                    ):
                        active_queue.remove_team(team)
            self.new_active_matches.append(active_match)
            self.active_matches.append(active_match)

    async def _check_active_matches(self):
        """Checks if the matchmaking manager can get results from ongoing/completed matches."""
        now = time.time()
        if (
            now - self._last_check_matches_time
            < QUEUE_MANAGER_CHECK_MATCH_RESULTS_INTERVAL_SEC
        ):
            return

        self._last_check_matches_time = now
        logging.debug("Checking matches for results...")
        for active_match in self.active_matches:
            if active_match.is_match_complete():
                logging.info(
                    f"Match {active_match.match_id} is complete. Adding to list of completed matches."
                )
                completed_match = CompletedMatch(active_match)
                self.active_matches.remove(active_match)
                self.completed_matches.append(completed_match)

    async def _check_if_should_kick_idle_players_from_queue(self):
        """Checks if players in queue have stayed in queue beyond acceptable idle time"""
        now = time.time()
        if (
            now - self._last_check_kick_players_time
            < QUEUE_MANAGER_CHECK_KICK_QUEUED_PLAYERS_INTERVAL_SEC
        ):
            return

        self._last_check_kick_players_time
        logging.debug("Checking players to kick from spending too long in queue...")
        for match_queue in self.active_queues:
            for queued_player in match_queue.players:
                if (
                    now - queued_player.queue_join_time_since_epoch
                    > QUEUE_MANAGER_MAX_TIME_IN_QUEUE_SEC
                ):
                    match_queue.remove_player(queued_player)
                    logging.info(
                        f"Kicked player {queued_player.profile.tm_account_id} from {match_queue.queue.queue_id} queue for exceeding {QUEUE_MANAGER_MAX_TIME_IN_QUEUE_SEC} seconds in queue."
                    )
            # TODO - add support for kicking teams

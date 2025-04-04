import asyncio
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
from matchmaking.matches.active_match import ActiveMatch
from matchmaking.matches.completed_match import CompletedMatch
from models.player_profile import PlayerProfile


@dataclass
class QueueStartedEvent:
    queue_id: str
    player: PlayerProfile


class EventType(Enum):
    """
    Defines the types of events that can be subscribed to.
    """

    NEW_ACTIVE_MATCH = 1
    NEW_COMPLETED_MATCH = 2
    QUEUE_STARTED = 3
    QUEUE_UPDATE = 4
    LEFT_QUEUE = 5


class MatchmakingManagerEventBus:
    """
    Manages pub/sub event buses to matchmaking manager events so concerned parties can act on events.
    """

    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(MatchmakingManagerEventBus, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):  # Avoid re-initializing the instance
            self._initialized = True

            self.subscriptions: Dict[EventType, List[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, event_type: EventType) -> asyncio.Queue:
        sub: asyncio.Queue = asyncio.Queue()
        self.subscriptions[event_type].append(sub)
        return sub

    def add_new_active_match(self, match: ActiveMatch) -> None:
        """Adds a new active match to a queue to be consumed by subscribers.

        Args:
            match (ActiveMatch): The active match to publish.
        """
        new_active_match_subs = self.subscriptions[EventType.NEW_ACTIVE_MATCH]
        for sub in new_active_match_subs:
            sub.put_nowait(match)

    def get_new_active_match(self, queue: asyncio.Queue) -> Optional[ActiveMatch]:
        """Gets a new active match from the given queue, None if empty.

        Args:
            queue (asyncio.Queue): A queue subscribed to NEW_ACTIVE_MATCH event.

        Returns:
            Optional[ActiveMatch]: ActiveMatch if a new one exists, False otherwise.
        """
        try:
            return queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def add_new_completed_match(self, match: CompletedMatch) -> None:
        """Adds a new completed match to a queue to be consumed by subscribers.

        Args:
            match (CompletedMatch): The completed match to publish.
        """
        new_completed_match_subs = self.subscriptions[EventType.NEW_COMPLETED_MATCH]
        for sub in new_completed_match_subs:
            sub.put_nowait(match)

    def get_new_completed_match(self, queue: asyncio.Queue) -> Optional[CompletedMatch]:
        """Gets a new completed match from the given queue, None if empty.

        Args:
            queue (asyncio.Queue): A queue subscribed to NEW_COMPLETED_MATCH event.

        Returns:
            Optional[CompletedMatch]: CompletedMatch if a new one exists, False otherwise.
        """
        try:
            return queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def add_new_queue_started(self, queue_id: str, player: PlayerProfile) -> None:
        """Adds a new mm queue started event to a pub-sub queue to be consumed by subscribers.

        Args:
            queue_id (str): The queue that was started by a player.
            player (PlayerProfile): The player that started the queue.
        """
        new_queue_started_subs = self.subscriptions[EventType.QUEUE_STARTED]
        for sub in new_queue_started_subs:
            sub.put_nowait(QueueStartedEvent(queue_id, player))

    def get_new_queue_started(
        self, queue: asyncio.Queue
    ) -> Optional[QueueStartedEvent]:
        """Gets a new queue started event from the given queue, None if empty.

        Args:
            queue (asyncio.Queue): A queue subscribed to QUEUE_STARTED event.

        Returns:
            Optional[QueueStartedEvent]: QueueStartedEvent if a new one exists, False otherwise.
        """
        try:
            return queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def add_queue_update(self, queue_id: str) -> None:
        """Adds a queue update event to a pub-sub queue to be consumed by subscribers.

        Args:
            queue_id (str): The queue that was joined by a player.
        """
        joined_queue_subs = self.subscriptions[EventType.QUEUE_UPDATE]
        for sub in joined_queue_subs:
            sub.put_nowait(queue_id)

    def get_new_queue_update(self, queue: asyncio.Queue) -> Optional[str]:
        """Gets a new queue update event from the given queue, None if empty.

        Args:
            queue (asyncio.Queue): A queue subscribed to QUEUE_UPDATE event.

        Returns:
            Optional[str]: queue_id if a new one exists, False otherwise.
        """
        try:
            return queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def add_player_left_queue(
        self, queue_id: str, players: list[PlayerProfile]
    ) -> None:
        """Adds a new player left queue event to a pub-sub queue to be consumed by subscribers.

        Args:
            queue_id: The queue that the players left
            players (list[PlayerProfile]): The players that left the queue.
        """
        joined_queue_subs = self.subscriptions[EventType.LEFT_QUEUE]
        for sub in joined_queue_subs:
            sub.put_nowait(players)

        queue_update_subs = self.subscriptions[EventType.QUEUE_UPDATE]
        for sub in queue_update_subs:
            sub.put_nowait(queue_id)

    def get_new_left_queue(self, queue: asyncio.Queue) -> Optional[list[PlayerProfile]]:
        """Gets a new left queue event from the given queue, None if empty.

        Args:
            queue (asyncio.Queue): A queue subscribed to LEFT_QUEUE event.

        Returns:
            Optional[list[PlayerProfile]]: list[PlayerProfile] if a new one exists, False otherwise.
        """
        try:
            return queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

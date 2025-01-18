from abc import ABC, abstractmethod
from dataclasses import dataclass
import time
from typing import List
from models.player_profile import PlayerProfile


class QueuedParty(ABC):
    """Abstract class for parties of players in a queue."""

    @abstractmethod
    def players(self) -> List[PlayerProfile]:
        """Gets all players in the party who are queued together.

        Returns:
            List[PlayerProfile]: List of players in the party.
        """
        pass

    @abstractmethod
    def queue_join_time(self) -> float:
        """Gets the time since epoch when the party joined the queue.

        Returns:
            float: Time since epoch when the party joined the queue.
        """
        pass


@dataclass(unsafe_hash=True)
class QueuedPlayer(QueuedParty):
    profile: PlayerProfile
    queue_join_time_since_epoch: float
    queue_id: str

    def players(self) -> List[PlayerProfile]:
        return [self.profile]
    
    def queue_join_time(self) -> float:
        return self.queue_join_time_since_epoch
    
    @classmethod
    def new_joined_player(cls, profile: PlayerProfile, queue_id: str):
        now = time.time()
        return cls(profile, now, queue_id)


@dataclass(unsafe_hash=True)
class QueuedTeam(QueuedParty):
    requester: PlayerProfile
    accepter: PlayerProfile
    queue_join_time_since_epoch: float
    queue_id: str

    def players(self) -> List[PlayerProfile]:
        return [self.requester, self.accepter]

    def queue_join_time(self) -> float:
        return self.queue_join_time_since_epoch

    @classmethod
    def new_joined_team(cls, requester: PlayerProfile, accepter: PlayerProfile, queue_id: str):
        now = time.time()
        return cls(requester, accepter, now, queue_id)

from dataclasses import dataclass
import time
from models.player_profile import PlayerProfile


@dataclass(unsafe_hash=True)
class QueuedPlayer:
    profile: PlayerProfile
    queue_join_time_since_epoch: float
    queue_id: str

    @classmethod
    def new_joined_player(cls, profile: PlayerProfile, queue_id: str):
        now = time.time()
        return cls(profile, now, queue_id)

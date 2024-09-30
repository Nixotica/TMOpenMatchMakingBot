from dataclasses import dataclass
from typing import Any, Dict

from aws.constants import KEY_LEADERBOARD_ID, KEY_CHANNEL_ID


@dataclass
class Leaderboard:
    leaderboard_id: str
    channel_id: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        leaderboard_id = data.get(KEY_LEADERBOARD_ID)
        channel_id = data.get(KEY_CHANNEL_ID)

        if not leaderboard_id or not channel_id:
            raise ValueError("Missing required fields")
        return cls(leaderboard_id, int(channel_id))
    
    def to_dict(self):
        return {
            KEY_LEADERBOARD_ID: self.leaderboard_id,
            KEY_CHANNEL_ID: self.channel_id
        }
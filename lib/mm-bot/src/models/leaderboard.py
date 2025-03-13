from dataclasses import dataclass
from typing import Any, Dict, Optional

from aws.constants import (
    KEY_ACTIVE,
    KEY_CHANNEL_ID,
    KEY_DISPLAY_NAME,
    KEY_LEADERBOARD_ID,
)


@dataclass
class Leaderboard:
    leaderboard_id: str
    channel_id: int
    display_name: Optional[str]
    active: Optional[bool]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        leaderboard_id = data.get(KEY_LEADERBOARD_ID)
        channel_id = data.get(KEY_CHANNEL_ID)
        display_name = data.get(KEY_DISPLAY_NAME)
        active = data.get(KEY_ACTIVE)

        if not leaderboard_id or not channel_id:
            raise ValueError("Missing required fields")
        return cls(leaderboard_id, int(channel_id), display_name, active)

    def to_dict(self):
        return {
            KEY_LEADERBOARD_ID: self.leaderboard_id,
            KEY_CHANNEL_ID: self.channel_id,
            KEY_DISPLAY_NAME: self.display_name,
            KEY_ACTIVE: self.active,
        }

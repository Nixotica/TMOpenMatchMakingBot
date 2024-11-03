from dataclasses import dataclass
from typing import Any, Dict, Optional

from aws.constants import *


@dataclass
class BotConfigs:
    global_leaderboard_id: Optional[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        global_leaderboard_id = data.get(CONFIGS_GLOBAL_LEADERBOARD_ID)

        return cls(global_leaderboard_id)

    def to_dict(self):
        return {CONFIGS_GLOBAL_LEADERBOARD_ID: self.global_leaderboard_id}

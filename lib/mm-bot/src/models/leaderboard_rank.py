from dataclasses import dataclass
from typing import Any, Dict

from aws.constants import KEY_DISPLAY_NAME, KEY_LEADERBOARD_ID, KEY_MIN_ELO, KEY_RANK_ID


@dataclass(unsafe_hash=True)
class LeaderboardRank:
    rank_id: str
    leaderboard_id: str
    display_name: str
    min_elo: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        rank_id = data.get(KEY_RANK_ID)
        leaderboard_id = data.get(KEY_LEADERBOARD_ID)
        display_name = data.get(KEY_DISPLAY_NAME)
        min_elo = data.get(KEY_MIN_ELO)

        if (
            rank_id is None
            or leaderboard_id is None
            or display_name is None
            or min_elo is None
        ):
            raise ValueError("Missing required fields")

        return cls(rank_id, leaderboard_id, display_name, min_elo)

    def to_dict(self):
        return {
            KEY_RANK_ID: self.rank_id,
            KEY_LEADERBOARD_ID: self.leaderboard_id,
            KEY_DISPLAY_NAME: self.display_name,
            KEY_MIN_ELO: self.min_elo,
        }

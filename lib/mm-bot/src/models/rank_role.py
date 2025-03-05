from dataclasses import dataclass
from typing import Any, Dict

from aws.constants import KEY_DISPLAY_NAME, KEY_MIN_ELO, KEY_RANK_ROLE_ID


@dataclass
class RankRole:
    rank_role_id: int
    display_name: str
    min_elo: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        rank_role_id = data.get(KEY_RANK_ROLE_ID)
        display_name = data.get(KEY_DISPLAY_NAME)
        min_elo = data.get(KEY_MIN_ELO)

        if rank_role_id is None or not display_name or min_elo is None:
            raise ValueError("Missing required fields")

        return cls(rank_role_id, display_name, min_elo)

    def to_dict(self):
        return {
            KEY_RANK_ROLE_ID: self.rank_role_id,
            KEY_DISPLAY_NAME: self.display_name,
            KEY_MIN_ELO: self.min_elo,
        }

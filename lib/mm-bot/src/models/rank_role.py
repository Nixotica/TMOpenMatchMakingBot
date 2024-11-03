from dataclasses import dataclass
from typing import Any, Dict

from aws.constants import KEY_MIN_ELO, KEY_RANK_ROLE_ID


@dataclass
class RankRole:
    rank_role_id: str
    min_elo: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        rank_role_id = data.get(KEY_RANK_ROLE_ID)
        min_elo = data.get(KEY_MIN_ELO)

        if not rank_role_id or min_elo is None:
            raise ValueError("Missing required fields")

        return cls(rank_role_id, min_elo)

    def to_dict(self):
        return {
            KEY_RANK_ROLE_ID: self.rank_role_id,
            KEY_MIN_ELO: self.min_elo,
        }

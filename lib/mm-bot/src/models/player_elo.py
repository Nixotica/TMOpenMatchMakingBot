from dataclasses import dataclass
from typing import Any, Dict
from aws.constants import KEY_TM_ACCOUNT_ID, KEY_ELO, KEY_LEADERBOARD_ID


@dataclass(unsafe_hash=True)
class PlayerElo:
    tm_account_id: str
    leaderboard_id: str
    elo: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        tm_account_id = data.get(KEY_TM_ACCOUNT_ID)
        leaderboard_id = data.get(KEY_LEADERBOARD_ID)
        elo = data.get(KEY_ELO)

        if not tm_account_id or not leaderboard_id or elo is None:
            raise ValueError("Missing required fields")

        return cls(tm_account_id, leaderboard_id, int(elo))

    def to_dict(self):
        return {
            KEY_TM_ACCOUNT_ID: self.tm_account_id,
            KEY_LEADERBOARD_ID: self.leaderboard_id,
            KEY_ELO: self.elo,
        }

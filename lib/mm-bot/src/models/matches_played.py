from dataclasses import dataclass
from typing import Any, Dict

from aws.constants import (
    KEY_MATCHES_PLAYED,
    KEY_MATCHES_WON,
    KEY_QUEUE_ID,
    KEY_TM_ACCOUNT_ID,
)


@dataclass
class MatchesPlayed:
    tm_account_id: str
    queue_id: str
    matches_played: int
    matches_won: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        tm_account_id = data.get(KEY_TM_ACCOUNT_ID)
        queue_id = data.get(KEY_QUEUE_ID)
        matches_played = data.get(KEY_MATCHES_PLAYED)
        matches_won = data.get(KEY_MATCHES_WON)

        if not tm_account_id or not queue_id or not matches_played or not matches_won:
            raise ValueError("Missing required fields")
        return cls(tm_account_id, queue_id, matches_played, matches_won)

    def to_dict(self):
        return {
            KEY_TM_ACCOUNT_ID: self.tm_account_id,
            KEY_QUEUE_ID: self.queue_id,
            KEY_MATCHES_PLAYED: self.matches_played,
            KEY_MATCHES_WON: self.matches_won,
        }

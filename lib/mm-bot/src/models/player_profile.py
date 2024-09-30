from dataclasses import dataclass
from typing import Any, Dict

from aws.constants import (
    KEY_DISCORD_ACCOUNT_ID,
    KEY_MATCHES_PLAYED,
    KEY_TM_ACCOUNT_ID,
)


@dataclass(unsafe_hash=True)
class PlayerProfile:
    tm_account_id: str
    discord_account_id: int
    matches_played: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        tm_account_id = data.get(KEY_TM_ACCOUNT_ID)
        discord_account_id = data.get(KEY_DISCORD_ACCOUNT_ID)
        matches_played = data.get(KEY_MATCHES_PLAYED)

        if not tm_account_id or not discord_account_id or not matches_played:
            raise ValueError("Missing required fields")

        return cls(tm_account_id, int(discord_account_id), int(matches_played))
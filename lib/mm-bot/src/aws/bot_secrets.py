from dataclasses import dataclass
from typing import Any, Dict, List
from aws.constants import *


@dataclass
class Secrets:
    ubi_auths: List[str]
    discord_bot_token: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        ubi_auths = data.get(SECRET_UBI_AUTHS)
        discord_bot_token = data.get(SECRET_DISCORD_BOT_TOKEN)

        if not ubi_auths or not discord_bot_token:
            raise ValueError("Missing required secrets")

        return cls(
            ubi_auths=ubi_auths,
            discord_bot_token=discord_bot_token,
        )
from dataclasses import dataclass
from typing import Any, Dict, List

from aws.constants import (
    SECRET_DISCORD_BOT_TOKEN,
    SECRET_PASTEBIN_API_DEV_KEY,
    SECRET_UBI_AUTHS,
)


@dataclass
class Secrets:
    ubi_auths: List[str]
    discord_bot_token: str
    pastebin_api_dev_key: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        ubi_auths = data.get(SECRET_UBI_AUTHS)
        discord_bot_token = data.get(SECRET_DISCORD_BOT_TOKEN)
        pastebin_api_dev_key = data.get(SECRET_PASTEBIN_API_DEV_KEY)

        if not ubi_auths or not discord_bot_token or not pastebin_api_dev_key:
            raise ValueError("Missing required secrets")

        return cls(ubi_auths, discord_bot_token, pastebin_api_dev_key)

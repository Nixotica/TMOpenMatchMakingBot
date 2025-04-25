from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from aws.constants import (
    SECRET_DISCORD_BOT_TOKEN,
    SECRET_PASTEBIN_API_DEV_KEY,
    SECRET_UBI_AUTHS,
    SECRET_PASTES_IO_LOGIN,
    SECRET_PASTES_IO_PASSWORD,
    SECRET_PASTEFY_LOGIN,
    SECRET_PASTEFY_PASSWORD,
)


@dataclass
class Secrets:
    ubi_auths: List[str]
    discord_bot_token: str
    pastebin_api_dev_key: Optional[str]
    pastes_io_login: Optional[str]
    pastes_io_password: Optional[str]
    pastefy_login: str
    pastefy_password: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        ubi_auths = data.get(SECRET_UBI_AUTHS)
        discord_bot_token = data.get(SECRET_DISCORD_BOT_TOKEN)
        pastebin_api_dev_key = data.get(SECRET_PASTEBIN_API_DEV_KEY)
        pastes_io_login = data.get(SECRET_PASTES_IO_LOGIN)
        pastes_io_password = data.get(SECRET_PASTES_IO_PASSWORD)
        pastefy_login = data.get(SECRET_PASTEFY_LOGIN)
        pastefy_password = data.get(SECRET_PASTEFY_PASSWORD)

        if (
            not ubi_auths
            or not discord_bot_token
            or not pastefy_login
            or not pastefy_password
        ):
            raise ValueError("Missing required secrets")

        return cls(
            ubi_auths,
            discord_bot_token,
            pastebin_api_dev_key,
            pastes_io_login,
            pastes_io_password,
            pastefy_login,
            pastefy_password,
        )

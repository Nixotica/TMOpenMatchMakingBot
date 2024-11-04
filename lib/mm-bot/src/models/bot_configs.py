from dataclasses import dataclass
from typing import Any, Dict, Optional

from aws.constants import *


@dataclass
class BotConfigs:
    global_leaderboard_id: Optional[str]
    bot_messages_channel_id: Optional[int] 

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        global_leaderboard_id = data.get(CONFIGS_GLOBAL_LEADERBOARD_ID)
        bot_messages_channel_id = data.get(CONFIGS_BOT_MESSAGES_CHANNEL_ID)
        
        return cls(global_leaderboard_id, bot_messages_channel_id)

    def to_dict(self):
        return {
            CONFIGS_GLOBAL_LEADERBOARD_ID: self.global_leaderboard_id,
            CONFIGS_BOT_MESSAGES_CHANNEL_ID: self.bot_messages_channel_id,
        }

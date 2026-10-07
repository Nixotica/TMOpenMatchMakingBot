from dataclasses import dataclass
from typing import Any, Dict, Optional

from aws.constants import (
    CONFIGS_BOT_MESSAGES_CHANNEL_ID,
    CONFIGS_GLOBAL_LEADERBOARD_ID,
    CONFIGS_PARTY_CHANNEL_ID,
    CONFIGS_PINGS_ROLE_ID,
    CONFIGS_PROFILE_CHANNEL_ID,
    CONFIGS_SCRIM_CATEGORY_ID,
    CONFIGS_SCRIM_MATCH_CLUB_ID,
)


@dataclass
class BotConfigs:
    global_leaderboard_id: Optional[str]
    bot_messages_channel_id: Optional[int]
    pings_role_id: Optional[int]
    party_channel_id: Optional[int]
    profile_channel_id: Optional[int]
    scrim_category_id: Optional[int]
    scrim_match_club_id: Optional[int]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        global_leaderboard_id = data.get(CONFIGS_GLOBAL_LEADERBOARD_ID)
        bot_messages_channel_id = data.get(CONFIGS_BOT_MESSAGES_CHANNEL_ID)
        pings_role_id = data.get(CONFIGS_PINGS_ROLE_ID)
        party_channel_id = data.get(CONFIGS_PARTY_CHANNEL_ID)
        profile_channel_id = data.get(CONFIGS_PROFILE_CHANNEL_ID)
        scrim_category_id = data.get(CONFIGS_SCRIM_CATEGORY_ID)
        scrim_match_club_id = data.get(CONFIGS_SCRIM_MATCH_CLUB_ID)

        return cls(
            global_leaderboard_id,
            bot_messages_channel_id,
            pings_role_id,
            party_channel_id,
            profile_channel_id,
            scrim_category_id,
            scrim_match_club_id,
        )

    def to_dict(self):
        return {
            CONFIGS_GLOBAL_LEADERBOARD_ID: self.global_leaderboard_id,
            CONFIGS_BOT_MESSAGES_CHANNEL_ID: self.bot_messages_channel_id,
            CONFIGS_PINGS_ROLE_ID: self.pings_role_id,
            CONFIGS_PARTY_CHANNEL_ID: self.party_channel_id,
            CONFIGS_PROFILE_CHANNEL_ID: self.profile_channel_id,
            CONFIGS_SCRIM_CATEGORY_ID: self.scrim_category_id,
            CONFIGS_SCRIM_MATCH_CLUB_ID: self.scrim_match_club_id,
        }

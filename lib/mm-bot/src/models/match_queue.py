from dataclasses import dataclass
from typing import Any, Dict, List

from aws.constants import KEY_LEADERBOARD_IDS, KEY_QUEUE_ID, KEY_ACTIVE, KEY_CAMPAIGN_ID, KEY_CAMPAIGN_CLUB_ID, KEY_MATCH_CLUB_ID, KEY_QUEUE_TYPE, KEY_CHANNEL_ID
from matchmaking.match_queues.enum import QueueType


@dataclass
class MatchQueue:
    queue_id: str
    campaign_club_id: int
    campaign_id: int
    match_club_id: int
    type: QueueType
    active: bool
    channel_id: int
    leaderboard_ids: List[str] | None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        queue_id = data.get(KEY_QUEUE_ID)
        campaign_club_id = data.get(KEY_CAMPAIGN_CLUB_ID)
        campaign_id = data.get(KEY_CAMPAIGN_ID)
        match_club_id = data.get(KEY_MATCH_CLUB_ID)
        type = data.get(KEY_QUEUE_TYPE)
        active = data.get(KEY_ACTIVE)
        channel_id = data.get(KEY_CHANNEL_ID)
        leaderboard_ids = data.get(KEY_LEADERBOARD_IDS)

        if not queue_id or not campaign_club_id or not campaign_id or not match_club_id or not type or not active or not channel_id:
            raise ValueError("Missing required fields")
        return cls(queue_id, int(campaign_club_id), int(campaign_id), int(match_club_id), type, active, int(channel_id), leaderboard_ids)
    
    def to_dict(self):
        return {
            KEY_QUEUE_ID: self.queue_id,
            KEY_CAMPAIGN_CLUB_ID: self.campaign_club_id,
            KEY_CAMPAIGN_ID: self.campaign_id,
            KEY_MATCH_CLUB_ID: self.match_club_id,
            KEY_QUEUE_TYPE: self.type.value,
            KEY_ACTIVE: self.active,
            KEY_CHANNEL_ID: self.channel_id
        }   
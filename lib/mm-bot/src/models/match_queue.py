from dataclasses import dataclass
from typing import Any, Dict

from aws.constants import KEY_QUEUE_ID, KEY_ACTIVE, KEY_CAMPAIGN_ID, KEY_CAMPAIGN_CLUB_ID, KEY_MATCH_CLUB_ID, KEY_QUEUE_TYPE
from matchmaking.match_queues.enum import QueueType


@dataclass
class MatchQueue:
    queue_id: str
    campaign_club_id: int
    campaign_id: int
    match_club_id: int
    type: QueueType
    active: bool

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        queue_id = data.get(KEY_QUEUE_ID)
        campaign_club_id = data.get(KEY_CAMPAIGN_CLUB_ID)
        campaign_id = data.get(KEY_CAMPAIGN_ID)
        match_club_id = data.get(KEY_MATCH_CLUB_ID)
        type = data.get(KEY_QUEUE_TYPE)
        active = data.get(KEY_ACTIVE)

        if not queue_id or not campaign_club_id or not campaign_id or not match_club_id or not type or not active:
            raise ValueError("Missing required fields")
        return cls(queue_id, int(campaign_club_id), int(campaign_id), int(match_club_id), type, active)
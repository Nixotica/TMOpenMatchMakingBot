from dataclasses import dataclass
from typing import Any, Dict
from aws.constants import KEY_BOT_MATCH_ID, KEY_QUEUE_ID, KEY_TM_MATCH_ID, KEY_TM_MATCH_LIVE_ID, KEY_TIME_PLAYED, KEY_RESULTS
import datetime as dt


@dataclass
class DdbMatchResults:
    bot_match_id: int
    queue_id: str
    tm_match_id: int
    tm_match_live_id: str 
    time_played: dt.datetime
    results: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            KEY_BOT_MATCH_ID: self.bot_match_id,
            KEY_QUEUE_ID: self.queue_id,
            KEY_TM_MATCH_ID: self.tm_match_id,
            KEY_TM_MATCH_LIVE_ID: self.tm_match_live_id,
            KEY_TIME_PLAYED: self.time_played,
            KEY_RESULTS: self.results
        }
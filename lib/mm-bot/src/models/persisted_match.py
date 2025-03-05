from dataclasses import dataclass
from typing import Any, Dict

from aws.constants import KEY_BOT_MATCH_ID, KEY_EVENT_ID, KEY_QUEUE_ID


@dataclass(unsafe_hash=True)
class PersistedMatch:
    bot_match_id: int
    event_id: int
    queue_id: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        bot_match_id = data.get(KEY_BOT_MATCH_ID)
        event_id = data.get(KEY_EVENT_ID)
        queue_id = data.get(KEY_QUEUE_ID)

        if bot_match_id is None or event_id is None or queue_id is None:
            raise ValueError(
                f"StoredActiveMatch must have a {KEY_BOT_MATCH_ID}, {KEY_EVENT_ID}, and {KEY_QUEUE_ID}"
            )

        return cls(bot_match_id, event_id, queue_id)

    def to_dict(self):
        return {
            KEY_BOT_MATCH_ID: self.bot_match_id,
            KEY_EVENT_ID: self.event_id,
            KEY_QUEUE_ID: self.queue_id,
        }

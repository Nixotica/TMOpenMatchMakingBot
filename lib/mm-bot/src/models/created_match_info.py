from dataclasses import dataclass


@dataclass
class CreatedMatchInfo:
    event_id: int
    round_id: int
    match_id: int
    match_live_id: str

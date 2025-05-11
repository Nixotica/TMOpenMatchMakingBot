from dataclasses import dataclass


@dataclass
class CreatedMatchInfo:
    event_id: int
    event_name: str
    round_id: int
    match_id: int
    match_live_id: str
    match_join_link: str

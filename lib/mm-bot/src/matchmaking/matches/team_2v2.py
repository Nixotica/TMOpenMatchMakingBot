from dataclasses import dataclass
from typing import Iterator
from models.player_profile import PlayerProfile


@dataclass
class Team2v2:
    player_a: PlayerProfile
    player_b: PlayerProfile

    def __iter__(self) -> Iterator[PlayerProfile]:
        yield self.player_a
        yield self.player_b


@dataclass
class Teams2v2:
    team_a: Team2v2
    team_b: Team2v2

    def __iter__(self) -> Iterator[Team2v2]:
        yield self.team_a
        yield self.team_b
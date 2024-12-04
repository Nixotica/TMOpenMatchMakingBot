from dataclasses import dataclass
from typing import Iterator, List
from models.player_profile import PlayerProfile
from nadeo_event_api.objects.inbound.match_results import RankedTeam


@dataclass(unsafe_hash=True)
class Team2v2:
    name: str
    player_a: PlayerProfile
    player_b: PlayerProfile

    def __iter__(self) -> Iterator[PlayerProfile]:
        yield self.player_a
        yield self.player_b

    def __contains__(self, player: PlayerProfile | str) -> bool:
        if isinstance(player, str):
            return self.player_a.tm_account_id == player or self.player_b.tm_account_id == player
        else:
            return player in self.__iter__()


@dataclass(unsafe_hash=True)
class Teams2v2:
    team_a: Team2v2
    team_b: Team2v2

    def __iter__(self) -> Iterator[Team2v2]:
        yield self.team_a
        yield self.team_b

    def __contains__(self, party: PlayerProfile | Team2v2) -> bool:
        if isinstance(party, PlayerProfile):
            return party in self.team_a or party in self.team_b
        return party in self.__iter__()

    def players(self) -> List[PlayerProfile]:
        return [self.team_a.player_a, self.team_a.player_b, self.team_b.player_a, self.team_b.player_b]
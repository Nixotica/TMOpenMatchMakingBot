from dataclasses import dataclass
from typing import Iterator

from models.player_profile import PlayerProfile


@dataclass(unsafe_hash=True)
class ActiveParty:
    # For now, parties ONLY consist of 2 players
    requester: PlayerProfile
    accepter: PlayerProfile

    def __iter__(self) -> Iterator[PlayerProfile]:
        yield self.requester
        yield self.accepter

    def __contains__(self, player: PlayerProfile) -> bool:
        return player in self.__iter__()
    
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

from models.player_profile import PlayerProfile


@dataclass(unsafe_hash=True)
class ActiveParty:
    # For now, parties ONLY consist of 2 players
    requester: PlayerProfile
    accepter: PlayerProfile

    # Keep track of party activity, to know when to disband it
    last_activity_time: datetime

    def __init__(self, requester: PlayerProfile, accepter: PlayerProfile):
        self.requester = requester
        self.accepter = accepter
        self.last_activity_time = datetime.utcnow()

    def __iter__(self) -> Iterator[PlayerProfile]:
        yield self.requester
        yield self.accepter

    def __contains__(self, player: PlayerProfile) -> bool:
        return player in self.__iter__()

    def teammate(self, player: PlayerProfile) -> PlayerProfile:
        if player == self.requester:
            return self.accepter
        elif player == self.accepter:
            return self.requester
        else:
            raise ValueError(f"Player {player.tm_account_id} is not in this party.")

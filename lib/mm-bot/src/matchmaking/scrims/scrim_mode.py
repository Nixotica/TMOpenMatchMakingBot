from enum import Enum

from matchmaking.constants import (
    NUM_1v1_PLAYERS,
    NUM_1v1v1v1_PLAYERS,
    NUM_2v2_PLAYERS,
)
from matchmaking.match_queues.enum import QueueType


class ScrimMode(Enum):
    """The match formats a scrim room can play. Each reuses the format of a queue type."""

    Mode2v2 = "2v2"
    Mode2v2Bo5 = "2v2 Bo5"
    Mode1v1v1v1 = "1v1v1v1"
    Mode1v1 = "1v1"

    def queue_type(self) -> QueueType:
        if self == ScrimMode.Mode2v2:
            return QueueType.Queue2v2
        elif self == ScrimMode.Mode2v2Bo5:
            return QueueType.QueueScrim2v2
        elif self == ScrimMode.Mode1v1v1v1:
            return QueueType.Queue1v1v1v1
        else:
            return QueueType.Queue1v1

    def num_players(self) -> int:
        if self.is_team_mode():
            return NUM_2v2_PLAYERS
        elif self == ScrimMode.Mode1v1v1v1:
            return NUM_1v1v1v1_PLAYERS
        else:
            return NUM_1v1_PLAYERS

    def is_team_mode(self) -> bool:
        return self.queue_type().is_2v2()

    def description(self) -> str:
        if self == ScrimMode.Mode2v2:
            return "Two teams of 2, one random map from the mappack"
        elif self == ScrimMode.Mode2v2Bo5:
            return "Two teams of 2, best of 5 with picks and bans"
        elif self == ScrimMode.Mode1v1v1v1:
            return "4 player cup on one random map from the mappack"
        else:
            return "Head to head cup on one random map from the mappack"

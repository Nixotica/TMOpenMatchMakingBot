from enum import Enum


class PartyRequestStatus(Enum):
    PENDING = 1
    ACCEPTED = 2
    REJECTED = 3
    CANCELLED = 4

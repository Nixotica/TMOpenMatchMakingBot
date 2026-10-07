import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from matchmaking.match_queues.constants import TEAM_BLUE, TEAM_RED
from matchmaking.matches.active_match import ActiveMatch
from matchmaking.matches.team_2v2 import Team2v2, Teams2v2
from matchmaking.scrims.constants import (
    SCRIM_INVITE_EXPIRATION_SEC,
    SCRIM_MAX_PLAYERS,
    SCRIM_QUEUE_ID_PREFIX,
    SCRIM_TEAM_SIZE,
)
from matchmaking.scrims.scrim_mappack import ScrimMappack
from matchmaking.scrims.scrim_mode import ScrimMode
from models.match_queue import MatchQueue
from models.player_profile import PlayerProfile


class ScrimRoomStatus(Enum):
    SETUP = 1  # Choosing the mode, mappack and players
    STARTING = 2  # Waiting on Nadeo to create the match
    IN_MATCH = 3  # Waiting for the match to complete


@dataclass
class ScrimInvite:
    invitee: PlayerProfile
    inviter: PlayerProfile
    sent_time: float


class ScrimRoom:
    """
    A scrim room, where a host sets up unranked matches with a mode and mappack of their choice
    against players they invite. The roster stays together between matches for rematches.
    """

    def __init__(self, room_id: int, host: PlayerProfile):
        self.room_id = room_id  # The ID of the room's discord channel
        self.host = host
        self.mode: Optional[ScrimMode] = None
        self.mappack: Optional[ScrimMappack] = None
        self.status = ScrimRoomStatus.SETUP
        self.bot_match_id: Optional[int] = None
        self.matches_played = 0
        self.last_activity_time = time.time()

        # Players in join order, and the side each one plays on (keyed by discord account ID).
        # Sides only matter in team modes.
        self._players: List[PlayerProfile] = []
        self._sides: Dict[int, str] = {}

        # Outstanding invites keyed by the invitee's discord account ID
        self.invites: Dict[int, ScrimInvite] = {}

    def touch(self) -> None:
        """Marks the room as active, pushing back its inactivity expiration."""
        self.last_activity_time = time.time()

    def players(self) -> List[PlayerProfile]:
        return list(self._players)

    def get_player(self, discord_account_id: int) -> Optional[PlayerProfile]:
        for player in self._players:
            if player.discord_account_id == discord_account_id:
                return player
        return None

    def has_player(self, discord_account_id: int) -> bool:
        return discord_account_id in self._sides

    def is_host(self, discord_account_id: int) -> bool:
        return self.host.discord_account_id == discord_account_id

    def is_full(self) -> bool:
        return len(self._players) >= SCRIM_MAX_PLAYERS

    def side_of(self, discord_account_id: int) -> Optional[str]:
        return self._sides.get(discord_account_id)

    def players_on(self, side: str) -> List[PlayerProfile]:
        return [
            player
            for player in self._players
            if self._sides[player.discord_account_id] == side
        ]

    def add_player(self, player: PlayerProfile, side: Optional[str] = None) -> bool:
        """Adds a player to the room. Sides can be uneven while setting up, so players can
            rearrange themselves, which also lets party teammates join the same side.

        Args:
            player (PlayerProfile): The player to add.
            side (Optional[str]): The side to put the player on. Defaults to the side with fewer
                players, or red on ties since the host starts on blue.

        Returns:
            bool: True if the player was added, False if they were already in the room or it's full.
        """
        if self.has_player(player.discord_account_id) or self.is_full():
            return False

        if side is None:
            side = (
                TEAM_BLUE
                if len(self.players_on(TEAM_BLUE)) < len(self.players_on(TEAM_RED))
                else TEAM_RED
            )

        self._players.append(player)
        self._sides[player.discord_account_id] = side
        self.invites.pop(player.discord_account_id, None)
        return True

    def remove_player(self, discord_account_id: int) -> Optional[PlayerProfile]:
        player = self.get_player(discord_account_id)
        if player is None:
            return None

        self._players.remove(player)
        self._sides.pop(discord_account_id)
        return player

    def switch_side(self, discord_account_id: int) -> bool:
        """Moves a player to the other side.

        Args:
            discord_account_id (int): The player to move.

        Returns:
            bool: True if the player switched sides, False if they're not in the room.
        """
        side = self._sides.get(discord_account_id)
        if side is None:
            return False

        self._sides[discord_account_id] = TEAM_RED if side == TEAM_BLUE else TEAM_BLUE
        return True

    def add_invite(self, invitee: PlayerProfile, inviter: PlayerProfile) -> bool:
        """Records an outstanding invite to the room.

        Returns:
            bool: True if the invite was added, False if the invitee is already in the room or invited.
        """
        if (
            self.has_player(invitee.discord_account_id)
            or invitee.discord_account_id in self.invites
        ):
            return False

        self.invites[invitee.discord_account_id] = ScrimInvite(
            invitee, inviter, time.time()
        )
        return True

    def expired_invites(self, now: float) -> List[ScrimInvite]:
        return [
            invite
            for invite in self.invites.values()
            if now - invite.sent_time > SCRIM_INVITE_EXPIRATION_SEC
        ]

    def start_blockers(self) -> List[str]:
        """Gets the reasons a match can't be started in the room yet.

        Returns:
            List[str]: Human readable reasons, empty if a match can be started.
        """
        blockers = []
        if self.mode is None:
            blockers.append("Choose a mode.")
        if self.mappack is None:
            blockers.append("Choose a mappack.")

        if self.mode is not None:
            num_players = self.mode.num_players()
            if len(self._players) != num_players:
                blockers.append(
                    f"{self.mode.value} needs exactly {num_players} players "
                    f"(the room has {len(self._players)})."
                )
            elif (
                self.mode.is_team_mode()
                and len(self.players_on(TEAM_BLUE)) != SCRIM_TEAM_SIZE
            ):
                blockers.append(
                    f"Each team needs exactly {SCRIM_TEAM_SIZE} players. Use Switch Side to even them out."
                )

        return blockers

    def teams(self) -> Teams2v2:
        blue = self.players_on(TEAM_BLUE)
        red = self.players_on(TEAM_RED)
        if len(blue) != SCRIM_TEAM_SIZE or len(red) != SCRIM_TEAM_SIZE:
            raise ValueError(
                f"Scrim room {self.room_id} doesn't have two full teams: {blue} vs {red}."
            )

        return Teams2v2(
            team_a=Team2v2(TEAM_BLUE, blue[0], blue[1]),
            team_b=Team2v2(TEAM_RED, red[0], red[1]),
        )

    def queue_id(self) -> str:
        return f"{SCRIM_QUEUE_ID_PREFIX}{self.room_id}"

    def to_match_queue(self, match_club_id: int) -> MatchQueue:
        """Builds the in-memory queue a match in this room is created from. It has no leaderboards,
            so the match is unranked.

        Args:
            match_club_id (int): The club to host the match in.

        Returns:
            MatchQueue: The scrim queue for the room's current mode and mappack.
        """
        if self.mode is None or self.mappack is None:
            raise ValueError(
                f"Scrim room {self.room_id} needs a mode and a mappack to create a match."
            )

        return MatchQueue(
            queue_id=self.queue_id(),
            campaign_club_id=self.mappack.campaign_club_id,
            campaign_id=self.mappack.campaign_id,
            match_club_id=match_club_id,
            type=self.mode.queue_type(),
            active=True,
            channel_id=self.room_id,
            leaderboard_ids=None,
            primary_leaderboard_id=None,
            ping_role_id=None,
            display_name=f"Scrim {self.mode.value}",
            category_id=None,
            is_scrim=True,
        )

    async def create_match(self, match_club_id: int, bot_match_id: int) -> ActiveMatch:
        """Creates a match for the room's roster in the competition tool.

        Args:
            match_club_id (int): The club to host the match in.
            bot_match_id (int): The bot match ID to give the match.

        Returns:
            ActiveMatch: The created match.
        """
        match_queue = self.to_match_queue(match_club_id)

        if self.mode == ScrimMode.Mode2v2:
            return await ActiveMatch.create_2v2(match_queue, bot_match_id, self.teams())
        elif self.mode == ScrimMode.Mode2v2Bo5:
            return await ActiveMatch.create_2v2_scrim(
                match_queue, bot_match_id, self.teams()
            )
        elif self.mode == ScrimMode.Mode1v1v1v1:
            return await ActiveMatch.create_1v1v1v1(
                match_queue, bot_match_id, self.players()
            )
        elif self.mode == ScrimMode.Mode1v1:
            return await ActiveMatch.create_1v1(
                match_queue, bot_match_id, self.players()
            )
        else:
            raise ValueError(f"Invalid scrim mode: {self.mode}")

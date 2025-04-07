from __future__ import annotations

import logging
from typing import List, Optional

from matchmaking.constants import SIM_MATCH_DURATION
from matchmaking.matches.event_creator import (
    create_1v1_match,
    create_1v1v1v1_match,
    create_2v2_match,
    create_lsc_match,
    create_solo_match,
)
from matchmaking.matches.team_2v2 import Teams2v2
from models.match_queue import MatchQueue
from models.player_profile import PlayerProfile
from nadeo_event_api.api.event_api import get_match_info
from nadeo_event_api.objects.inbound.match_info import MatchInfo


class ActiveMatch:
    """
    A class representing an ongoing match in the competition tool.
    Facilitates creation, monitoring, and deletion of the match.
    """

    def __init__(
        self,
        event_id: int,
        event_name: str,
        round_id: int,
        match_id: int,
        match_live_id: str,
        bot_match_id: int,
        player_profiles: (
            List[PlayerProfile] | Teams2v2
        ),  # TODO - this is terrible and not extensible
        match_queue: MatchQueue,
    ):
        self.event_id = event_id
        self.event_name = event_name
        self.round_id = round_id
        self.match_id = match_id
        self.match_live_id = match_live_id
        self.bot_match_id = bot_match_id
        self.player_profiles = player_profiles
        self.match_queue = match_queue

        self._match_info = None

    @staticmethod
    async def create_1v1v1v1(
        match_queue: MatchQueue,
        bot_match_id: int,
        players: List[PlayerProfile],
    ) -> ActiveMatch:
        logging.info(f"Creating new match for players: {players}")
        match_info = await create_1v1v1v1_match(match_queue, bot_match_id, players)

        return ActiveMatch(
            match_info.event_id,
            match_info.event_name,
            match_info.round_id,
            match_info.match_id,
            match_info.match_live_id,
            bot_match_id,
            players,
            match_queue,
        )

    @staticmethod
    async def create_1v1(
        match_queue: MatchQueue,
        bot_match_id: int,
        players: List[PlayerProfile],
    ) -> ActiveMatch:
        logging.info(f"Creating new 1v1 match for players: {players}")
        match_info = await create_1v1_match(match_queue, bot_match_id, players)

        return ActiveMatch(
            match_info.event_id,
            match_info.round_id,
            match_info.match_id,
            match_info.match_live_id,
            bot_match_id,
            players,
            match_queue,
        )

    @staticmethod
    async def create_2v2(
        match_queue: MatchQueue,
        bot_match_id: int,
        teams: Teams2v2,
    ) -> ActiveMatch:
        logging.info(f"Creating new 2v2 match for teams {teams}")
        match_info = await create_2v2_match(match_queue, bot_match_id, teams)

        return ActiveMatch(
            match_info.event_id,
            match_info.event_name,
            match_info.round_id,
            match_info.match_id,
            match_info.match_live_id,
            bot_match_id,
            teams,
            match_queue,
        )

    @staticmethod
    async def create_sim_2v2(
        match_queue: MatchQueue,
        bot_match_id: int,
        teams: Teams2v2,
    ) -> ActiveMatch:
        logging.info(f"Creating new simulated 2v2 match for teams {teams}")
        from matchmaking.matches.simulator import MatchSimulator

        return MatchSimulator().create_sim_2v2_match(
            match_queue, bot_match_id, teams, SIM_MATCH_DURATION
        )

    @staticmethod
    async def create_solo(
        match_queue: MatchQueue,
        bot_match_id: int,
        player: PlayerProfile,
    ) -> ActiveMatch:
        logging.info(f"Creating new solo match for player {player}")
        match_info = await create_solo_match(match_queue, bot_match_id, player)

        return ActiveMatch(
            match_info.event_id,
            match_info.event_name,
            match_info.round_id,
            match_info.match_id,
            match_info.match_live_id,
            bot_match_id,
            [player],
            match_queue,
        )

    @staticmethod
    async def create_lsc(
        match_queue: MatchQueue,
        bot_match_id: int,
        players: List[PlayerProfile],
    ) -> ActiveMatch:
        logging.info(f"Creating new LSC match for players {players}")
        match_info = await create_lsc_match(match_queue, bot_match_id, players)

        return ActiveMatch(
            match_info.event_id,
            match_info.event_name,
            match_info.round_id,
            match_info.match_id,
            match_info.match_live_id,
            bot_match_id,
            players,
            match_queue,
        )

    def _get_cached_match_info(self) -> MatchInfo:
        if not self._match_info:
            self._match_info = get_match_info(self.match_live_id)
        return self._match_info

    def has_player(self, player: PlayerProfile) -> bool:
        return player in self.player_profiles

    def participants(self) -> List[PlayerProfile]:
        if isinstance(self.player_profiles, Teams2v2):
            return self.player_profiles.players()
        return self.player_profiles

    def teams(self) -> Optional[Teams2v2]:
        if isinstance(self.player_profiles, Teams2v2):
            return self.player_profiles
        return None

    def is_match_complete(self) -> bool:
        if self.match_queue.type.is_simulated():
            from matchmaking.matches.simulator import MatchSimulator

            return MatchSimulator().is_match_complete(self.bot_match_id)
        else:
            self._match_info = get_match_info(self.match_live_id)
            if self._match_info.status == "COMPLETED":  # type: ignore
                return True
            return False

    def get_match_join_link(self) -> str | None:
        match_info = self._get_cached_match_info()
        if match_info.join_link:
            return match_info.join_link
        else:
            logging.warning("Match join link not found.")
            return None

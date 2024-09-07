from __future__ import annotations
import logging
from typing import List
from models.player_profile import PlayerProfile
from nadeo_event_api.api.event_api import get_match_results, get_match_info
from nadeo_event_api.objects.inbound.match_results import MatchResults
from nadeo_event_api.objects.inbound.match_info import MatchInfo
from nadeo_event_api.api.structure.event import Event
from models.match_queue import MatchQueue
from matchmaking.matches.event_creator import create_1v1v1v1_match


class ActiveMatch:
    """A class representing an ongoing match in the competition tool. Facilitates creation, monitoring, and deletion of the match. 
    """
    def __init__(
            self,
            event_id: int,
            round_id: int,
            match_id: int,
            match_live_id: str,
            player_profiles: List[PlayerProfile],
    ):
        self.event_id = event_id
        self.round_id = round_id
        self.match_id = match_id
        self.match_live_id = match_live_id
        self.player_profiles = player_profiles
        
        self._match_info = None

    @staticmethod
    def create(
        match_queue: MatchQueue,
        players: List[PlayerProfile],
    ) -> ActiveMatch:
        logging.info(f"Creating new match for players: {players}")
        (event_id, round_id, match_id, match_live_id) = create_1v1v1v1_match(match_queue, players)
        
        return ActiveMatch(event_id, round_id, match_id, match_live_id, players)

    def _get_match_info(self) -> MatchInfo:
        if not self._match_info:
            self._match_info = get_match_info(self.match_live_id)
        return self._match_info

    def is_match_complete(self) -> bool:
        match_info = self._get_match_info()
        if match_info.status == "COMPLETED":
            return True
        return False
    
    def get_match_join_link(self) -> str | None:
        match_info = self._get_match_info()
        if match_info.join_link:
            return match_info.join_link
        else: 
            logging.warning("Match join link not found.")
            return None

    def get_match_results(self) -> MatchResults:
        # TODO - pagination if needed
        return get_match_results(self.match_id, length=len(self.player_profiles), offset=0)

    def cleanup(self) -> None:
        logging.info(f"Cleaning up match {self.match_id} by deleting from Nadeo servers...")
        Event.delete_from_id(self.event_id)
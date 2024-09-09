from __future__ import annotations

import logging
from typing import Dict, List
from models.player_profile import PlayerProfile
from matchmaking.matches.team_2v2 import Teams2v2, Team2v2
from matchmaking.matches.active_match import ActiveMatch
from nadeo_event_api.objects.inbound.match_results import MatchResults
from nadeo_event_api.api.event_api import get_match_results
from matchmaking.match_complete.calculate_elo import calculate_elo_ratings
from matchmaking.match_complete.match_positions import get_match_positions_1v1v1v1, get_match_positions_2v2
from nadeo_event_api.api.structure.event import Event
import datetime as dt

class CompletedMatch:
    """A class representing a match that has been recently completed.
    """

    def __init__(
            self,
            active_match: ActiveMatch,
    ): 
        if not self.active_match.is_match_complete():
            raise ValueError(f"Match {self.active_match.match_id} is not complete and cannot be converted to CompletedMatch.")

        self.time_completed = dt.datetime.utcnow()
        self.active_match = active_match

        if isinstance(self.active_match.player_profiles, Teams2v2):
            self.match_results = get_match_results(self.active_match.match_id, length=4, offset=0)
        else:
            self.match_results = get_match_results(self.active_match.match_id, length=len(self.active_match.player_profiles), offset=0)

        if isinstance(self.active_match.player_profiles, List):
            match_positions = get_match_positions_1v1v1v1(self.active_match.player_profiles, self.match_results)
            (updated_elo_ratings, elo_differences) = calculate_elo_ratings(match_positions)
        else:
            match_positions = get_match_positions_2v2(self.active_match.player_profiles, self.match_results)
            (updated_elo_ratings, elo_differences) = calculate_elo_ratings(match_positions)
        
        self.updated_elo_ratings = updated_elo_ratings
        self.elo_differences = elo_differences
    
    def update_database(self) -> None:
        pass
        # TODO

    def cleanup(self) -> None:
        logging.info(f"Cleaning up match {self.active_match.match_id} by deleting from Nadeo servers...")
        Event.delete_from_id(self.active_match.event_id)
from __future__ import annotations

import logging
from typing import Dict, List
from models.player_profile import PlayerProfile
from models.player_elo import PlayerElo
from aws.dynamodb import DynamoDbManager
from matchmaking.matches.team_2v2 import Teams2v2, Team2v2
from matchmaking.matches.active_match import ActiveMatch
from nadeo_event_api.objects.inbound.match_results import MatchResults
from nadeo_event_api.api.event_api import get_match_results
from matchmaking.match_complete.calculate_elo import calculate_elo_ratings
from matchmaking.match_complete.match_positions import (
    get_match_positions_1v1v1v1,
    get_match_positions_2v2,
)
from nadeo_event_api.api.structure.event import Event
import datetime as dt


class CompletedMatch:
    """A class representing a match that has been recently completed."""

    def __init__(
        self,
        active_match: ActiveMatch,
        canceled: bool = False,
    ):
        self.time_completed = dt.datetime.utcnow()
        self.ddb_manager = DynamoDbManager()
        self.active_match = active_match

        if canceled:
            return

        if not active_match.is_match_complete():
            raise ValueError(
                f"Match {self.active_match.match_id} is not complete and cannot be converted to CompletedMatch."
            )

        if isinstance(self.active_match.player_profiles, Teams2v2):
            self.match_results = get_match_results(
                self.active_match.match_id, length=4, offset=0
            )
        else:
            self.match_results = get_match_results(
                self.active_match.match_id,
                length=len(self.active_match.player_profiles),
                offset=0,
            )

        if isinstance(self.active_match.player_profiles, List):
            match_positions = get_match_positions_1v1v1v1(
                self.active_match.player_profiles, self.match_results
            )
        # TODO - handle this case...
        else:
            logging.error("Elo calculation for 2v2 is not supported yet.")
        #     match_positions = get_match_positions_2v2(self.active_match.player_profiles, self.match_results)

        if self.active_match.match_queue.leaderboard_ids is None:
            logging.info(
                "No leaderboard IDs found for match queue, skipping elo calculation."
            )

        # Create a list of all updated elos for each leaderboard and another list for elo differences
        self.updated_elo_ratings: List[PlayerElo] = []
        self.elo_differences: List[PlayerElo] = []

        # Loop over each leaderboard related to the match queue...
        for leaderboard_id in active_match.match_queue.leaderboard_ids:  # type: ignore
            # Create mapping from player elo -> match position
            player_elos: Dict[PlayerElo, int] = {}

            # Convert player profiles into player elos by getting existing elo from DDB
            for player_profile, match_position in match_positions.items():
                player_elo = self.ddb_manager.get_or_create_player_elo(
                    player_profile.tm_account_id, leaderboard_id
                )
                player_elos[player_elo] = match_position

            (updated_elo_ratings, elo_differences) = calculate_elo_ratings(player_elos)

            # Store the updated elos and the difference in elo for each player in this leaderboard
            for original_player_elo_obj, updated_elo in updated_elo_ratings.items():
                new_player_elo = PlayerElo(
                    tm_account_id=original_player_elo_obj.tm_account_id,
                    leaderboard_id=original_player_elo_obj.leaderboard_id,
                    elo=updated_elo,
                )
                self.updated_elo_ratings.append(new_player_elo)

            for original_player_elo_obj, elo_difference in elo_differences.items():
                new_player_elo = PlayerElo(
                    tm_account_id=original_player_elo_obj.tm_account_id,
                    leaderboard_id=original_player_elo_obj.leaderboard_id,
                    elo=elo_difference,
                )
                self.elo_differences.append(new_player_elo)

        logging.info(
            f"Match {self.active_match.match_id} completed at {self.time_completed} with results: {self.match_results}. Elo updated: {self.updated_elo_ratings} ({self.elo_differences})."
        )

    def cleanup(self) -> None:
        logging.info(
            f"Cleaning up match {self.active_match.match_id} by deleting from Nadeo servers..."
        )
        Event.delete_from_id(self.active_match.event_id)

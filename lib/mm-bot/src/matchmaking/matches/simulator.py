from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List

from matchmaking.matches.active_match import ActiveMatch
from matchmaking.matches.team_2v2 import Teams2v2
from models.match_queue import MatchQueue

from nadeo_event_api.objects.inbound.match_results import (
    MatchResults,
    RankedParticipant,
    RankedTeam,
)


@dataclass
class SimulatedMatch:
    active_match: ActiveMatch
    created_time: datetime
    duration: timedelta


class MatchSimulator:
    """
    A singleton class which holds simulated matches, bypassing the Nadeo API.
    This is particularly useful when we want to run E2E tests without having
    players present to complete matches, or for integration testing.
    """

    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(MatchSimulator, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):  # Avoid re-initializing the instance
            self._initialized = True

            # Store a list of simulated matches
            self.simulated_matches: List[SimulatedMatch] = []

            # Store a mapping of bot match id to simulated match results
            self.match_results: Dict[int, MatchResults] = {}

    def create_sim_2v2_match(
        self,
        match_queue: MatchQueue,
        bot_match_id: int,
        teams: Teams2v2,
        duration: timedelta,
    ) -> ActiveMatch:
        """Creates a new simulated 2v2 match for the given players and a given duration.
            Once the duration has completed, it will generated fake match info to mark
            it as completed.

        Args:
            match_queue (MatchQueue): The queue for which this match was created.
            bot_match_id (int): The bot match id to assign to this match.
            teams (Teams2v2): The teams "playing" this match.
            duration (timedelta): The duration to wait before marking this match status as "COMPLETED"

        Returns:
            ActiveMatch: A fake active match created and owned by the simulator.
        """

        active_match = ActiveMatch(
            event_id=-1,
            event_name="Sim Match",
            round_id=-1,
            match_id=-1,
            match_live_id=str(
                bot_match_id
            ),  # This needs to be unique, since it's DDB index key
            bot_match_id=bot_match_id,
            player_profiles=teams,
            match_queue=match_queue,
        )

        simulated_match = SimulatedMatch(
            active_match=active_match,
            created_time=datetime.utcnow(),
            duration=duration,
        )

        self.simulated_matches.append(simulated_match)

        return active_match

    def is_match_complete(self, bot_match_id: int) -> bool:
        """Get if the simulated match is complete based on its creation time and
            the duration it was set to delay its completion. Also generates the
            simulated match results under the hood if complete.

        Args:
            bot_match_id (int): The bot match id for the match to check.

        Returns:
            bool: Returns true if complete, False if not.
        """
        for simulated_match in self.simulated_matches:
            if bot_match_id == simulated_match.active_match.bot_match_id:
                if (
                    datetime.utcnow() - simulated_match.duration
                    >= simulated_match.created_time
                ):
                    self.simulated_matches.remove(simulated_match)
                    self.match_results[simulated_match.active_match.bot_match_id] = (
                        self._generate_simulated_match_results(simulated_match)
                    )
                    return True
                return False

        # Otherwise, it's not registered and was likely already completed.
        return True

    def get_match_results(self, bot_match_id: int) -> MatchResults:
        """Gets the match results for the given match by bot match id. It also removes the
            results from the MatchSimulator storage, so it will return None if called twice.

        Args:
            bot_match_id (int): The bot match id for the match to get results for.

        Returns:
            MatchResults: The simulated match results.
        """
        return self.match_results.pop(bot_match_id, None)  # type: ignore

    def get_simulated_matches(self) -> List[SimulatedMatch]:
        return self.simulated_matches

    def _generate_simulated_match_results(
        self, simulated_match: SimulatedMatch
    ) -> MatchResults:
        """Generates match results for the given simulated match. It will simply assign the
            results in the order of teams having joined the queue, and put blue team as
            the winner over red team for 2v2 mode.

        Args:
            simulated_match (SimulatedMatch): The match for which to generate results.

        Returns:
            MatchResults: The simulated match results.
        """
        results: List[RankedParticipant] = []
        idx = 0
        for player in simulated_match.active_match.participants():
            # Create a "ranked participant" for this player.
            ranked_participant = RankedParticipant(
                participant=player.tm_account_id,
                rank=idx + 1,  # Ranked in the order they joined the queue.
                score=0,  # Unused
                zone=None,  # Unused
                team=None,  # Overwrite in next step if teams.
            )

            # Overwrite the team if the match is a team match.
            for team in simulated_match.active_match.teams():  # type: ignore
                if player in team:
                    ranked_participant.team = team.name

            results.append(ranked_participant)

            idx += 1

        # If this was a 2v2 match, we need to create ranked teams.
        teams: List[RankedTeam] = []
        if simulated_match.active_match.match_queue.type.is_2v2():

            idx = 0
            for team in simulated_match.active_match.teams():  # type: ignore
                ranked_team = RankedTeam(
                    position=idx + 1,  # Blue wins, red loses.
                    team=team.name,
                    rank=idx + 1,
                    score=0,  # Unused
                )

                teams.append(ranked_team)

                idx += 1

        return MatchResults(
            match_live_id=simulated_match.active_match.match_live_id,
            round_position=0,
            results=results,
            teams=teams,
        )

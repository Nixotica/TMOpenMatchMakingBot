import logging
from typing import Dict
from matchmaking.matches.team_2v2 import Team2v2, Teams2v2
from nadeo_event_api.objects.inbound.match_results import MatchResults

from models.player_profile import PlayerProfile


class MatchPositions2v2:
    def __init__(
        self,
        teams: Teams2v2,
        results: MatchResults,
    ):
        self.teams = teams
        self.results = results
        
    def individual_results(self) -> Dict[PlayerProfile, int]:
        """Get the individual positions of players independent of their team's results. 
        This is calculated by the game under the hood, so the rank of players in the "results" field is
        actually correlated with how many points they contributed to the game overall (4, 3, 2, 1 repartition).

        Returns:
            Dict[PlayerProfile, int]: A map of players to their rank (1st -> 4th)
        """
        match_positions = {}
        players = self.teams.players()
        for result in self.results.results:
            for player in players:
                if player.tm_account_id == result.participant:
                    if result.rank is None:
                        logging.warning(
                            f"Player {player.tm_account_id} has no rank in match results. They probably didn't show up. Giving them last."
                        )
                        match_positions[player] = 4
                    else:
                        match_positions[player] = result.rank
                    
        return match_positions
    
    def team_results(self) -> Dict[Team2v2, int]:
        match_positions = {}
        for team in self.results.teams:
            # Get the Team2v2 from the RankedTeam
            team_2v2 = next(
                (
                    t
                    for t in self.teams
                    if t.name == team.team
                )
            )

            if team.rank is None:
                logging.warning(
                    f"Team {team.team_id} has no rank in match results. They probably didn't show up. Giving them last."
                )
                match_positions[team_2v2] = 2
            else:
                match_positions[team_2v2] = team.rank

        return match_positions
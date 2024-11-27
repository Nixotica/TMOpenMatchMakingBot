import logging
from typing import Dict, List
from nadeo_event_api.objects.inbound.match_results import MatchResults
from matchmaking.matches.team_2v2 import Team2v2, Teams2v2
from models.player_profile import PlayerProfile


def get_match_positions_1v1v1v1(
    players: List[PlayerProfile], results: MatchResults
) -> Dict[PlayerProfile, int]:
    match_positions = {}
    for result in results.results:
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


def get_match_positions_2v2(
    teams: Teams2v2, results: MatchResults
) -> Dict[PlayerProfile, int]:
    players = [
        teams.team_a.player_a,
        teams.team_a.player_b,
        teams.team_b.player_a,
        teams.team_b.player_b,
    ]
    return get_match_positions_1v1v1v1(players, results)

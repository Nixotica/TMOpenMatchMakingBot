from dataclasses import dataclass
from typing import Dict, List
from models.player_profile import PlayerProfile
import numpy as np
from matchmaking.match_complete.match_positions_2v2 import MatchPositions2v2
from matchmaking.matches.team_2v2 import Team2v2
from models.player_elo import PlayerElo


@dataclass
class UpdatedElos:
    """A class representing updated elo ratings and the differences with previous elo for a given match.
    """
    updated_elo_ratings: Dict[PlayerElo, int]
    elo_differences: Dict[PlayerElo, int]


def expected_score(elo_i: int, elo_j: int):
    """
    Calculate the expected score for player i against player j.
    """
    return 1 / (1 + 10 ** ((elo_j - elo_i) / 400))
    

def calculate_elo_2v2_ratings(
    match_positions: MatchPositions2v2,
    player_elos: List[PlayerElo], 
    K_team=20,
    K_individual=5,
) -> UpdatedElos:
    """
    Calculate updated Elo ratings for all players based on their match positions and their team's placement.
    NOTE: Only pass in PlayerElo's pertaining to a single leaderboard at a time!

    Args:
        match_positions (MatchPositions2v2): The match positions object containing individual and team placements.
        player_elos (List[PlayerElo]): A list of players' current elos before this match.
        K_team (int, optional): Sensitivity for Elo adjustment in the team vs team calculation (default is 20).
        K_individual (int, optional): Sensitivity for Elo adjustment using individual player placement (default is 10).
    Returns:
        UpdatedElos: An object capturing the updated elos for every player.
    """

    def get_team_rating(player_elos: List[PlayerElo], team: Team2v2) -> int:
        player_a_rating = None
        player_b_rating = None

        for player_elo in player_elos:
            if player_elo.tm_account_id == team.player_a.tm_account_id:
                player_a_rating = player_elo.elo
            elif player_elo.tm_account_id == team.player_b.tm_account_id:
                player_b_rating = player_elo.elo
        
        if player_a_rating is None or player_b_rating is None:
            raise ValueError(
                f"Could not find player elos for team {team} in {player_elos}"
            )
        
        return (player_a_rating + player_b_rating) // 2

    # Calculate the team elo as the average of each team's player ratings
    team_a_rating = get_team_rating(player_elos, match_positions.teams.team_a)
    team_b_rating = get_team_rating(player_elos, match_positions.teams.team_b)

    # Expected score for each team based on the average team rating
    expected_score_a = expected_score(team_a_rating, team_b_rating)
    expected_score_b = expected_score(team_b_rating, team_a_rating)

    # Calculate total rating adjustment for each team
    teams_results = match_positions.team_results()
    
    # Get the actual score (1 = win, 0 = lose) for each team
    team_a_position = teams_results[match_positions.teams.team_a]
    actual_score_team_a = 1 if team_a_position == 1 else 0
    actual_score_team_b = 1 - actual_score_team_a

    team_a_adjustment = K_team * (actual_score_team_a - expected_score_a)
    team_b_adjustment = K_team * (actual_score_team_b - expected_score_b)

    print('team a adjustment:', team_a_adjustment)
    print('team b adjustment:', team_b_adjustment)

    individual_results = match_positions.individual_results()

    def get_player_placement(player: PlayerElo, individual_results: Dict[PlayerProfile, int]) -> int:
        for player_profile, placement in individual_results.items():
            if player_profile.tm_account_id == player.tm_account_id:
                return placement

        raise ValueError(f"Could not find player {player} in {individual_results}")
    
    # Calculate new elo for each player with adjusted distribution to avoid boosting
    updated_elo_ratings = {}
    elo_differences = {}
    for player in player_elos:
        R_i = player.elo
        
        # Determine the player's team's expected and actual scores, and total adjustment
        player_in_team_a = match_positions.teams.team_a.__contains__(player.tm_account_id)
        team_adjustment = team_a_adjustment if player_in_team_a else team_b_adjustment

        # Calculate individual adjustment based on head-to-head performance
        individual_adjustment = 0
        for opponent in player_elos:
            if opponent.tm_account_id == player.tm_account_id:
                continue  # Skip self

            # Calculate expected score against this opponent
            E_ij = expected_score(R_i, opponent.elo)

            # Determine actual score against this opponent (1 if player placed higher, 0 otherwise)
            player_placement = get_player_placement(player, individual_results)
            opponent_placement = get_player_placement(opponent, individual_results)
            S_ij = 1 if player_placement < opponent_placement else 0

            # Add to individual adjustment
            individual_adjustment += K_individual * (S_ij - E_ij)

        # Combine team and individual adjustments
        total_adjustment = team_adjustment + individual_adjustment

        # Calculate the updated elo and diff
        R_i_prime = R_i + total_adjustment
        diff = R_i_prime - R_i

        print(f'player {player.tm_account_id} R_i_prime {R_i_prime} and diff {diff}')

        updated_elo_ratings[player] = round(R_i_prime)
        elo_differences[player] = round(diff)

    return UpdatedElos(
        updated_elo_ratings=updated_elo_ratings,
        elo_differences=elo_differences,
    )


def calculate_elo_ratings(
    match_positions: Dict[PlayerElo, int], K=20
) -> UpdatedElos:
    """
    Calculate updated Elo ratings for all players based on their match positions.
    NOTE: Only pass in PlayerElo's pertaining to a single leaderboard at a time!

    Args:
        match_positions (Dict[PlayerElo, int]): A dictionary with player elos as keys and their match positions as values.
        K (int, optional): Sensitivity for Elo adjustment (default is 20).

    Returns:
        UpdatedElos: An object capturing the updated elos for every player.
    """

    if len(match_positions) < 2:
        # Work-around for solo queue testing - just give player 1 elo
        player_elo_obj = next(iter(match_positions))
        return UpdatedElos(
            updated_elo_ratings={player_elo_obj: player_elo_obj.elo + 1},
            elo_differences={player_elo_obj: 1}
        )

    def update_elo(R_i, S_i, E_i, K=7):
        """
        Update the Elo rating for a player based on the expected score and actual score.
        """
        return R_i + K * (S_i - E_i)

    initial_elo_ratings = {player: player.elo for player in match_positions}

    # Convert positions to actual scores (S_i)
    num_players = len(match_positions)
    position_to_score = {i: num_players - i for i in range(1, num_players + 1)}

    # Calculate expected scores (E_i)
    expected_scores = {}
    for player_i in initial_elo_ratings:
        E_i = 0
        for player_j in initial_elo_ratings:
            if player_i != player_j:
                E_i += expected_score(
                    initial_elo_ratings[player_i], initial_elo_ratings[player_j]
                )
        expected_scores[player_i] = round(E_i, 8)

    # Calculate updated Elo ratings
    updated_elo_ratings = {}
    for player in initial_elo_ratings:
        S_i = position_to_score[match_positions[player]]
        E_i = expected_scores[player]
        R_i = initial_elo_ratings[player]
        updated_elo_ratings[player] = round(update_elo(R_i, S_i, E_i, K))

    # Calculate the difference in Elo ratings
    elo_differences = {
        player: updated_elo_ratings[player] - initial_elo_ratings[player]
        for player in initial_elo_ratings
    }

    return UpdatedElos(
        updated_elo_ratings,
        elo_differences,
    )

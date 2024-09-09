from typing import Dict
import numpy as np
from models.player_profile import PlayerProfile

def calculate_elo_ratings(match_positions: Dict[PlayerProfile, int], K=7) -> tuple[Dict[PlayerProfile, int], Dict[PlayerProfile, int]]:
    """
    Calculate updated Elo ratings for all players based on their match positions.
    
    Parameters:
    - match_positions: A dictionary with player names as keys and their match positions as values.
    - K: Sensitivity constant for Elo adjustment (default is 7).
    
    Returns:
    - updated_elo_ratings: A dictionary with player names as keys and their updated Elo ratings as values.
    - elo_differences: A dictionary with player names as keys and the change in their Elo ratings.
    """

    def expected_score(elo_i: int, elo_j: int):
        """
        Calculate the expected score for player i against player j.
        """
        return 1 / (1 + 10 ** ((elo_j - elo_i) / 400))

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
                E_i += expected_score(initial_elo_ratings[player_i], initial_elo_ratings[player_j])
        expected_scores[player_i] = round(E_i, 8)

    # Calculate updated Elo ratings
    updated_elo_ratings = {}
    for player in initial_elo_ratings:
        S_i = position_to_score[match_positions[player]]
        E_i = expected_scores[player]
        R_i = initial_elo_ratings[player]
        updated_elo_ratings[player] = round(update_elo(R_i, S_i, E_i, K), 2)

    # Calculate the difference in Elo ratings
    elo_differences = {player: updated_elo_ratings[player] - initial_elo_ratings[player] for player in initial_elo_ratings}

    return updated_elo_ratings, elo_differences
from dataclasses import dataclass
import logging
import math
from typing import Dict, List

from matchmaking.match_complete.match_positions_2v2 import MatchPositions2v2
from matchmaking.matches.team_2v2 import Team2v2
from models.player_elo import PlayerElo
from models.player_profile import PlayerProfile


@dataclass
class UpdatedElos:
    """A class representing updated elo ratings and the differences with previous elo for a given match."""

    updated_elo_ratings: Dict[PlayerElo, int]
    elo_differences: Dict[PlayerElo, int]


def expected_score(elo_i: int, elo_j: int):
    """
    Calculate the expected score for player i against player j.
    """
    return 1 / (1 + 10 ** ((elo_j - elo_i) / 400))


def get_team_points_multiplier(
    player: PlayerElo, placement: int, teammate_placement: int, won: bool
) -> float:
    """Gets a player's share of the team's points won or lost based on their position and
        their teammate's position.

    Args:
        player (PlayerElo): The player whose points are being calculated, as their current elo.
        placement (int): The player's individual placement in the match.
        teammate_placement (int): The player's teammate's individual placement in the match.
        won (bool): Whether the player's team won the match.

    Returns:
        float: The elo diff multiplier to be applied to this player's elo change.
    """

    # Simply enumerate all possibilities and return the multiplier
    if placement == 1:
        if teammate_placement == 2:
            return 0.5
        elif teammate_placement == 3:
            return 0.6 if won else 0.4
        elif teammate_placement == 4:
            return 0.8 if won else 0.2

    if placement == 2:
        if teammate_placement == 1:
            return 0.5
        elif teammate_placement == 3:
            return 0.5
        elif teammate_placement == 4:
            return 0.7 if won else 0.3

    if placement == 3:
        if teammate_placement == 1:
            return 0.4 if won else 0.6
        elif teammate_placement == 2:
            return 0.5
        elif teammate_placement == 4:
            return 0.5

    if placement == 4:
        if teammate_placement == 1:
            return 0.2 if won else 0.8
        elif teammate_placement == 2:
            return 0.3 if won else 0.7
        elif teammate_placement == 3:
            return 0.5

    # If we reach here, something went wrong
    logging.error(
        f"Could not calculate team points multiplier for player {player} with "
        f"placement {placement} and teammate placement {teammate_placement}, "
        f"won {won}. This should not happen. Returning 0.5"
    )
    return 0.5


def calculate_elo_2v2_ratings(
    match_positions: MatchPositions2v2,
    player_elos: List[PlayerElo],
    K_team=30,
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

    def symmetric_round(x):
        """
        Round the elo symmetrically around zero such that no elo is gained nor lost.
        """
        if x > 0:
            return math.floor(x + 0.5)
        else:
            return math.ceil(x - 0.5)

    def force_even_symmetrically(x):
        """
        Force the result to be even so it can be split evenly in case of 50/50,
        accounting for the fact that we want to subtract if it's elo loss.
        """
        if x % 2 == 0:
            return x
        elif x > 0:
            return x + 1
        else:
            return x - 1

    team_a_adjustment: int = force_even_symmetrically(
        symmetric_round(K_team * (actual_score_team_a - expected_score_a))
    )
    team_b_adjustment: int = force_even_symmetrically(
        symmetric_round(K_team * (actual_score_team_b - expected_score_b))
    )

    def get_player_placement(
        player: PlayerElo, individual_results: Dict[PlayerProfile, int]
    ) -> int:
        for player_profile, placement in individual_results.items():
            if player_profile.tm_account_id == player.tm_account_id:
                return placement

        raise ValueError(
            f"Could not find player {player} in individual results {individual_results}"
        )

    def get_player_teammate_placement(
        player: PlayerElo, team: Team2v2, individual_results: Dict[PlayerProfile, int]
    ) -> int:
        teammate_account_id = (
            team.player_b.tm_account_id
            if player.tm_account_id == team.player_a.tm_account_id
            else team.player_a.tm_account_id
        )

        for player_profile, placement in individual_results.items():
            if player_profile.tm_account_id == teammate_account_id:
                return placement

        raise ValueError(
            f"Could not find teammate {teammate_account_id} in individual results {individual_results}"
        )

    individual_results = match_positions.individual_results()

    # Calculate new elo for each player with adjusted distribution to avoid boosting
    updated_elo_ratings = {}
    elo_differences = {}
    for player in player_elos:
        # Get the player's team
        player_team = (
            match_positions.teams.team_a
            if match_positions.teams.team_a.__contains__(player.tm_account_id)
            else match_positions.teams.team_b
        )

        # Determine the player's team's expected and actual scores, and total adjustment
        player_in_team_a = match_positions.teams.team_a.__contains__(
            player.tm_account_id
        )
        team_adjustment = team_a_adjustment if player_in_team_a else team_b_adjustment

        # Based on the player's placement and their teammate's placement, calculate multiplier to apply
        # to their team adjustment to split the amount won or lost
        player_placement = get_player_placement(player, individual_results)
        teammate_placement = get_player_teammate_placement(
            player, player_team, individual_results
        )
        team_points_multiplier = get_team_points_multiplier(
            player, player_placement, teammate_placement, team_adjustment > 0
        )

        # Use symmetric rounding again to avoid bleeding or synthesis of elo
        new_elo = symmetric_round(team_adjustment * team_points_multiplier) + player.elo
        elo_diff = new_elo - player.elo

        updated_elo_ratings[player] = new_elo
        elo_differences[player] = elo_diff

    return UpdatedElos(
        updated_elo_ratings=updated_elo_ratings,
        elo_differences=elo_differences,
    )


def calculate_elo_ratings(match_positions: Dict[PlayerElo, int], K=20) -> UpdatedElos:
    """
    Calculate updated Elo ratings for all players based on their match positions.
    NOTE: Only pass in PlayerElo's pertaining to a single leaderboard at a time!

    Args:
        match_positions (Dict[PlayerElo, int]): A dictionary with player elos as
            keys and their match positions as values.
        K (int, optional): Sensitivity for Elo adjustment (default is 20).

    Returns:
        UpdatedElos: An object capturing the updated elos for every player.
    """

    if len(match_positions) < 2:
        # Work-around for solo queue testing - just give player 1 elo
        player_elo_obj = next(iter(match_positions))
        return UpdatedElos(
            updated_elo_ratings={player_elo_obj: player_elo_obj.elo + 1},
            elo_differences={player_elo_obj: 1},
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

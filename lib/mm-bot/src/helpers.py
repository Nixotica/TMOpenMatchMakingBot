from typing import List, Optional
from models.leaderboard_rank import LeaderboardRank

def get_rank_for_player(
    player_elo: int,
    leaderboard_id: str,
    ranks: List[LeaderboardRank],
) -> Optional[LeaderboardRank]:
    """
    Get the rank for a player based on their Elo rating and the list of ranks.

    Args:
        player_elo (int): The player's Elo rating.
        leaderboard_id (str): The ID of the leaderboard to get the rank for.
        ranks (List[LeaderboardRank]): A list of LeaderboardRank objects representing the ranks.

    Returns:
        LeaderboardRank: The rank for the player based on their Elo rating.
    """
    player_rank = None
    least_distance_above_min_elo = float('inf')
    for rank in ranks:
        distance = player_elo - rank.min_elo
        if distance >= 0 and distance <= least_distance_above_min_elo and rank.leaderboard_id == leaderboard_id:
            least_distance_above_min_elo = distance
            player_rank = rank

    return player_rank
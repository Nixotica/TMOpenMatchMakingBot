from asyncio import sleep
import logging
from typing import List, Optional
from models.leaderboard_rank import LeaderboardRank
from discord.ext import commands
from discord.user import User

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


async def get_discord_user(
        bot: commands.Bot,
        discord_account_id: int,
) -> Optional[User]:
    """Get a discord user by their discord account id. First attempts to access cache, then 
    falls back to calling the API. 

    Args:
        bot (commands.Bot): _description_
        discord_account_id (int): _description_

    Returns:
        Optional[User]: _description_
    """ 

    user = bot.get_user(discord_account_id)
    
    if user is not None:
        return user
    
    logging.info(f"User {discord_account_id} not found in cache, attempting to fetch from discord API...")
    
    retries = 3
    for i in range(retries):
        try:
            user = await bot.fetch_user(discord_account_id)
            if user is not None:
                return user
            
            logging.error(f"Failed to find user {discord_account_id} from discord API.")
            return None
        except Exception as e:
            i += 1
            logging.error(f"Failed to fetch user {discord_account_id} from discord API with error {e}, retrying... ({i}/{retries})")
            await sleep(1)
            continue

    return None
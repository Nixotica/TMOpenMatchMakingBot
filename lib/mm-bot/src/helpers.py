from asyncio import sleep
import logging
from typing import List, Optional

import discord
from aws.s3 import S3ClientManager
from cogs.constants import COG_PARTY_MANAGER
from matchmaking.party.party_manager import PartyManager
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


def get_next_rank_for_player(
    player_elo: int,
    leaderboard_id: str,
    ranks: List[LeaderboardRank],
) -> Optional[LeaderboardRank]:
    """
    Get the next rank for a player based on their Elo rating and the list of ranks.

    Args:
        player_elo (int): The player's Elo rating.
        leaderboard_id (str): The ID of the leaderboard to get the rank for.
        ranks (List[LeaderboardRank]): A list of LeaderboardRank objects representing the ranks.

    Returns:
        LeaderboardRank: The next rank for the player based on their Elo rating.
    """
    next_rank_for_player = None
    least_distance_below_min_elo = float('inf')
    for rank in ranks:
        distance = rank.min_elo - player_elo
        if distance >= 0 and distance <= least_distance_below_min_elo and rank.leaderboard_id == leaderboard_id:
            least_distance_below_min_elo = distance
            next_rank_for_player = rank

    return next_rank_for_player


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


async def get_ping_channel(
    bot: commands.Bot,
    s3_manager: S3ClientManager,
) -> Optional[discord.TextChannel]:
    """Gets the ping channel for generic bot messages (not queue-specific)

    Args:
        bot (commands.Bot): The discord bot
        s3_manager (S3ClientManager): The s3 client manager for retrieving configs

    Returns:
        Optional[discord.TextChannel]: _description_
    """
    configs = s3_manager.get_configs()
    ping_channel_id = configs.bot_messages_channel_id

    if ping_channel_id is None:
        logging.error("No ping channel set.")
        return
    
    ping_channel = bot.get_channel(ping_channel_id)
    if ping_channel is None:
        logging.error(f"Ping channel not found with ID {ping_channel_id}.")
        return
    if not isinstance(ping_channel, discord.TextChannel):
        logging.error(f"Channel {ping_channel_id} is not a text channel.")
        return
    
    return ping_channel


async def get_party_channel(
    bot: commands.Bot,
    s3_manager: S3ClientManager,
) -> Optional[discord.TextChannel]:
    """Gets the party channel for party messages.

    Args:
        bot (commands.Bot): The discord bot
        s3_manager (S3ClientManager): The s3 client manager for retrieving configs

    Returns:
        Optional[discord.TextChannel]: _description_
    """
    configs = s3_manager.get_configs()
    party_channel_id = configs.party_channel_id

    if party_channel_id is None:
        logging.error("No party channel set.")
        return

    party_channel = bot.get_channel(party_channel_id)
    if party_channel is None:
        logging.error(f"Party channel not found with ID {party_channel_id}.")
        return
    if not isinstance(party_channel, discord.TextChannel):
        logging.error(f"Channel {party_channel_id} is not a text channel.")
        return

    return party_channel

async def safe_delete_message(message: discord.Message) -> None:
    """Delete message safely, catching errors"""
    try:
        await message.delete()
    except discord.NotFound:
        logging.info("Message already deleted.")
    except discord.Forbidden:
        logging.warning("Bot lacks permission to delete messages.")
    except Exception as e:
        logging.error(f"Unexpected error deleting message: {e}")
        
def get_party_manager(bot: commands.Bot) -> Optional[PartyManager]:
    """Gets party manager singleton if initialized, else returns None."""
    party_manager = bot.get_cog(COG_PARTY_MANAGER)
    if not party_manager:
        logging.warning("Error retrieving party manager.")
        return None
    return party_manager
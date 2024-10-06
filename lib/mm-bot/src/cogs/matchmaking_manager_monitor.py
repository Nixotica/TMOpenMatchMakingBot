import logging
from typing import Dict, List
import discord
from aws.dynamodb import DynamoDbManager
from discord.ext import commands, tasks
from models.player_profile import PlayerProfile
from models.player_elo import PlayerElo
from matchmaking.match_queues.matchmaking_manager import MatchmakingManager

class MonitorMatchmakingManager(commands.Cog):
    """ 
    Cog monitoring the matchmaking queue and determining when to ping players. 
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.matchmaking_manager = MatchmakingManager()
        self.ddb_manager = DynamoDbManager()

    def cog_load(self):
        logging.info("Matchmaking Manager Monitor loading...")
        self.check_for_new_matches.start() 
        self.check_for_completed_matches.start()

    def cog_unload(self):
        """Stop the task when the cog is unloaded."""
        logging.info("Matchmaking Manager Monitor unloading...")
        self.check_for_new_matches.cancel()
        self.check_for_completed_matches.cancel()

    async def send_player_match_start_notification(self, player: PlayerProfile, match_join_link: str | None) -> None:
        try:
            user = await self.bot.fetch_user(player.discord_account_id)
            if match_join_link is None:
                await user.send(f"Your match has been created, join with the Events tab in-game. Good luck!")
            else:
                await user.send(f"You got a match, join link: {match_join_link}. Good luck!")
        except Exception as e:
            logging.error(f"Error sending message to {player.discord_account_id}: {e}")

    async def send_player_match_complete_notification(self, player: PlayerProfile, leaderboard_to_elos_and_diffs: Dict[str, tuple[int, int]]) -> None:
        """Sends a player a match complete notification with their updated elo and difference for each leaderboard the match queue is in.

        Args:
            player (PlayerProfile): The player to send the notification to
            leaderboard_to_elos_and_diffs (Dict[str, tuple[int, int]]): A dictionary mapping leaderboard ID to a tuple of player elo and elo difference.
        """
        try:
            user = await self.bot.fetch_user(player.discord_account_id)
            match_finished_msg = "Your match has finished!\n"
            
            for (leaderboard, (updated_elo, elo_diff)) in leaderboard_to_elos_and_diffs.items():
                elo_diff_prefix = "+" if elo_diff >= 0 else "-"
                match_finished_msg += f"{leaderboard}: {updated_elo} ({elo_diff_prefix}{elo_diff})\n"
            
            await user.send(f"Your match has finished! New elo: {updated_elo} ({elo_diff_prefix}{elo_diff})")
        except Exception as e:
            logging.error(f"Error sending message to {player.discord_account_id}: {e}")

    @tasks.loop(seconds=10)  # Run every 10 seconds
    async def check_for_new_matches(self):
        """Periodically checks if new matches have been created."""
        logging.debug(f"Bot checking for new matches...")
        new_matches = self.matchmaking_manager.process_new_active_matches()

        for match in new_matches:
            logging.info(f"New match {match.match_id}, notifying players.")
            match_join_link = match.get_match_join_link()
            # Notify the players in the match
            if isinstance(match.player_profiles, List):
                for player in match.player_profiles:
                    await self.send_player_match_start_notification(player, match_join_link)
            else:
                await self.send_player_match_start_notification(match.player_profiles.team_a.player_a, match_join_link)
                await self.send_player_match_start_notification(match.player_profiles.team_a.player_b, match_join_link)
                await self.send_player_match_start_notification(match.player_profiles.team_b.player_a, match_join_link)
                await self.send_player_match_start_notification(match.player_profiles.team_b.player_b, match_join_link)

    @tasks.loop(seconds=10)  # Run every 10 seconds
    async def check_for_completed_matches(self):
        """Periodically checks if matches have been completed."""
        logging.debug(f"Bot checking for completed matches...")
        completed_matches = self.matchmaking_manager.process_completed_matches()

        for match in completed_matches:
            logging.info(f"Match {match.active_match.match_id} is completed, processing...")
            # Upload to match results table
            self.ddb_manager.put_match_results(
                match.active_match.match_queue.queue_id,
                match.active_match.match_id,
                match.active_match.match_live_id,
                match.time_completed,
                match.match_results.__str__(),
            )
            match.cleanup()

            # Notify the players in the match
            if isinstance(match.active_match.player_profiles, List):
                # Create a mapping from player profile -> dict of leaderboard id -> (updated elo, elo diff)
                player_profile_to_leaderboard_elo_update_and_diff_map: Dict[PlayerProfile, Dict[str, tuple[int, int]]] = {}

                for player_profile in match.active_match.player_profiles:
                    leaderboards_to_elo_update_and_diff_map: Dict[str, tuple[int, int]] = {}
                    for leaderboard_id in match.active_match.match_queue.leaderboard_ids: # type: ignore
                        # Find the updated elo rating for this player on this leaderboard
                        updated_elo = None
                        for updated_elo_rating in match.updated_elo_ratings:
                            if updated_elo_rating.tm_account_id == player_profile.tm_account_id and updated_elo_rating.leaderboard_id == leaderboard_id:
                                updated_elo = updated_elo_rating.elo
                        elo_diff = None
                        for elo_diff_rating in match.elo_differences:
                            if elo_diff_rating.tm_account_id == player_profile.tm_account_id and elo_diff_rating.leaderboard_id == leaderboard_id:
                                elo_diff = elo_diff_rating.elo

                        if not updated_elo or not elo_diff:
                            logging.error(f"Could not find updated elo or elo diff for player {player_profile.tm_account_id} on leaderboard {leaderboard_id}")
                            continue
                        leaderboards_to_elo_update_and_diff_map[leaderboard_id] = (updated_elo, elo_diff)

                    # Add all the leaderboards' updated elos and differences to the map
                    player_profile_to_leaderboard_elo_update_and_diff_map[player_profile] = leaderboards_to_elo_update_and_diff_map

                # Now add the updated elos back to the elo table for each leaderboard
                for player_profile, updated_elos_by_leaderboard_id in player_profile_to_leaderboard_elo_update_and_diff_map.items():
                    for leaderboard_id, (updated_elo, elo_diff) in updated_elos_by_leaderboard_id.items():
                        self.ddb_manager.update_player_elo(player_profile.tm_account_id, leaderboard_id, updated_elo)

                # Finally notify players
                for (player_profile, updated_elos_by_leaderboard_id) in player_profile_to_leaderboard_elo_update_and_diff_map.items():
                    await self.send_player_match_complete_notification(player_profile, updated_elos_by_leaderboard_id)
            else:
                # TODO - elo calculation for 2v2
                pass
                # await self.send_player_match_complete_notification(match.active_match.player_profiles.team_a.player_a, 0, 0)
                # await self.send_player_match_complete_notification(match.active_match.player_profiles.team_a.player_b, 0, 0)
                # await self.send_player_match_complete_notification(match.active_match.player_profiles.team_b.player_a, 0, 0)
                # await self.send_player_match_complete_notification(match.active_match.player_profiles.team_b.player_b, 0, 0)

    @check_for_new_matches.before_loop
    async def before_check_for_new_matches(self):
        """Wait until the bot is ready before starting the loop."""
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(MonitorMatchmakingManager(bot))
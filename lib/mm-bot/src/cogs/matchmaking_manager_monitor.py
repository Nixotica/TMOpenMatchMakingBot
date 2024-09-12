import logging
from typing import List
import discord
from aws.dynamodb import DynamoDbManager
from discord.ext import commands, tasks
from models.player_profile import PlayerProfile
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
        user = await self.bot.fetch_user(player.discord_account_id)
        if match_join_link is None:
            await user.send(f"Your match has been created, join with the Events tab in-game. Good luck!")
        else:
            await user.send(f"You got a match, join link: {match_join_link}. Good luck!")

    async def send_player_match_complete_notification(self, player: PlayerProfile, updated_elo: int, elo_diff: int) -> None:
        user = await self.bot.fetch_user(player.discord_account_id)
        elo_diff_prefix = "+" if elo_diff >= 0 else "-"
        await user.send(f"Your match has finished! New elo: {updated_elo} ({elo_diff_prefix}{elo_diff})")

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
            self.ddb_manager.put_match_results(match)
            match.cleanup()

            # Notify the players in the match
            if isinstance(match.active_match.player_profiles, List):
                for player in match.active_match.player_profiles:
                    updated_elo = match.updated_elo_ratings.get(player)
                    elo_diff = match.elo_differences.get(player)

                    if not updated_elo or not elo_diff:
                        logging.warning(f"Player {player} not found in updated_elo_ratings or elo_differences, not updating their elo...")
                        continue

                    self.ddb_manager.update_player_profile_match_complete(player.tm_account_id, updated_elo)

                    await self.send_player_match_complete_notification(player, updated_elo, elo_diff)
            else:
                # TODO - elo calculation for 2v2
                await self.send_player_match_complete_notification(match.active_match.player_profiles.team_a.player_a, 0, 0)
                await self.send_player_match_complete_notification(match.active_match.player_profiles.team_a.player_b, 0, 0)
                await self.send_player_match_complete_notification(match.active_match.player_profiles.team_b.player_a, 0, 0)
                await self.send_player_match_complete_notification(match.active_match.player_profiles.team_b.player_b, 0, 0)

    @check_for_new_matches.before_loop
    async def before_check_for_new_matches(self):
        """Wait until the bot is ready before starting the loop."""
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(MonitorMatchmakingManager(bot))
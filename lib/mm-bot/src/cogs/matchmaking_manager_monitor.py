import logging
import discord
from discord.ext import commands, tasks
from matchmaking.match_queues.matchmaking_manager import MatchmakingManager

class MonitorMatchmakingManager(commands.Cog):
    """ 
    Cog monitoring the matchmaking queue and determining when to ping players. 
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.matchmaking_manager = MatchmakingManager()
        self.check_for_new_matches.start()  # Start the task when the cog is loaded
        self.check_for_completed_matches.start()

    def cog_unload(self):
        """Stop the task when the cog is unloaded."""
        self.check_for_new_matches.cancel()

    @tasks.loop(seconds=10)  # Run every 10 seconds
    async def check_for_new_matches(self):
        """Periodically checks if new matches have been created."""
        logging.debug(f"Bot checking for new matches...")
        new_matches = self.matchmaking_manager.process_new_active_matches()

        for match in new_matches:
            match_join_link = match.get_match_join_link()
            # Notify the players in the match
            for player in match.player_profiles:
                user = await self.bot.fetch_user(player.discord_account_id)
                await user.send(f"You got a match: {match_join_link}! Good luck!")

    @tasks.loop(seconds=10)  # Run every 10 seconds
    async def check_for_completed_matches(self):
        """Periodically checks if matches have been completed."""
        logging.debug(f"Bot checking for completed matches...")
        completed_matches = self.matchmaking_manager.process_completed_matches()

        for match in completed_matches:
            # Notify the players in the match
            for player in match.player_profiles:
                user = self.bot.fetch_user(player.discord_account_id)
                user.send(f"Your match has been completed. Good job!")

    @check_for_new_matches.before_loop
    async def before_check_for_new_matches(self):
        """Wait until the bot is ready before starting the loop."""
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(MonitorMatchmakingManager(bot))
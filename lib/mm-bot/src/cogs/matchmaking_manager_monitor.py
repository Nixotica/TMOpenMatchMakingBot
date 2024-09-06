import discord
from discord.ext import commands, tasks
from matchmaking.match_queues.matchmaking_manager import MatchmakingManager

class MonitorMatchmakingManager(commands.Cog):
    """ 
    Cog monitoring the matchmaking queue and determining when to ping players. 
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.matchmaking_manager = MatchmakingManager()  # type: ignore 
        self.check_for_new_matches.start()  # Start the task when the cog is loaded

    def cog_unload(self):
        """Stop the task when the cog is unloaded."""
        self.check_for_new_matches.cancel()

    @tasks.loop(seconds=10)  # Run every 10 seconds
    async def check_for_new_matches(self):
        """Periodically checks if new matches have been created."""
        new_matches = self.matchmaking_manager.process_new_active_matches()

        for match in new_matches:
            # Notify the players in the match
            for player in match.player_profiles:
                user = self.bot.fetch_user(player.discord_account_id)
                user.send(f"You got a match! Good luck!")

    @tasks.loop(seconds=10)  # Run every 10 seconds
    async def check_for_completed_matches(self):
        """Periodically checks if matches have been completed."""
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

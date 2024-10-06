from datetime import datetime
import logging
from discord import ui
from discord.ext import commands, tasks
import discord
from aws.dynamodb import DynamoDbManager

class LeaderboardView(ui.View):
    """ 
    A view for a leaderboard including a button to query personal position as a view. 
    """
    def __init__(self, bot: commands.Bot, leaderboard_id: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.ddb_manager = DynamoDbManager()
        self.leaderboard_id = leaderboard_id

    async def start_task(self, message: discord.message.Message) -> None:
        """Pass-through for cog to give the view the pre-loaded embed message to retain and update. 

        Args:
            message (discord.message.Message): The message containing the leaderboard embed.
        """
        self.message = message
        self.update_embed.start()

    async def stop_task(self) -> None:
        """
        Unloads the view.
        """
        await self.message.delete()

    @tasks.loop(minutes=15)
    async def update_embed(self) -> None:
        """Updates the embed with the latest global leaderboard state.
        """
        logging.debug(f"Updating embed for leaderboard: {self.leaderboard_id}.")

        players_sorted_by_elo = self.ddb_manager.get_players_by_elo_descending(self.leaderboard_id)

        top_25_players = players_sorted_by_elo[:min(len(players_sorted_by_elo), 25)] 

        embed = discord.Embed(title=f"Leaderboard - {self.leaderboard_id} (Updated {datetime.utcnow()}UTC)")
        player_pos = 1
        for player in top_25_players:
            player_profile = self.ddb_manager.query_player_profile_for_tm_account_id(player.tm_account_id)

            if player_profile is None:
                logging.error(f"No player profile found for TM account ID {player.tm_account_id} while updating leaderboard...")
                continue

            player_discord_name = await self.bot.fetch_user(player_profile.discord_account_id)
            
            guild = self.message.guild
            
            if guild is not None:
                guild_member = guild.get_member(player_profile.discord_account_id)
                if guild_member is not None:
                    player_discord_name = guild_member.display_name                

            embed.add_field(name=f"{player_pos}. {player_discord_name}", value=f"{player.elo}")
            
            player_pos += 1

        await self.message.edit(embed=embed)
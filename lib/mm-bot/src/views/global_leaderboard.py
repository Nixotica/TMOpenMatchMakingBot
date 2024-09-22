import logging
from discord import ui
from discord.ext import commands
import discord
from aws.dynamodb import DynamoDbManager

class GlobalLeaderboardView(ui.View):
    """ 
    A view for the global leaderboard including a button to query personal position as a view. 
    """
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.ddb_manager = DynamoDbManager()

    async def give_message(self, message: discord.message.Message) -> None:
        """Pass-through for cog to give the view the pre-loaded embed message to retain and update.

        Args:
            message (discord.message.Message): The message containing the leaderboard embed.
        """
        self.message = message

    async def unload(self) -> None:
        """
        Unloads the view.
        """
        await self.message.delete()

    async def update_embed(self) -> None:
        """Updates the embed with the latest global leaderboard state.
        """
        logging.debug("Updating embed for global leaderboard.")

        players = self.ddb_manager.get_player_profiles()
        
        players_sorted_by_elo = sorted(players, key=lambda x: x.elo, reverse=True)

        top_25_players = players_sorted_by_elo[:min(len(players), 25)] 

        embed = discord.Embed(title="Global Leaderboard")
        player_pos = 1
        for player in top_25_players:
            player_discord_name = await self.bot.fetch_user(player.discord_account_id)
            
            guild = self.message.guild
            
            if guild is not None:
                guild_member = guild.get_member(player.discord_account_id)
                if guild_member is not None:
                    player_discord_name = guild_member.display_name                

            embed.add_field(name=f"{player_pos}. {player_discord_name}", value=f"{player.elo}", inline=False)
            
            player_pos += 1

        await self.message.edit(embed=embed)
from datetime import datetime
import logging
from discord import ui
from discord.ext import commands, tasks
import discord
from aws.dynamodb import DynamoDbManager
from helpers import get_discord_user, get_next_rank_for_player, get_rank_for_player
from cogs.constants import COLOR_EMBED


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

    @ui.button(label="See my Position", style=discord.ButtonStyle.blurple)
    async def see_my_position(self, interaction: discord.Interaction, button: ui.Button):
        user = interaction.user

        logging.info(
            f"Processing button pressed to see my position in leaderboard {self.leaderboard_id} for user {user.name}"
        )

        # Also just update the embed to avoid any confusing instances where player sees different rank in response from leaderboard
        await self.update_embed()

        player_profile = self.ddb_manager.query_player_profile_for_discord_account_id(
            user.id
        )

        if not player_profile:
            await interaction.response.send_message(
                f"You have not registered your account yet.",
                ephemeral=True,
            )
            return
        
        (first_listed_player_pos, nearby_players) = self.ddb_manager.get_nearby_players_by_elo(
            self.leaderboard_id, player_profile.tm_account_id
        )

        if nearby_players == []:
            await interaction.response.send_message(
                f"Error finding you in the leaderboard.",
                ephemeral=True,
            )
            return
        
        player_pos = -1
        for i, player in enumerate(nearby_players):
            if player.tm_account_id == player_profile.tm_account_id:
                player_pos = first_listed_player_pos + i
                break

        if player_pos == -1:
            await interaction.response.send_message(
                f"Error finding you in the leaderboard.",
                ephemeral=True,
            )
            return
        
        # Display the list of players around player
        nearby_players_name = "Leaderboard:"
        nearby_players_value = ""
        pos = first_listed_player_pos
        for player in nearby_players:
            player_profile = self.ddb_manager.query_player_profile_for_tm_account_id(player.tm_account_id)
            
            if not player_profile:
                nearby_players_value += f"**{pos}.** ({player.elo}) Deregistered Account\n"
            else:
                nearby_players_value += f"**{pos}.** ({player.elo}) <@{player_profile.discord_account_id}>\n"

            pos += 1

        # Display how much further player is away from their next rank
        player_elo = nearby_players[player_pos - first_listed_player_pos]
        leaderboard_ranks_descending = self.ddb_manager.get_ranks_for_leaderboard_by_min_elo_descending(self.leaderboard_id)
        
        embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())
        embed.add_field(name=nearby_players_name, value=nearby_players_value, inline=False)
        
        next_rank = get_next_rank_for_player(player_elo.elo, self.leaderboard_id, leaderboard_ranks_descending)
        
        if next_rank is not None:
            next_rank_name = "Next Rank:"
            next_rank_value = f"{next_rank.display_name} - {next_rank.min_elo} ({next_rank.min_elo - player_elo.elo} away)"

            embed.add_field(name=next_rank_name, value=next_rank_value, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @tasks.loop(minutes=5)
    async def update_embed(self) -> None:
        """Updates the embed with the latest leaderboard state."""
        logging.debug(f"Updating embed for leaderboard: {self.leaderboard_id}.")

        leaderboard = self.ddb_manager.query_leaderboard_by_id(self.leaderboard_id)

        if leaderboard is None:
            logging.error(
                f"When updating LeaderboardView embed, leaderboard {self.leaderboard_id} was not found."
            )
            return

        leaderboard_name = leaderboard.display_name if leaderboard.display_name else leaderboard.leaderboard_id
        embed = discord.Embed(
            title=f"Leaderboard - {leaderboard_name}",
            color=COLOR_EMBED,
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text="Last updated")

        top_25_player_elos = self.ddb_manager.get_top_25_players_by_elo(
            self.leaderboard_id
        )

        if len(top_25_player_elos) == 0:
            logging.warning(
                f"No players found for leaderboard {self.leaderboard_id} while updating leaderboard..."
            )
            await self.message.edit(embed=embed)
            return

        leaderboard_ranks_descending = self.ddb_manager.get_ranks_for_leaderboard_by_min_elo_descending(self.leaderboard_id)
        logging.info(f"Leaderboard ranks: {leaderboard_ranks_descending}")
        prev_player_rank = get_rank_for_player(
            top_25_player_elos[0].elo, self.leaderboard_id, leaderboard_ranks_descending
        )
        logging.info(f"Initial player rank: {prev_player_rank} for player {top_25_player_elos[0]}")

        if prev_player_rank is None:
            logging.error(
                f"No rank found for player with elo {top_25_player_elos[0].elo} while updating leaderboard..."
            )
            return

        player_pos = 1
        rank_group_msg = ""
        for player_elo in top_25_player_elos:
            player_rank = get_rank_for_player(
                player_elo.elo, self.leaderboard_id, leaderboard_ranks_descending
            )
            if player_rank is None:
                logging.error(
                    f"No rank found for player with elo {player_elo.elo} while updating leaderboard, skipping..."
                )
                continue
            
            # If this is a new section of players of same rank, complete the previous section using the rank above
            if player_rank != prev_player_rank:
                embed.add_field(
                    name=prev_player_rank.display_name, value=rank_group_msg,
                )
                rank_group_msg = ""
                prev_player_rank = player_rank

            player_profile = self.ddb_manager.query_player_profile_for_tm_account_id(
                player_elo.tm_account_id
            )

            if player_profile is None:
                logging.error(
                    f"No player profile found for TM account ID {player_elo.tm_account_id} while updating leaderboard..."
                )
                continue

            rank_group_msg += f"**{player_pos}.** ({player_elo.elo}) <@{player_profile.discord_account_id}>\n"

            player_pos += 1

        # Final section of message
        embed.add_field(
            name=prev_player_rank.display_name, value=rank_group_msg, inline=False,
        )

        await self.message.edit(embed=embed)

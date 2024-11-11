from datetime import datetime
import logging
from discord import ui
from discord.ext import commands, tasks
import discord
from aws.dynamodb import DynamoDbManager
from helpers import get_rank_for_player
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

    @tasks.loop(minutes=15)
    async def update_embed(self) -> None:
        """Updates the embed with the latest leaderboard state."""
        logging.debug(f"Updating embed for leaderboard: {self.leaderboard_id}.")

        embed = discord.Embed(
            title=f"Leaderboard - {self.leaderboard_id}",
            color=COLOR_EMBED,
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text="Last updated")

        players_sorted_by_elo = self.ddb_manager.get_players_by_elo_descending(
            self.leaderboard_id
        )

        if len(players_sorted_by_elo) == 0:
            logging.warning(
                f"No players found for leaderboard {self.leaderboard_id} while updating leaderboard..."
            )
            await self.message.edit(embed=embed)
            return

        top_25_player_elos = players_sorted_by_elo[: min(len(players_sorted_by_elo), 25)]

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

            player_discord_name = await self.bot.fetch_user(
                player_profile.discord_account_id
            )

            guild = self.message.guild

            if guild is not None:
                guild_member = guild.get_member(player_profile.discord_account_id)
                if guild_member is not None:
                    player_discord_name = guild_member.display_name

            rank_group_msg += f"**{player_pos}.** ({player_elo.elo}) {player_discord_name}\n"

            player_pos += 1

        # Final section of message
        embed.add_field(
            name=prev_player_rank.display_name, value=rank_group_msg, inline=False,
        )

        await self.message.edit(embed=embed)

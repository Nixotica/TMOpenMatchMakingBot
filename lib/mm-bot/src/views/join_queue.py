from datetime import datetime
import logging
from typing import Dict, List, Optional
import discord
from discord import TextChannel, ui
from discord.ext import tasks, commands
from cogs.constants import COLOR_EMBED
from helpers import get_rank_for_player
from matchmaking.match_queues.enum import QueueType
from matchmaking.match_queues.matchmaking_manager import MatchmakingManager
from aws.dynamodb import DynamoDbManager
from matchmaking.matches.active_match import ActiveMatch
from matchmaking.matches.team_2v2 import Teams2v2
from cogs.party_manager import get_party_manager
from models.leaderboard_rank import LeaderboardRank
from models.player_profile import PlayerProfile


class MatchQueueView(ui.View):
    """
    A view for joining and leaving a matchmaking queue, plus the players in the queue and active queues. 
    """

    def __init__(self, bot: commands.Bot, queue_id: str, channel: TextChannel):
        super().__init__(timeout=None)
        self.bot = bot
        self.mm_manager = MatchmakingManager()
        self.ddb_manager = DynamoDbManager()
        self.queue_id = queue_id
        self.channel = channel
        self.active_match_messages: Dict[int, discord.message.Message] = {}
        self.prev_num_queued_players: int = -1

    async def start_task(self, message: discord.message.Message):
        self.active_queue_message = message
        self.update_embed_task = self.update_queue_embed.start()
        self.update_active_matches_embeds_task = self.update_active_matches_embeds.start()

    async def stop_task(self):
        await self.active_queue_message.delete()
        for (_, message) in self.active_match_messages.items():
            await message.delete()
            
    @ui.button(label="Join Queue", style=discord.ButtonStyle.green)
    async def join_queue(self, interaction: discord.Interaction, button: ui.Button):
        user = interaction.user

        logging.info(
            f"Processing button pressed to join queue {self.queue_id} for user {user.name}"
        )

        player_profile = self.ddb_manager.query_player_profile_for_discord_account_id(
            user.id
        )

        if not player_profile:
            await interaction.response.send_message(
                f"You have not registered your account yet.", ephemeral=True
            )
            return
        
        if self.mm_manager.is_player_in_match(player_profile):
            await interaction.response.send_message(
                f"You are already in a match.", ephemeral=True
            )
            return
        
        with_teammate: Optional[PlayerProfile] = None
        
        # Handle partied players joining queue.
        party_manager = get_party_manager(self.bot)
        if party_manager:
            player_party = party_manager.get_player_party(player_profile)
        if player_party is not None:
            queue = self.mm_manager.get_active_queue_by_id(self.queue_id)
            if not queue:
                logging.warning(f"Unexpectedly could not find queue with ID {self.queue_id} in mm manager.")
                return
            
            # If this is a solo queue, do not allow player to join
            if queue.queue.type != QueueType.Queue2v2:
                await interaction.response.send_message(
                    f"This queue does not allowed partied players. Use /unparty first!", ephemeral=True
                )
                return

            # If their teammate is in a match, warn them and do not allow them to join
            teammate = player_party.teammate(player_profile)
            if self.mm_manager.is_player_in_match(teammate):
                await interaction.response.send_message(
                    f"Your teammate <@{teammate.discord_account_id}> is still in a match.", ephemeral=True
                )
                return
            
            added_queue = self.mm_manager.add_party_to_queue(player_party, self.queue_id)
            with_teammate = teammate

        # Otherwise solo queueing
        else:
            added_queue = self.mm_manager.add_player_to_queue(player_profile, self.queue_id)

        if not added_queue:
            await interaction.response.send_message(
                f"Failed to join queue {self.queue_id}.", ephemeral=True
            )
            return

        with_teammate_msg = f" with <@{with_teammate.discord_account_id}>" if with_teammate else ""
        await interaction.response.send_message(
            f"Joined queue {self.queue_id}{with_teammate_msg}.", ephemeral=True
        )

        await self.update_queue_embed()

    @ui.button(label="Leave Queue", style=discord.ButtonStyle.red)
    async def leave_queue(self, interaction: discord.Interaction, button: ui.Button):
        user = interaction.user

        logging.info(
            f"Processing button pressed to leave queue {self.queue_id} for user {user.name}"
        )

        player_profile = self.ddb_manager.query_player_profile_for_discord_account_id(
            user.id
        )

        if not player_profile:
            # Don't tell the user anything, they probably aren't registered
            return

        requested_queue = self.mm_manager.get_active_queue_by_id(self.queue_id)

        if not requested_queue:
            logging.error(
                f"When attempting to leave queue {self.queue_id}, queue was not found."
            )
            return

        player_profiles = []
        for party in requested_queue.player_parties:
            for player in party.players():
                player_profiles.append(player)

        if player_profile not in player_profiles:
            await interaction.response.send_message(
                f"You are not in queue {self.queue_id}.", ephemeral=True
            )
            return

        party_manager = get_party_manager(self.bot)
        if party_manager:
            player_party = party_manager.get_player_party(player_profile)
        if player_party is not None:
            self.mm_manager.remove_party_from_queue(player_party, self.queue_id)
        else:
            self.mm_manager.remove_player_from_queue(player_profile, self.queue_id)

        await interaction.response.send_message(
            f"Left queue {self.queue_id}.", ephemeral=True
        )

        await self.update_queue_embed()

    @tasks.loop(seconds=15)
    async def update_queue_embed(self) -> None:
        logging.debug(f"Updating embed for queue {self.queue_id}.")

        queue = self.mm_manager.get_active_queue_by_id(self.queue_id)

        if queue is None:
            logging.error(
                f"When updating MatchQueueView embed, queue {self.queue_id} was not found."
            )
            raise ValueError(f"Queue {self.queue_id} not found.")

        num_players = 0
        for party in queue.player_parties:
            num_players += len(party.players())

        # If the number of players hasn't changed, don't bother updating the queue. 
        if num_players == self.prev_num_queued_players:
            logging.debug(f"Number of players in queue {self.queue_id} has not changed, skipping update.")
            return
        self.prev_num_queued_players = num_players

        queue_name = queue.queue.display_name if queue.queue.display_name else queue.queue.queue_id
        embed = discord.Embed(
            title=f"Better Matchmaking Queue - {queue_name}",
            color=COLOR_EMBED,
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text="Last updated")

        leaderboard_id = queue.queue.primary_leaderboard_id
        if leaderboard_id is None or num_players == 0:
            embed.add_field(name="Players:", value=num_players)
        else:
            leaderboard_ranks = self.ddb_manager.get_ranks_for_leaderboard_by_min_elo_descending(
                leaderboard_id
            )
            ranks_to_count: Dict[LeaderboardRank, int] = {}
            for party in queue.player_parties:
                for player in party.players():
                    player_elo = self.ddb_manager.get_or_create_player_elo(
                        player.tm_account_id,
                        leaderboard_id,
                    )
                    rank = get_rank_for_player(player_elo.elo, leaderboard_id, leaderboard_ranks)
                    if rank is None:
                        logging.error(f"Failed to get rank for player {player_elo.tm_account_id} with elo {player_elo.elo} on leaderboard {leaderboard_id}.")
                        continue
                    if ranks_to_count.get(rank) is None:
                        ranks_to_count[rank] = 1
                    else:
                        ranks_to_count[rank] += 1

            value = ""
            for rank in leaderboard_ranks:
                if ranks_to_count.get(rank) is None:
                    continue
                value += f"{rank.display_name}: {ranks_to_count[rank]}\n"

            embed.add_field(name="Players:", value=value)
        try:
            await self.active_queue_message.edit(embed=embed)
        except Exception as e:
            logging.warning(f"Failed to update queue {queue_name} embed: {e}")

    async def process_new_active_solo_match(self, active_match: ActiveMatch) -> None:
        if not isinstance(active_match.player_profiles, List):
            logging.error(
                f"Expected player profiles to be a list, got {type(active_match.player_profiles)} instead."
            )
            return

        players = active_match.player_profiles

        value = ""
        for player in players:
            value += f"<@{player.discord_account_id}>\n"

        embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())
        embed.add_field(
            name=f"🏎️ Match #{active_match.bot_match_id} in progress...",
            value=value
        )

        message = await self.channel.send(embed=embed)
        self.active_match_messages[active_match.bot_match_id] = message

    async def process_new_active_teams_match(self, active_match: ActiveMatch) -> None:
        if not isinstance(active_match.player_profiles, Teams2v2):
            logging.error(
                f"Expected player profiles to be a Teams2v2, got {type(active_match.player_profiles)} instead."
            )
            return
        
        embed = discord.Embed(
            title=f"🏎️ Match #{active_match.bot_match_id} in progress...",
            color=COLOR_EMBED, 
            timestamp=datetime.utcnow()
        )

        team_a = active_match.player_profiles.team_a
        embed.add_field(
            name="Blue Team",
            value=f"<@{team_a.player_a.discord_account_id}> & <@{team_a.player_b.discord_account_id}>"
        )

        team_b = active_match.player_profiles.team_b
        embed.add_field(
            name="Red Team",
            value=f"<@{team_b.player_a.discord_account_id}> & <@{team_b.player_b.discord_account_id}>"
        )

        message = await self.channel.send(embed=embed)
        self.active_match_messages[active_match.bot_match_id] = message

    @tasks.loop(seconds=15)
    async def update_active_matches_embeds(self) -> None:
        logging.debug(f"Updating embeds for active matches in queue {self.queue_id}.")

        # Get new active matches and send the messages for them.
        new_active_matches = self.mm_manager.process_new_active_matches_for_queue(self.queue_id)

        for new_match in new_active_matches:
            if isinstance(new_match.player_profiles, List):
                await self.process_new_active_solo_match(new_match)
            elif isinstance(new_match.player_profiles, Teams2v2):
                await self.process_new_active_teams_match(new_match)
            else:
                logging.error(f"Unknown match type {type(new_match)}")
                continue

            logging.info(f"New match with bot match ID {new_match.bot_match_id} added to queue view {self.queue_id}")

        # Get completed matches and delete the messages for them.
        completed_matches = self.mm_manager.process_completed_matches_for_queue(self.queue_id)

        for completed_match in completed_matches:
            try:
                message = self.active_match_messages.pop(completed_match.active_match.bot_match_id)

                await message.delete()

                logging.info(f"Completed match with bot match ID {completed_match.active_match.bot_match_id} removed from queue view {self.queue_id}")
            except Exception as e:
                logging.error(f"Failed to delete message for completed match with bot match ID {completed_match.active_match.bot_match_id} in queue view {self.queue_id}: {e}")
                continue
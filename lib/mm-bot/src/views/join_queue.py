from datetime import datetime
import logging
from typing import Dict, List
import discord
from discord import TextChannel, ui
from discord.ext import tasks, commands
from cogs.constants import COLOR_EMBED
from matchmaking.match_queues.matchmaking_manager import MatchmakingManager
from aws.dynamodb import DynamoDbManager
from matchmaking.matches.active_match import ActiveMatch
from matchmaking.matches.team_2v2 import Teams2v2


class MatchQueueView(ui.View):
    """
    A view for joining and leaving a matchmaking queue, plus the players in the queue and active queues. 
    """

    def __init__(self, queue_id: str, channel: TextChannel):
        super().__init__(timeout=None)
        self.mm_manager = MatchmakingManager()
        self.ddb_manager = DynamoDbManager()
        self.queue_id = queue_id
        self.channel = channel
        self.active_match_messages: Dict[int, discord.message.Message] = {}

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

        added_queue = self.mm_manager.add_player_to_queue(player_profile, self.queue_id)

        if not added_queue:
            await interaction.response.send_message(
                f"Failed to join queue {self.queue_id}.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Joined queue {self.queue_id}.", ephemeral=True
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

        requested_queue = self.mm_manager.get_active_queue_by_id(self.queue_id)

        if not requested_queue:
            logging.error(
                f"When attempting to leave queue {self.queue_id}, queue was not found."
            )
            return

        player_profiles = [p.profile for p in requested_queue.players]
        if player_profile not in player_profiles:
            await interaction.response.send_message(
                f"You are not in queue {self.queue_id}.", ephemeral=True
            )
            return

        self.mm_manager.remove_player_from_queue(player_profile, self.queue_id)

        await interaction.response.send_message(
            f"Left queue {self.queue_id}.", ephemeral=True
        )

        await self.update_queue_embed()

    async def start_task(self, message: discord.message.Message):
        self.active_queue_message = message
        self.update_embed_task = self.update_queue_embed.start()
        self.update_active_matches_embeds_task = self.update_active_matches_embeds.start()

    async def stop_task(self):
        await self.active_queue_message.delete()
        for (_, message) in self.active_match_messages.items():
            await message.delete()

    @tasks.loop(seconds=15)
    async def update_queue_embed(self) -> None:
        logging.debug(f"Updating embed for queue {self.queue_id}.")

        queue = self.mm_manager.get_active_queue_by_id(self.queue_id)

        if queue is None:
            logging.error(
                f"When updating MatchQueueView embed, queue {self.queue_id} was not found."
            )
            raise ValueError(f"Queue {self.queue_id} not found.")

        num_players_in_queue = len(queue.players)

        # TODO - display player count by rank

        # TODO - display active matches count

        embed = discord.Embed(title=f"Better Matchmaking Queue - {self.queue_id}")
        embed.add_field(name="Players: ", value=num_players_in_queue)

        await self.active_queue_message.edit(embed=embed)

    @tasks.loop(seconds=15)
    async def update_active_matches_embeds(self) -> None:
        logging.debug(f"Updating embeds for active matches in queue {self.queue_id}.")

        # Get new active matches and send the messages for them.
        new_active_matches = self.mm_manager.process_new_active_matches_for_queue(self.queue_id)

        for new_match in new_active_matches:
            players = new_match.player_profiles

            # TODO - support 2v2
            if isinstance(players, Teams2v2):
                logging.error("Not implemented to handle 2v2 matches...")
                continue

            value = ""
            for player in players:
                value += f"<@{player.discord_account_id}>\n"
            
            embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())
            embed.add_field(
                name=f"🏎️ Match #{new_match.bot_match_id} in progress...",
                value=value
            )

            message = await self.channel.send(embed=embed)
            self.active_match_messages[new_match.bot_match_id] = message

            logging.info(f"New match with bot match ID {new_match.bot_match_id} added to queue view {self.queue_id}")

        # Get completed matches and delete the messages for them.
        completed_matches = self.mm_manager.process_completed_matches_for_queue(self.queue_id)

        for completed_match in completed_matches:
            message = self.active_match_messages.pop(completed_match.active_match.bot_match_id)

            await message.delete()

            logging.info(f"Completed match with bot match ID {completed_match.active_match.bot_match_id} removed from queue view {self.queue_id}")
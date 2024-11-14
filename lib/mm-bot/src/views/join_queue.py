import logging
import discord
from discord import ui
from discord.ext import tasks, commands
from matchmaking.match_queues.matchmaking_manager import MatchmakingManager
from aws.dynamodb import DynamoDbManager


class JoinQueueView(ui.View):
    """
    A view for joining and leaving a matchmaking queue, plus the players in the queue.
    """

    def __init__(self, queue_id: str):
        super().__init__(timeout=None)
        self.mm_manager = MatchmakingManager()
        self.ddb_manager = DynamoDbManager()
        self.queue_id = queue_id

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

        await self.update_embed()

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

        await self.update_embed()

    async def start_task(self, message: discord.message.Message):
        self.message = message
        self.update_embed_task = self.update_embed.start()

    async def stop_task(self):
        await self.message.delete()

    @tasks.loop(seconds=15)
    async def update_embed(self) -> None:
        logging.debug(f"Updating embed for queue {self.queue_id}.")

        queue = self.mm_manager.get_active_queue_by_id(self.queue_id)

        if queue is None:
            logging.error(
                f"When updating JoinQueueView embed, queue {self.queue_id} was not found."
            )
            raise ValueError(f"Queue {self.queue_id} not found.")

        num_players_in_queue = len(queue.players)

        # TODO - display player count by rank

        # TODO - display active matches count

        embed = discord.Embed(title=f"Better Matchmaking Queue - {self.queue_id}")
        embed.add_field(name="Players: ", value=num_players_in_queue)

        await self.message.edit(embed=embed)

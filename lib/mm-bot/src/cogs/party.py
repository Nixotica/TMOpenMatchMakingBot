import logging
import discord
from discord.ext import commands

from aws.dynamodb import DynamoDbManager
from aws.s3 import S3ClientManager
from cogs.constants import ROLE_MOD
from matchmaking.match_queues.matchmaking_manager import MatchmakingManager
from matchmaking.party.party_manager import PartyManager


class Party(commands.Cog, name="party"):
    """
    Party bot commands for setting up party message channel and allowing players to join/leave parties.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mm_manager = MatchmakingManager()
        self.ddb_manager = DynamoDbManager()
        self.s3_manager = S3ClientManager()
        self.party_manager = PartyManager()

    @commands.hybrid_command(
        name="set_party_channel",
        description="Set the channel for party requests players can accept or decline."
    )
    @commands.has_role(ROLE_MOD)
    async def set_party_channel(
        self, ctx: commands.Context, channel_id: str # Cannot be int - too long for discord bot
    ) -> None:
        logging.info(
            f"Processing command to set party channel from user {ctx.message.author.name}."
        )

        channel_id = eval(channel_id)
        if not isinstance(channel_id, int):
            await ctx.send(f"Invalid channel ID: {channel_id}.", ephemeral=True)
            return

        configs = self.s3_manager.get_configs()
        configs.party_channel_id = channel_id
        self.s3_manager.update_config(configs)

        await ctx.send(f"Party channel set to {channel_id}.", ephemeral=True)

    @commands.hybrid_command(
        name="party",
        description="Invite a player to your party."
    )
    async def party(
        self, ctx: commands.Context, member: discord.Member,
    ) -> None:
        logging.info(
            f"Processing command to invite player {member.name} to party from user {ctx.message.author.name}."
        )

        configs = self.s3_manager.get_configs()
        if not configs.party_channel_id:
            if not configs.bot_messages_channel_id:
                await ctx.send(
                    "Party channel not set. Please contact a moderator."
                )
            else:
                party_channel_id = configs.bot_messages_channel_id
        else:
            party_channel_id = configs.party_channel_id
        party_channel = self.bot.get_channel(party_channel_id)
        if party_channel is None:
            logging.error(f"Party channel not found with ID {party_channel_id}.")
            await ctx.send(
                "Party channel not found. Please contact a moderator."
            )
            return
        if not isinstance(party_channel, discord.TextChannel):
            logging.error(f"Party channel is not a text channel.")
            await ctx.send(
                "Party channel not found. Please contact a moderator."
            )
            return

        requester_profile = self.ddb_manager.query_player_profile_for_discord_account_id(
            ctx.message.author.id
        )

        if not requester_profile:
            await ctx.send(f"You must register your account first!")
            return

        accepter_profile = self.ddb_manager.query_player_profile_for_discord_account_id(
            member.id
        )

        if not accepter_profile:
            await ctx.send(f"{member.name} must register their account first!")
            return

        accept_button = discord.ui.Button(label="✅ Accept", style=discord.ButtonStyle.green)
        decline_button = discord.ui.Button(label="❌ Decline", style=discord.ButtonStyle.red)
        view = discord.ui.View()
        view.add_item(accept_button)
        view.add_item(decline_button)

        message = await party_channel.send(
            content=f"❗ <@{accepter_profile.discord_account_id}>! <@{requester_profile.discord_account_id}> has requested you to join their party.",
            view=view,
        )

        
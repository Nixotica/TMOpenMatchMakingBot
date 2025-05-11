import logging

import discord
from aws.dynamodb import DynamoDbManager
from aws.s3 import S3ClientManager
from cogs.constants import ROLE_MOD
from cogs.matchmaking_manager_v2 import get_matchmaking_manager_v2
from cogs.party_manager import get_party_manager
from discord.ext import commands

from helpers import get_party_channel


class Party(commands.Cog):
    """
    Party bot commands for setting up party message channel and allowing players to join/leave parties.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ddb_manager = DynamoDbManager()
        self.s3_manager = S3ClientManager()

        mm_manager = get_matchmaking_manager_v2()
        if mm_manager is None:
            raise ValueError(
                "Matchmaking manager, a fatally dependent resource, not found."
            )
        self.mm_manager = mm_manager

    @commands.hybrid_command(
        name="set_party_channel",
        description="Set the channel for party requests players can accept or decline.",
    )
    @commands.has_role(ROLE_MOD)
    async def set_party_channel(
        self,
        ctx: commands.Context,
        channel_id: str,  # Cannot be int - too long for discord bot
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

    @commands.hybrid_command(name="party", description="Invite a player to your party.")
    async def party(
        self,
        ctx: commands.Context,
        member: discord.Member,
    ) -> None:
        logging.info(
            f"Processing command to invite player {member.name} to party from user {ctx.message.author.name}."
        )

        requester_profile = (
            self.ddb_manager.query_player_profile_for_discord_account_id(
                ctx.message.author.id
            )
        )

        if not requester_profile:
            await ctx.send("You must register your account first!")
            return

        accepter_profile = self.ddb_manager.query_player_profile_for_discord_account_id(
            member.id
        )

        if not accepter_profile:
            await ctx.send(f"{member.name} must register their account first!")
            return

        party_manager = get_party_manager()
        if not party_manager:
            await ctx.send("Error sending party request.")
            return

        await party_manager.add_outstanding_party_request(
            requester_profile, accepter_profile
        )

        await ctx.send(f"Party request sent to {member.name}.", ephemeral=True)

    @commands.hybrid_command(name="unparty", description="Disband your party.")
    async def unparty(
        self,
        ctx: commands.Context,
    ) -> None:
        logging.info(
            f"Processing command to disband party from user {ctx.message.author.name}."
        )

        requester_profile = (
            self.ddb_manager.query_player_profile_for_discord_account_id(
                ctx.message.author.id
            )
        )

        if not requester_profile:
            await ctx.send("You must register your account first!")
            return

        party_manager = get_party_manager()
        if not party_manager:
            await ctx.send("Error attemping to unparty.")
            return

        party = party_manager.remove_party(requester_profile)
        if not party:
            await ctx.send("You are not in a party.", ephemeral=True)
            return

        # If players are in any queues, remove them
        self.mm_manager.remove_party_from_all_queues(party.players())

        # Ping the player's teammate
        teammate_discord_id = party.teammate(requester_profile).discord_account_id
        party_channel = await get_party_channel(self.bot, self.s3_manager)
        if party_channel:
            embed = discord.Embed(
                color=discord.Color.red(),
                description=f"<@{requester_profile.discord_account_id}> unpartied from you."
                f"⚠️ You must rejoin any queues you were in.",
            )
            await party_channel.send(content=f"<@{teammate_discord_id}>", embed=embed)

        await ctx.send(
            f"Unpartied from <@{teammate_discord_id}>. ⚠️ You must rejoin any queues you were in.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Party(bot))

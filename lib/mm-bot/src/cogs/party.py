import logging

import discord
from aws.dynamodb import DynamoDbManager
from aws.s3 import S3ClientManager
from cogs.constants import ROLE_MOD
from cogs.party_manager import get_party_manager
from discord.ext import commands


class Party(commands.Cog):
    """
    Party bot commands for setting up party message channel and allowing players to join/leave parties.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ddb_manager = DynamoDbManager()
        self.s3_manager = S3ClientManager()

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

        await ctx.send(
            f"Unpartied from <@{party.teammate(requester_profile).discord_account_id}>.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Party(bot))

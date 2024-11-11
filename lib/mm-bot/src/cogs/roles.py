import logging
import discord
from discord.ext import commands, tasks

from aws.dynamodb import DynamoDbManager
from aws.s3 import S3ClientManager
from models.rank_role import RankRole
from cogs.constants import ROLE_ADMIN


class Roles(commands.Cog, name="roles"):
    """
    Commands and management for creating and managing user roles.
    Includes the process of updating elo-based ranks.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ddb_manager = DynamoDbManager()
        self.s3_manager = S3ClientManager()

    @commands.hybrid_command(
        name="link_rank_role",
        description="Link a role to a minimum elo to get that role on the 'global' leaderboard.",
    )
    @commands.has_role(ROLE_ADMIN)
    async def link_rank_role(
        self, ctx: commands.Context, role: discord.Role, min_elo: int
    ) -> None:
        logging.info(
            f"Processing command to create rank role from user {ctx.message.author.name}"
        )

        if min_elo < 0:
            await ctx.send(f"Invalid minimum elo, must be greater than zero.")
            return
        
        rank_role = RankRole(role.id, role.name, min_elo)
        success = self.ddb_manager.create_rank_role(rank_role)

        if success:
            await ctx.send(
                f"Successfully created rank role {role.name} with minimum elo {min_elo}."
            )
        else:
            await ctx.send(f"Failed to create rank role {role.name}.")

    @commands.hybrid_command(
        name="refresh_player_rank",
        description="Refresh a player's rank and roles based on the 'global' leaderboard.",
    )
    @commands.has_role(ROLE_ADMIN)
    async def refresh_player_ranks(
        self, ctx: commands.Context, user: discord.Member,
    ) -> None:
        logging.info(
            f"Processing command to refresh player rank from user {ctx.message.author.name}"
        )

        try:
            member = ctx.guild.get_member(user.id) # type: ignore
            member_roles = member.roles # type: ignore
        except Exception as e:
            await ctx.send(f"Failed to get roles for user {user.name}.")
            return

        player_profile = self.ddb_manager.query_player_profile_for_discord_account_id(
            user.id
        )

        if not player_profile:
            await ctx.send(f"Player {user.name} has not registered their account yet.")
            return

        configs = self.s3_manager.get_configs()
        global_leaderboard = configs.global_leaderboard_id

        if global_leaderboard is None:
            logging.info("No global leaderboard found, not updating player rank role.")
            return

        player_elo = self.ddb_manager.get_or_create_player_elo(player_profile.tm_account_id, global_leaderboard)
        rank_roles = self.ddb_manager.get_rank_roles()

        # Find the rank role the user should have now
        new_rank_role = None
        distance_above_min_elo = 0
        for role in rank_roles:
            if player_elo.elo - role.min_elo >= distance_above_min_elo:
                distance_above_min_elo = player_elo.elo - role.min_elo
                new_rank_role = role

        if new_rank_role is None:
            await ctx.send(f"Couldn't assign a rank to user with elo {player_elo}")
            return

        # Remove user's discord roles which correspond to a rank role
        rank_role_ids = [role.rank_role_id for role in rank_roles]
        for role in member_roles:
            if role.id in rank_role_ids: # type: ignore
                await member.remove_roles(role) # type: ignore

        # Add the new role to the user
        await member.add_roles(ctx.guild.get_role(new_rank_role.rank_role_id)) # type: ignore
        logging.info(f"Updated rank role for user {player_profile.discord_account_id} to {new_rank_role.display_name}") # type: ignore


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Roles(bot))
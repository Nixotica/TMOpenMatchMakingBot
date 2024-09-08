import logging
import discord
from discord.ext import commands
from models.team_2v2 import Team2v2
from matchmaking.match_queues.matchmaking_manager import MatchmakingManager
from aws.dynamodb import DynamoDbManager

class JoinQueue(commands.Cog, name="join"):
    """
    Command for a player to join a matchmaking queue. 
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mm_manager = MatchmakingManager()
        self.ddb_manager = DynamoDbManager()

    @commands.hybrid_command(
        name="join",
        description="Join a queue for matchmaking."
    )
    async def join(self, ctx: commands.Context, queue_id: str) -> None: 
        logging.info(f"Processing command to join queue {queue_id} for user {ctx.message.author.name}.")

        player_profile = DynamoDbManager().query_player_profile_for_discord_account_id(ctx.message.author.id)

        added_queue = self.mm_manager.add_player_to_queue(player_profile, queue_id) # type: ignore

        if not added_queue:
            await ctx.send(f"Failed to join queue {queue_id}.")
            return
        await ctx.send(f"Joined queue {queue_id} along with {len(added_queue.players) - 1} others.")

    @commands.hybrid_command(
        name="join_team",
        description="Join a queue for 2v2 matchmaking."
    )
    async def join_team(self, ctx: commands.Context, queue_id: str, member: discord.Member) -> None:
        logging.info(f"Processing command to join team queue for user {ctx.message.author.name} with invite to {member}.")

        if ctx.message.author.id == member.id:
            await ctx.send(f"You cannot invite yourself to a team queue.")
            return

        inviter_profile = DynamoDbManager().query_player_profile_for_discord_account_id(ctx.message.author.id)
        invitee_profile = DynamoDbManager().query_player_profile_for_discord_account_id(member.id)

        if not inviter_profile:
            await ctx.send(f"You have not registered your account yet.")
            return

        if not invitee_profile:
            await ctx.send(f"The player you attempted to invite has not registered their account yet.")
            return
    
        await ctx.send(f"{member.mention}, {ctx.author.name} has invited you to a party! Do you accept?")
        
        # Adding buttons for accept/decline (discord.py has a Buttons library for this, or you can use reactions)
        await ctx.send(f"React with ✅ to accept or ❌ to decline.")

        # Waiting for reaction from the invited user
        def check(reaction, user):
            return user == member and str(reaction.emoji) in ["✅", "❌"]
        
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
            
            if str(reaction.emoji) == "✅":
                # Add both to the queue
                team = Team2v2(inviter_profile, invitee_profile)
                added_queue = self.mm_manager.add_team_to_queue(team, queue_id)

                if not added_queue:
                    await ctx.send(f"Failed to join queue {queue_id}.")
                    await member.send(f"Failed to join queue {queue_id}.")
                    return
                
                await ctx.send(f"{ctx.author.mention} and {member.mention} are now in the party queue!")
            else:
                await ctx.send(f"{member.name} declined the invitation.")
        except:
            await ctx.send(f"{member.name} did not respond in time.")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(JoinQueue(bot))
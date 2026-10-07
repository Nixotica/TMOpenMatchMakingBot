import logging
import time
from typing import Dict, Optional

import discord
from aws.dynamodb import DynamoDbManager
from aws.s3 import S3ClientManager
from cogs.constants import ROLE_ADMIN, ROLE_MOD
from cogs.matchmaking_manager_v2 import get_matchmaking_manager_v2
from cogs.party_manager import get_party_manager
from discord.ext import commands, tasks
from matchmaking.match_queues.constants import TEAM_BLUE
from matchmaking.matches.completed_match import CompletedMatch
from matchmaking.matches.event_creator import CreateMatchError
from matchmaking.mm_event_bus import EventType, MatchmakingManagerEventBus
from matchmaking.scrims.constants import (
    SCRIM_CHANNEL_NAME_PREFIX,
    SCRIM_CHECK_COMPLETED_MATCHES_TASK_SEC,
    SCRIM_CHECK_ROOMS_TASK_SEC,
    SCRIM_ROOM_CHANNEL_TOPIC,
    SCRIM_ROOM_INACTIVITY_SEC,
)
from matchmaking.scrims.scrim_mappack import (
    ScrimMappack,
    count_campaign_maps,
    mappacks_from_queues,
    parse_campaign_reference,
)
from matchmaking.scrims.scrim_room import ScrimRoom, ScrimRoomStatus
from models.player_profile import PlayerProfile
from views.scrim_room import (
    ScrimInviteView,
    ScrimRoomView,
    build_closed_invite_embed,
    build_invite_embed,
    build_match_ready_embed,
    build_results_embed,
    mentions,
)


class ScrimManager(commands.Cog):
    """
    Scrim rooms: private channels where a player or party sets up unranked matches with the mode
    and mappack of their choice, against players they invite by @mentioning them.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ddb_manager = DynamoDbManager()
        self.s3_manager = S3ClientManager()
        self.mm_event_bus = MatchmakingManagerEventBus()

        mm_manager = get_matchmaking_manager_v2()
        if mm_manager is None:
            raise ValueError(
                "Matchmaking manager, a fatally dependent resource, not found."
            )
        self.mm_manager = mm_manager

        # Open rooms keyed by room (channel) ID
        self.rooms: Dict[int, ScrimRoomView] = {}

        self.completed_match_sub = self.mm_event_bus.subscribe(
            EventType.NEW_COMPLETED_MATCH
        )

    def cog_load(self):
        logging.info("Scrim Manager loading...")
        self.delete_orphaned_rooms.start()
        self.check_stale_rooms.start()
        self.process_completed_matches.start()

    def cog_unload(self):
        logging.info("Scrim Manager unloading...")
        self.delete_orphaned_rooms.cancel()
        self.check_stale_rooms.cancel()
        self.process_completed_matches.cancel()

    def find_room_with_player(self, discord_account_id: int) -> Optional[ScrimRoomView]:
        for room_view in self.rooms.values():
            if room_view.room.has_player(discord_account_id):
                return room_view
        return None

    def find_room_with_match(self, bot_match_id: int) -> Optional[ScrimRoomView]:
        for room_view in self.rooms.values():
            if room_view.room.bot_match_id == bot_match_id:
                return room_view
        return None

    def get_scrim_category(self) -> Optional[discord.CategoryChannel]:
        category_id = self.s3_manager.get_configs().scrim_category_id
        if category_id is None:
            return None

        category = self.bot.get_channel(category_id)
        if not isinstance(category, discord.CategoryChannel):
            logging.error(f"Scrim category {category_id} not found.")
            return None
        return category

    def get_match_club_id(self, mappack: ScrimMappack) -> int:
        """Gets the club to host a scrim match in: the configured scrim club, or else the
        match club of the queue the mappack came from, or else that of any queue."""
        configs = self.s3_manager.get_configs()
        if configs.scrim_match_club_id is not None:
            return configs.scrim_match_club_id

        if mappack.match_club_id is not None:
            return mappack.match_club_id

        for active_queue in self.mm_manager.active_queues:
            return active_queue.queue.match_club_id

        raise ValueError(
            "There's no club to host scrim matches in. A mod needs to run /set_scrim_match_club."
        )

    def get_free_teammate(self, player: PlayerProfile) -> Optional[PlayerProfile]:
        """Gets the player's party teammate, if they have one who isn't in a scrim room yet."""
        party_manager = get_party_manager()
        if party_manager is None:
            return None

        party = party_manager.get_player_party(player)
        if party is None:
            return None

        party_manager.update_party_activity(party)
        teammate = party.teammate(player)
        if self.find_room_with_player(teammate.discord_account_id) is not None:
            return None
        return teammate

    def check_can_start_match(self, room: ScrimRoom) -> Optional[str]:
        """Gets why a room can't start a match, if it can't."""
        if room.status != ScrimRoomStatus.SETUP:
            return "A match is already starting or in progress."

        blockers = room.start_blockers()
        players_in_match = [
            player
            for player in room.players()
            if self.mm_manager.is_player_in_match(player)
        ]
        if players_in_match:
            blockers.append(f"{mentions(players_in_match)} still in another match.")

        if blockers:
            return "Can't start yet:\n" + "\n".join(f"- {b}" for b in blockers)
        return None

    async def set_room_access(
        self, room_view: ScrimRoomView, member: discord.Member, can_chat: bool
    ) -> bool:
        """Lets a member see a room, and optionally chat in it.

        Returns:
            bool: True if the member's access was set, False if discord refused.
        """
        try:
            await room_view.channel.set_permissions(
                member,
                overwrite=discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=can_chat,
                    read_message_history=True,
                ),
            )
            return True
        except Exception as e:
            logging.error(
                f"Failed to give {member.id} access to scrim room {room_view.room.room_id}: {e}"
            )
            return False

    async def remove_room_access(
        self, room_view: ScrimRoomView, discord_account_id: int
    ) -> None:
        member = room_view.channel.guild.get_member(discord_account_id)
        if member is None:
            return

        try:
            await room_view.channel.set_permissions(member, overwrite=None)
        except Exception as e:
            logging.warning(
                f"Failed to remove {discord_account_id} from scrim room {room_view.room.room_id}: {e}"
            )

    async def open_room(
        self,
        category: discord.CategoryChannel,
        host_member: discord.Member,
        host: PlayerProfile,
        teammate: Optional[PlayerProfile],
    ) -> ScrimRoomView:
        """Creates a scrim room channel for a host, and their party teammate if they have one.

        Args:
            category (discord.CategoryChannel): The category to create the room channel in.
            host_member (discord.Member): The host's discord member.
            host (PlayerProfile): The host.
            teammate (Optional[PlayerProfile]): The host's party teammate, who joins on their side.

        Returns:
            ScrimRoomView: The opened room.
        """
        guild = category.guild
        members = [host_member]
        if teammate is not None:
            teammate_member = guild.get_member(teammate.discord_account_id)
            if teammate_member is None:
                teammate = None
            else:
                members.append(teammate_member)

        # Overwrite permissions so only players in the room (and mods+) can see it
        overwrites: Dict[discord.Role | discord.Member, discord.PermissionOverwrite] = (
            {}
        )
        overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
        for role_name in (ROLE_MOD, ROLE_ADMIN):
            role = discord.utils.get(guild.roles, name=role_name)
            if role is not None:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True)
        for member in members:
            overwrites[member] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )
        overwrites[guild.me] = discord.PermissionOverwrite(
            view_channel=True,  # Needed to get responses
            send_messages=True,  # Obviously
            manage_channels=True,  # Needed to delete channel
            manage_messages=True,
            embed_links=True,  # Needed to send embeds
            use_application_commands=True,  # Needed for buttons
            read_messages=True,
            read_message_history=True,
        )

        channel = await guild.create_text_channel(
            name=f"{SCRIM_CHANNEL_NAME_PREFIX}{host_member.name}",
            category=category,
            overwrites=overwrites,  # type: ignore
            topic=SCRIM_ROOM_CHANNEL_TOPIC,
        )

        room = ScrimRoom(channel.id, host)
        room.add_player(host, TEAM_BLUE)
        if teammate is not None:
            room.add_player(teammate, TEAM_BLUE)

        mappacks = mappacks_from_queues(
            active_queue.queue for active_queue in self.mm_manager.active_queues
        )
        room_view = ScrimRoomView(self, room, channel, mappacks)
        try:
            room_view.message = await channel.send(
                content=mentions(room.players()),
                embed=room_view.build_embed(),
                view=room_view,
            )
        except Exception:
            room_view.stop()
            await channel.delete(reason="Failed to set up scrim room.")
            raise
        self.rooms[room.room_id] = room_view

        logging.info(f"Opened scrim room {room.room_id} for players {room.players()}.")
        return room_view

    def forget_room(self, room_view: ScrimRoomView) -> None:
        """Stops tracking a room, canceling its match if one is in progress."""
        room = room_view.room
        self.rooms.pop(room.room_id, None)
        room_view.stop()

        # Canceling the match also deletes it from Nadeo's servers
        if room.status == ScrimRoomStatus.IN_MATCH and room.bot_match_id is not None:
            self.mm_manager.cancel_match(room.bot_match_id)

    async def close_room(self, room_view: ScrimRoomView, reason: str) -> None:
        """Closes a room by deleting its channel."""
        room = room_view.room
        self.forget_room(room_view)

        try:
            await room_view.channel.delete(reason=reason)
        except Exception as e:
            logging.error(
                f"Failed to delete channel for scrim room {room.room_id}: {e}"
            )

        logging.info(f"Closed scrim room {room.room_id}: {reason}")

    async def invite(
        self, room_view: ScrimRoomView, inviter: PlayerProfile, member: discord.Member
    ) -> Optional[str]:
        """Invites a member to a room, letting them see it to accept or decline.

        Args:
            room_view (ScrimRoomView): The room to invite to.
            inviter (PlayerProfile): The player in the room sending the invite.
            member (discord.Member): The member to invite.

        Returns:
            Optional[str]: Why the member couldn't be invited, None if they were.
        """
        room = room_view.room
        if member.bot:
            return f"{member.mention} is a bot."
        if room.has_player(member.id):
            return f"{member.mention} is already in this room."
        if member.id in room.invites:
            return f"{member.mention} is already invited."
        if room.status != ScrimRoomStatus.SETUP:
            return "Wait for the current match to finish before inviting players."
        if room.is_full():
            return "This room is full."

        invitee = self.ddb_manager.query_player_profile_for_discord_account_id(
            member.id
        )
        if invitee is None:
            return f"{member.mention} must register their account first!"
        if self.find_room_with_player(member.id) is not None:
            return f"{member.mention} is already in another scrim room."

        room.add_invite(invitee, inviter)
        room.touch()

        try:
            if not await self.set_room_access(room_view, member, can_chat=False):
                raise PermissionError("Couldn't let them see the room.")
            room_view.invite_messages[member.id] = await room_view.channel.send(
                content=member.mention,
                embed=build_invite_embed(room, inviter),
                view=ScrimInviteView(room_view, member.id),
            )
        except Exception as e:
            logging.error(
                f"Failed to invite {member.id} to scrim room {room.room_id}: {e}"
            )
            room.invites.pop(member.id, None)
            await self.remove_room_access(room_view, member.id)
            return f"Failed to invite {member.mention}."

        await room_view.refresh()

        logging.info(
            f"Player {inviter} invited {invitee} to scrim room {room.room_id}."
        )
        return None

    async def close_invite_message(
        self, room_view: ScrimRoomView, discord_account_id: int, outcome: str
    ) -> None:
        """Replaces an invite's message with its outcome, removing its buttons."""
        message = room_view.invite_messages.pop(discord_account_id, None)
        if message is None:
            return

        try:
            await message.edit(
                content=None, embed=build_closed_invite_embed(outcome), view=None
            )
        except Exception as e:
            logging.warning(f"Failed to edit scrim invite message: {e}")

    async def accept_invite(
        self, room_view: ScrimRoomView, discord_account_id: int
    ) -> Optional[str]:
        """Adds an invited player to a room, along with their party teammate if they have one.

        Returns:
            Optional[str]: Why the invite couldn't be accepted, None if it was.
        """
        room = room_view.room
        invite = room.invites.get(discord_account_id)
        if invite is None:
            return "This invite is no longer valid."
        if room.status != ScrimRoomStatus.SETUP:
            return "Wait for the current match to finish, then accept."
        if self.find_room_with_player(discord_account_id) is not None:
            return "You're already in another scrim room. Leave it first."
        if room.is_full():
            return "This room is full."

        guild = room_view.channel.guild
        member = guild.get_member(discord_account_id)
        if member is None:
            return "Couldn't find you in this server."

        room.add_player(invite.invitee)
        await self.set_room_access(room_view, member, can_chat=True)
        outcome = f"✅ <@{discord_account_id}> accepted the invite"

        # Partied players bring their teammate along, on their side
        teammate = self.get_free_teammate(invite.invitee)
        teammate_member = (
            guild.get_member(teammate.discord_account_id) if teammate else None
        )
        if (
            teammate is not None
            and teammate_member is not None
            and room.add_player(teammate, room.side_of(discord_account_id))
        ):
            await self.set_room_access(room_view, teammate_member, can_chat=True)
            await self.close_invite_message(
                room_view,
                teammate.discord_account_id,
                f"✅ <@{teammate.discord_account_id}> joined with their teammate.",
            )
            outcome += f" and brought their teammate <@{teammate.discord_account_id}>"

        room.touch()
        await self.close_invite_message(room_view, discord_account_id, outcome + ".")
        await room_view.refresh()

        logging.info(f"Player {invite.invitee} joined scrim room {room.room_id}.")
        return None

    async def decline_invite(
        self, room_view: ScrimRoomView, discord_account_id: int
    ) -> None:
        room_view.room.invites.pop(discord_account_id, None)
        await self.close_invite_message(
            room_view,
            discord_account_id,
            f"❌ <@{discord_account_id}> declined the invite.",
        )
        await self.remove_room_access(room_view, discord_account_id)
        await room_view.refresh()

    async def remove_player(
        self, room_view: ScrimRoomView, discord_account_id: int, notice: str
    ) -> Optional[str]:
        """Removes a player (other than the host) from a room between matches.

        Returns:
            Optional[str]: Why the player couldn't be removed, None if they were.
        """
        room = room_view.room
        if room.is_host(discord_account_id):
            return "The host can't leave the room. Use Close Room instead."
        if not room.has_player(discord_account_id):
            return "That player isn't in this room."
        if room.status != ScrimRoomStatus.SETUP:
            return "Players can't leave while a match is starting or in progress."

        room.remove_player(discord_account_id)
        room.touch()
        await self.remove_room_access(room_view, discord_account_id)
        await room_view.channel.send(notice)
        await room_view.refresh()
        return None

    async def leave_room(
        self, room_view: ScrimRoomView, discord_account_id: int
    ) -> Optional[str]:
        if not room_view.room.has_player(discord_account_id):
            return "You aren't in this room."

        return await self.remove_player(
            room_view, discord_account_id, f"👋 <@{discord_account_id}> left the room."
        )

    async def kick(
        self, room_view: ScrimRoomView, discord_account_id: int
    ) -> Optional[str]:
        """Removes a player from a room, or withdraws their invite."""
        room = room_view.room
        if discord_account_id in room.invites:
            room.invites.pop(discord_account_id)
            await self.close_invite_message(
                room_view,
                discord_account_id,
                f"🚫 The invite to <@{discord_account_id}> was withdrawn.",
            )
            await self.remove_room_access(room_view, discord_account_id)
            await room_view.refresh()
            return None

        return await self.remove_player(
            room_view,
            discord_account_id,
            f"👢 <@{discord_account_id}> was removed from the room.",
        )

    async def set_custom_mappack(
        self, room_view: ScrimRoomView, discord_account_id: int, campaign_text: str
    ) -> Optional[str]:
        """Sets a room's mappack to a club campaign given by its trackmania.io link.

        Returns:
            Optional[str]: Why the mappack couldn't be set, None if it was.
        """
        room = room_view.room
        if not room.is_host(discord_account_id):
            return "Only the host can choose the mappack."
        if room.status != ScrimRoomStatus.SETUP:
            return "The mappack can't change while a match is starting or in progress."

        campaign_ids = parse_campaign_reference(campaign_text)
        if campaign_ids is None:
            return (
                "That isn't a campaign. Paste a link like "
                "https://trackmania.io/#/campaigns/<club id>/<campaign id>"
            )

        # A queue's mappack keeps hosting matches in that queue's club
        club_id, campaign_id = campaign_ids
        listed_mappack = room_view.mappack_select.get_mappack(
            f"{club_id}/{campaign_id}"
        )
        if listed_mappack is not None:
            room.mappack = listed_mappack
        else:
            num_maps = count_campaign_maps(club_id, campaign_id)
            if num_maps == 0:
                return f"Couldn't load any maps from campaign {club_id}/{campaign_id}."

            room.mappack = ScrimMappack(
                name=f"Campaign {club_id}/{campaign_id} ({num_maps} maps)",
                campaign_club_id=club_id,
                campaign_id=campaign_id,
            )
        room.touch()
        await room_view.refresh()
        return None

    async def create_room_match(self, room_view: ScrimRoomView) -> None:
        """Creates a match for a room which is starting one, and has the matchmaking manager track it
        until it completes. Players in the room are pinged once they can join."""
        room = room_view.room
        try:
            if room.mappack is None:
                raise ValueError("The room has no mappack.")

            match_club_id = self.get_match_club_id(room.mappack)
            bot_match_id = self.ddb_manager.get_next_bot_match_id_and_increment()
            room.bot_match_id = bot_match_id
            active_match = await room.create_match(match_club_id, bot_match_id)
        except Exception as e:
            logging.error(f"Error generating match for scrim room {room.room_id}: {e}")
            room.status = ScrimRoomStatus.SETUP
            room.bot_match_id = None

            if room.room_id in self.rooms:
                reason = (
                    str(e)
                    if isinstance(e, (CreateMatchError, ValueError))
                    else "Something went wrong."
                )
                await room_view.channel.send(
                    f"⚠️ Failed to generate the match: {reason} Try again in a bit."
                )
                await room_view.refresh()
            return

        self.mm_manager.register_active_match(active_match)

        # The room's channel may have been deleted while Nadeo created the match
        if room.room_id not in self.rooms:
            self.mm_manager.cancel_match(active_match.bot_match_id)
            return

        room.status = ScrimRoomStatus.IN_MATCH
        room.touch()
        await room_view.channel.send(
            content=mentions(active_match.participants()),
            embed=build_match_ready_embed(active_match),
        )
        await room_view.refresh()

        logging.info(
            f"Created match {active_match.bot_match_id} for scrim room {room.room_id}."
        )

    async def report_completed_match(self, completed_match: CompletedMatch) -> None:
        """Posts the results of a scrim match in its room, and opens the room for another match."""
        if not completed_match.active_match.match_queue.is_scrim:
            return

        room_view = self.find_room_with_match(completed_match.active_match.bot_match_id)
        if room_view is None:
            return  # The room closed before its match completed

        room = room_view.room
        room.status = ScrimRoomStatus.SETUP
        room.bot_match_id = None
        room.touch()
        if not completed_match.canceled:
            room.matches_played += 1

        await room_view.channel.send(
            content=mentions(completed_match.active_match.participants()),
            embed=build_results_embed(completed_match),
        )
        await room_view.refresh()

    @tasks.loop(seconds=SCRIM_CHECK_COMPLETED_MATCHES_TASK_SEC)
    async def process_completed_matches(self) -> None:
        completed_match = self.mm_event_bus.get_new_completed_match(
            self.completed_match_sub
        )
        while completed_match is not None:
            try:
                await self.report_completed_match(completed_match)
            except Exception as e:
                logging.error(
                    f"Error reporting completed match {completed_match.active_match.bot_match_id} "
                    f"in its scrim room: {e}"
                )
            completed_match = self.mm_event_bus.get_new_completed_match(
                self.completed_match_sub
            )

    @tasks.loop(seconds=SCRIM_CHECK_ROOMS_TASK_SEC)
    async def check_stale_rooms(self) -> None:
        """Expires unanswered invites, and closes rooms which have been inactive between matches."""
        now = time.time()
        for room_view in list(self.rooms.values()):
            room = room_view.room
            try:
                expired_invites = room.expired_invites(now)
                for invite in expired_invites:
                    discord_account_id = invite.invitee.discord_account_id
                    room.invites.pop(discord_account_id, None)
                    await self.close_invite_message(
                        room_view,
                        discord_account_id,
                        f"⌛ The invite to <@{discord_account_id}> expired.",
                    )
                    await self.remove_room_access(room_view, discord_account_id)
                if expired_invites:
                    await room_view.refresh()

                if (
                    room.status == ScrimRoomStatus.SETUP
                    and now - room.last_activity_time > SCRIM_ROOM_INACTIVITY_SEC
                ):
                    await self.close_room(room_view, "Closed for inactivity.")
            except Exception as e:
                logging.error(f"Error checking scrim room {room.room_id}: {e}")

    @tasks.loop(count=1)
    async def delete_orphaned_rooms(self) -> None:
        """Rooms only exist in memory, so room channels left by a previous bot instance are dead."""
        category = self.get_scrim_category()
        if category is None:
            return

        for channel in category.text_channels:
            if (
                channel.topic == SCRIM_ROOM_CHANNEL_TOPIC
                and channel.id not in self.rooms
            ):
                logging.info(f"Deleting orphaned scrim room channel {channel.name}.")
                try:
                    await channel.delete(
                        reason="Scrim room from a previous bot instance."
                    )
                except Exception as e:
                    logging.warning(f"Failed to delete orphaned scrim room: {e}")

    @delete_orphaned_rooms.before_loop
    @check_stale_rooms.before_loop
    @process_completed_matches.before_loop
    async def before_checks(self):
        """Wait until the bot is ready before starting the loop."""
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Invites players that someone in a room @mentions in the room's channel."""
        if message.author.bot or not message.mentions or message.guild is None:
            return

        room_view = self.rooms.get(message.channel.id)
        if room_view is None:
            return

        inviter = room_view.room.get_player(message.author.id)
        if inviter is None:
            return  # Only players in the room can invite

        for user in message.mentions:
            # Mentioning players who are already in the room is just chatting
            if (
                user.bot
                or room_view.room.has_player(user.id)
                or user.id in room_view.room.invites
            ):
                continue

            member = message.guild.get_member(user.id)
            if member is None:
                continue

            error = await self.invite(room_view, inviter, member)
            if error is not None:
                await message.reply(
                    error,
                    mention_author=False,
                    allowed_mentions=discord.AllowedMentions.none(),
                )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        room_view = self.rooms.get(channel.id)
        if room_view is None:
            return

        self.forget_room(room_view)
        logging.info(f"Scrim room {channel.id} channel was deleted.")

    @commands.hybrid_command(
        name="scrim",
        description="Open a scrim room to play unranked matches against players you invite.",
    )
    @commands.guild_only()
    async def scrim(self, ctx: commands.Context) -> None:
        logging.info(
            f"Processing command to open a scrim room from user {ctx.author.name}."
        )
        await ctx.defer(ephemeral=True)

        host = self.ddb_manager.query_player_profile_for_discord_account_id(
            ctx.author.id
        )
        if not host:
            await ctx.send("You must register your account first!", ephemeral=True)
            return

        existing_room = self.find_room_with_player(ctx.author.id)
        if existing_room is not None:
            await ctx.send(
                f"You are already in scrim room {existing_room.channel.mention}.",
                ephemeral=True,
            )
            return

        category = self.get_scrim_category()
        if category is None or not isinstance(ctx.author, discord.Member):
            await ctx.send(
                "Scrims aren't set up yet. A mod needs to run /set_scrim_category.",
                ephemeral=True,
            )
            return

        try:
            room_view = await self.open_room(
                category, ctx.author, host, self.get_free_teammate(host)
            )
        except Exception as e:
            logging.error(f"Failed to open scrim room for {ctx.author.name}: {e}")
            await ctx.send(
                "Failed to open a scrim room. Try again later.", ephemeral=True
            )
            return

        await ctx.send(
            f"Opened scrim room {room_view.channel.mention}. Invite players by @mentioning them there!",
            ephemeral=True,
        )

    @commands.hybrid_command(
        name="scrim_invite",
        description="Invite a player to your scrim room. You can also @mention them in the room.",
    )
    @commands.guild_only()
    async def scrim_invite(self, ctx: commands.Context, player: discord.Member) -> None:
        logging.info(
            f"Processing command to invite {player.name} to a scrim room from user {ctx.author.name}."
        )

        room_view = self.rooms.get(ctx.channel.id)
        if room_view is None:
            await ctx.send("Use this command in your scrim room.", ephemeral=True)
            return

        inviter = room_view.room.get_player(ctx.author.id)
        if inviter is None:
            await ctx.send("Only players in this room can invite.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)
        error = await self.invite(room_view, inviter, player)
        await ctx.send(error or f"Invited {player.mention}.", ephemeral=True)

    @commands.hybrid_command(
        name="scrim_kick",
        description="Remove a player from your scrim room, or withdraw their invite.",
    )
    @commands.guild_only()
    async def scrim_kick(self, ctx: commands.Context, player: discord.Member) -> None:
        logging.info(
            f"Processing command to kick {player.name} from a scrim room from user {ctx.author.name}."
        )

        room_view = self.rooms.get(ctx.channel.id)
        if room_view is None:
            await ctx.send("Use this command in your scrim room.", ephemeral=True)
            return

        if not room_view.room.is_host(ctx.author.id):
            await ctx.send("Only the host can remove players.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)
        error = await self.kick(room_view, player.id)
        await ctx.send(error or f"Removed {player.mention}.", ephemeral=True)

    @commands.hybrid_command(
        name="set_scrim_category",
        description="Set the category scrim rooms are created in.",
    )
    @commands.has_role(ROLE_MOD)
    async def set_scrim_category(
        self, ctx: commands.Context, category: discord.CategoryChannel
    ) -> None:
        logging.info(
            f"Processing command to set scrim category {category.id} from user {ctx.author.name}."
        )

        configs = self.s3_manager.get_configs()
        configs.scrim_category_id = category.id
        self.s3_manager.update_config(configs)

        await ctx.send(
            f"Scrim rooms will be created in category {category.name}.",
            ephemeral=True,
        )

    @commands.hybrid_command(
        name="set_scrim_match_club",
        description="Set the club hosting scrim matches, instead of the match club of the mappack's queue.",
    )
    @commands.has_role(ROLE_MOD)
    async def set_scrim_match_club(self, ctx: commands.Context, club_id: int) -> None:
        logging.info(
            f"Processing command to set scrim match club {club_id} from user {ctx.author.name}."
        )

        configs = self.s3_manager.get_configs()
        configs.scrim_match_club_id = club_id
        self.s3_manager.update_config(configs)

        await ctx.send(
            f"Scrim matches will be hosted in club {club_id}.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ScrimManager(bot))

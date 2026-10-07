from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

import discord
from cogs.constants import COLOR_EMBED
from discord import ui
from matchmaking.match_queues.constants import TEAM_BLUE, TEAM_RED
from matchmaking.matches.active_match import ActiveMatch
from matchmaking.matches.completed_match import CompletedMatch
from matchmaking.scrims.constants import SCRIM_INVITE_EXPIRATION_SEC
from matchmaking.scrims.scrim_mappack import ScrimMappack
from matchmaking.scrims.scrim_mode import ScrimMode
from matchmaking.scrims.scrim_room import ScrimRoom, ScrimRoomStatus
from models.player_profile import PlayerProfile

if TYPE_CHECKING:
    from cogs.scrim_manager import ScrimManager

CUSTOM_MAPPACK_VALUE = "custom"
# Discord allows 25 options per select menu. Two are kept for the custom mappack options.
MAX_LISTED_MAPPACKS = 23


def mentions(players: List[PlayerProfile]) -> str:
    return " ".join(f"<@{player.discord_account_id}>" for player in players)


class ScrimModeSelect(ui.Select["ScrimRoomView"]):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Choose a mode",
            row=0,
            options=[
                discord.SelectOption(
                    label=mode.value, value=mode.value, description=mode.description()
                )
                for mode in ScrimMode
            ],
        )

    def sync(self, mode: Optional[ScrimMode], disabled: bool) -> None:
        for option in self.options:
            option.default = mode is not None and option.value == mode.value
        self.disabled = disabled

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is not None:
            await self.view.on_mode_selected(interaction, ScrimMode(self.values[0]))


class ScrimMappackSelect(ui.Select["ScrimRoomView"]):
    def __init__(self, mappacks: List[ScrimMappack]) -> None:
        super().__init__(placeholder="Choose a mappack", row=1)
        self.mappacks = mappacks[:MAX_LISTED_MAPPACKS]
        self.sync(None, disabled=False)

    def sync(self, selected: Optional[ScrimMappack], disabled: bool) -> None:
        options = [self._option(mappack, selected) for mappack in self.mappacks]

        # Show a custom mappack the room is using, since it isn't listed
        if selected is not None and self.get_mappack(selected.key()) is None:
            options.append(self._option(selected, selected))

        options.append(
            discord.SelectOption(
                label="Custom campaign...",
                value=CUSTOM_MAPPACK_VALUE,
                description="Any club campaign, by its trackmania.io link",
            )
        )
        self.options = options
        self.disabled = disabled

    def get_mappack(self, value: str) -> Optional[ScrimMappack]:
        for mappack in self.mappacks:
            if mappack.key() == value:
                return mappack
        return None

    def _option(
        self, mappack: ScrimMappack, selected: Optional[ScrimMappack]
    ) -> discord.SelectOption:
        return discord.SelectOption(
            label=mappack.name[:100],
            value=mappack.key(),
            description=f"Campaign {mappack.key()}",
            default=selected is not None and mappack.key() == selected.key(),
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is not None:
            await self.view.on_mappack_selected(interaction, self.values[0])


class CustomMappackModal(ui.Modal):
    campaign: ui.TextInput = ui.TextInput(
        label="trackmania.io campaign link",
        placeholder="https://trackmania.io/#/campaigns/<club id>/<campaign id>",
        max_length=200,
    )

    def __init__(self, room_view: ScrimRoomView):
        super().__init__(title="Custom Mappack")
        self.room_view = room_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Loading the campaign from Nadeo can take a few seconds
        await interaction.response.defer(ephemeral=True, thinking=True)

        error = await self.room_view.manager.set_custom_mappack(
            self.room_view, interaction.user.id, self.campaign.value
        )
        await interaction.followup.send(error or "Mappack updated.", ephemeral=True)


class ScrimRoomView(ui.View):
    """
    The setup panel of a scrim room, where the host picks the mode and mappack and starts matches,
    and players pick their side. Also tracks the room's discord channel and messages.
    """

    def __init__(
        self,
        manager: ScrimManager,
        room: ScrimRoom,
        channel: discord.TextChannel,
        mappacks: List[ScrimMappack],
    ):
        super().__init__(timeout=None)
        self.manager = manager
        self.room = room
        self.channel = channel
        self.message: Optional[discord.Message] = None

        # Outstanding invite messages keyed by the invitee's discord account ID
        self.invite_messages: Dict[int, discord.Message] = {}

        self.mode_select = ScrimModeSelect()
        self.mappack_select = ScrimMappackSelect(mappacks)
        self.add_item(self.mode_select)
        self.add_item(self.mappack_select)

        self.sync_components()

    def sync_components(self) -> None:
        """Enables only the components which apply to the room's current state."""
        room = self.room
        in_setup = room.status == ScrimRoomStatus.SETUP
        self.mode_select.sync(room.mode, disabled=not in_setup)
        self.mappack_select.sync(room.mappack, disabled=not in_setup)
        self.start_button.disabled = not in_setup
        self.cancel_match_button.disabled = room.status != ScrimRoomStatus.IN_MATCH
        self.switch_side_button.disabled = not in_setup or (
            room.mode is not None and not room.mode.is_team_mode()
        )
        self.leave_button.disabled = not in_setup
        self.close_button.disabled = not in_setup

    def build_embed(self) -> discord.Embed:
        room = self.room
        embed = discord.Embed(
            title="Scrim Room",
            description="Invite players by @mentioning them in this channel, or with `/scrim_invite`. "
            "The host picks the mode and mappack, then starts the match. Scrims are unranked.",
            color=COLOR_EMBED,
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text=f"Matches played: {room.matches_played} | Last updated")

        embed.add_field(name="Host", value=f"<@{room.host.discord_account_id}>")
        embed.add_field(
            name="Mode", value=room.mode.value if room.mode else "Not chosen"
        )
        embed.add_field(
            name="Mappack",
            value=(
                f"[{room.mappack.name}]({room.mappack.link()})"
                if room.mappack
                else "Not chosen"
            ),
        )

        if room.mode is not None and not room.mode.is_team_mode():
            embed.add_field(
                name="Players", value=mentions(room.players()) or "-", inline=False
            )
        else:
            embed.add_field(
                name="Blue Team", value=mentions(room.players_on(TEAM_BLUE)) or "-"
            )
            embed.add_field(
                name="Red Team", value=mentions(room.players_on(TEAM_RED)) or "-"
            )

        if room.invites:
            embed.add_field(
                name="Invited",
                value=" ".join(f"<@{discord_id}>" for discord_id in room.invites),
                inline=False,
            )

        embed.add_field(name="Status", value=self._status(), inline=False)
        return embed

    def _status(self) -> str:
        room = self.room
        if room.status == ScrimRoomStatus.STARTING:
            return "Generating the match... This can take a minute."
        if room.status == ScrimRoomStatus.IN_MATCH:
            return f'Match #{room.bot_match_id} in progress! Join the club activity "BMM - #{room.bot_match_id}".'

        blockers = room.start_blockers()
        if blockers:
            return "\n".join(f"- {blocker}" for blocker in blockers)
        return "Ready! The host can press Start Scrim."

    async def refresh(self) -> None:
        """Redraws the panel to show the room's current state."""
        if self.message is None:
            return

        self.sync_components()
        try:
            await self.message.edit(embed=self.build_embed(), view=self)
        except Exception as e:
            logging.warning(
                f"Failed to refresh panel for scrim room {self.room.room_id}: {e}"
            )

    async def redraw(self, interaction: discord.Interaction) -> None:
        """Redraws the panel in response to an interaction with it."""
        self.room.touch()
        self.sync_components()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def check_host(self, interaction: discord.Interaction) -> bool:
        if not self.room.is_host(interaction.user.id):
            await interaction.response.send_message(
                "Only the host can do that.", ephemeral=True
            )
            return False
        return True

    async def check_setup(self, interaction: discord.Interaction) -> bool:
        if self.room.status != ScrimRoomStatus.SETUP:
            await interaction.response.send_message(
                "Not while a match is starting or in progress.", ephemeral=True
            )
            return False
        return True

    async def on_mode_selected(
        self, interaction: discord.Interaction, mode: ScrimMode
    ) -> None:
        if not await self.check_host(interaction) or not await self.check_setup(
            interaction
        ):
            return

        self.room.mode = mode
        await self.redraw(interaction)

    async def on_mappack_selected(
        self, interaction: discord.Interaction, value: str
    ) -> None:
        if not await self.check_host(interaction) or not await self.check_setup(
            interaction
        ):
            return

        if value == CUSTOM_MAPPACK_VALUE:
            await interaction.response.send_modal(CustomMappackModal(self))
            return

        # Selecting the room's current (possibly custom) mappack again keeps it
        mappack = self.mappack_select.get_mappack(value)
        if mappack is not None:
            self.room.mappack = mappack
        await self.redraw(interaction)

    @ui.button(label="Start Scrim", style=discord.ButtonStyle.green, row=2)
    async def start_button(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.check_host(interaction):
            return

        error = self.manager.check_can_start_match(self.room)
        if error is not None:
            await interaction.response.send_message(error, ephemeral=True)
            return

        self.room.status = ScrimRoomStatus.STARTING
        await self.redraw(interaction)

        # Nadeo can take a few minutes to create the match, which is fine after responding
        await self.manager.create_room_match(self)

    @ui.button(label="Cancel Match", style=discord.ButtonStyle.grey, row=2)
    async def cancel_match_button(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        if not await self.check_host(interaction):
            return

        bot_match_id = self.room.bot_match_id
        if self.room.status != ScrimRoomStatus.IN_MATCH or bot_match_id is None:
            await interaction.response.send_message(
                "There's no match in progress.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Canceling match #{bot_match_id}...", ephemeral=True
        )
        self.manager.mm_manager.cancel_match(bot_match_id)

    @ui.button(label="Switch Side", style=discord.ButtonStyle.blurple, row=2)
    async def switch_side_button(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        if not self.room.has_player(interaction.user.id):
            await interaction.response.send_message(
                "You aren't in this room.", ephemeral=True
            )
            return
        if not await self.check_setup(interaction):
            return

        self.room.switch_side(interaction.user.id)
        await self.redraw(interaction)

    @ui.button(label="Leave", style=discord.ButtonStyle.grey, row=2)
    async def leave_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()

        error = await self.manager.leave_room(self, interaction.user.id)
        if error is not None:
            await interaction.followup.send(error, ephemeral=True)

    @ui.button(label="Close Room", style=discord.ButtonStyle.red, row=2)
    async def close_button(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.check_host(interaction):
            return

        if self.room.status != ScrimRoomStatus.SETUP:
            await interaction.response.send_message(
                "Cancel the match or wait for it to finish, then close the room.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        await self.manager.close_room(self, "Closed by the host.")


class ScrimInviteView(ui.View):
    """Lets an invited player accept or decline joining a scrim room."""

    def __init__(self, room_view: ScrimRoomView, invitee_discord_id: int):
        super().__init__(timeout=None)
        self.room_view = room_view
        self.invitee_discord_id = invitee_discord_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure that only the invitee can interact with the buttons."""
        if interaction.user.id != self.invitee_discord_id:
            await interaction.response.send_message(
                "You are not the intended recipient of this invite!", ephemeral=True
            )
            return False
        return True

    @ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()

        error = await self.room_view.manager.accept_invite(
            self.room_view, self.invitee_discord_id
        )
        if error is not None:
            await interaction.followup.send(error, ephemeral=True)

    @ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()

        await self.room_view.manager.decline_invite(
            self.room_view, self.invitee_discord_id
        )


def build_invite_embed(room: ScrimRoom, inviter: PlayerProfile) -> discord.Embed:
    setup = []
    if room.mode is not None:
        setup.append(room.mode.value)
    if room.mappack is not None:
        setup.append(f"on {room.mappack.name}")
    setup_str = f" ({' '.join(setup)})" if setup else ""

    embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())
    embed.add_field(
        name="❗ Scrim Invite",
        value=f"<@{inviter.discord_account_id}> invited you to scrim{setup_str}. "
        f"Accept within {SCRIM_INVITE_EXPIRATION_SEC // 60} minutes to join the room.",
    )
    return embed


def build_closed_invite_embed(outcome: str) -> discord.Embed:
    embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())
    embed.add_field(name="❗ Scrim Invite", value=outcome)
    return embed


def build_match_ready_embed(active_match: ActiveMatch) -> discord.Embed:
    club_link = (
        f"https://trackmania.io/#/clubs/{active_match.match_queue.match_club_id}"
    )
    embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())
    embed.add_field(
        name=f"❗ Scrim Match #{active_match.bot_match_id} Ready",
        value=f'Join the [club]({club_link}) and click activity "{active_match.event_name}"!',
    )
    return embed


def build_results_embed(completed_match: CompletedMatch) -> discord.Embed:
    active_match = completed_match.active_match
    embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())

    if completed_match.canceled:
        embed.add_field(
            name=f"❌ Scrim Match #{active_match.bot_match_id} Canceled",
            value="The host can press Start Scrim to play another match.",
        )
        return embed

    results = completed_match.match_results
    teams = active_match.teams()
    lines = []
    if teams is not None and results.teams:
        # Teams without a rank didn't show up, so list them last
        for ranked_team in sorted(
            results.teams, key=lambda team: team.rank or len(results.teams) + 1
        ):
            team = next((t for t in teams if t.name == ranked_team.team), None)
            team_players = mentions(list(team)) if team is not None else ""
            lines.append(
                f"{ranked_team.rank or '-'}. {ranked_team.team} {team_players}"
            )
    else:
        # Players without a rank didn't show up, so list them last
        participants = active_match.participants()
        ranks = {
            player.tm_account_id: results.get_rank(player.tm_account_id)
            for player in participants
        }
        for player in sorted(
            participants, key=lambda p: ranks[p.tm_account_id] or len(participants) + 1
        ):
            lines.append(
                f"{ranks[player.tm_account_id] or '-'}. <@{player.discord_account_id}>"
            )

    lines.append(
        "\nNo elo changes, since scrims are unranked. Rematch with Start Scrim!"
    )
    embed.add_field(
        name=f"🏁 Scrim Match #{active_match.bot_match_id} Finished",
        value="\n".join(lines),
    )
    return embed

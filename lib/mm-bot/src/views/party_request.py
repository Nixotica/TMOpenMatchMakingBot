import discord
from matchmaking.party.active_party import ActiveParty
from matchmaking.party.request_status import PartyRequestStatus


class PartyRequestView(discord.ui.View):
    def __init__(self, active_party: ActiveParty):
        super().__init__()
        self.active_party = active_party
        self.status: PartyRequestStatus = PartyRequestStatus.PENDING

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure that only the accepter can interact with the buttons."""
        if interaction.user.id != self.active_party.accepter.discord_account_id:
            await interaction.response.send_message(
                "You are not the intended recipient of this request!", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Handle the accepter clicking the 'Accept' button."""
        await interaction.response.send_message(
            f"✅ <@{self.active_party.accepter.discord_account_id}> accepted the invite!",
            ephemeral=False,
        )

        self.status = PartyRequestStatus.ACCEPTED

        if interaction.message:
            await interaction.message.delete()

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Handle the accepter clicking the 'Reject' button."""
        await interaction.response.send_message(
            f"❌ <@{self.active_party.accepter.discord_account_id}> declined the invite.",
            ephemeral=False,
        )

        self.status = PartyRequestStatus.REJECTED

        if interaction.message:
            await interaction.message.delete()

    def get_status(self) -> PartyRequestStatus:
        return self.status

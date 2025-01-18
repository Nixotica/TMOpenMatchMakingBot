from dataclasses import dataclass

import discord

from views.party_request import PartyRequestView


@dataclass
class PartyRequest:
    message: discord.message.Message
    view: PartyRequestView
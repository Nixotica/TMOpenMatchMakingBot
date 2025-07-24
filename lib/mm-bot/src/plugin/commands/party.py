from plugin.responses.base_response import BaseResponse


class PartyInvitationCommand(BaseResponse):
    def __init__(self, invitee_id: str):
        super().__init__()
        self.invitee_id = invitee_id

    def name(self) -> str:
        return "PartyInvitation"

    def payload(self):
        return {"TmAccountId": self.invitee_id}


class AddPlayersToPartyCommand(BaseResponse):
    def __init__(self):
        super().__init__()
        self.party_members: list[dict] = []

    def name(self) -> str:
        return "AddPlayersToParty"

    def add_party_member(self, tm_account_id: str):
        self.party_members.append({"TmAccountId": tm_account_id})

    def payload(self):
        return {"PartyMembers": self.party_members}


class RemovePlayersFromPartyCommand(BaseResponse):
    def __init__(self):
        super().__init__()
        self.party_members: list[dict] = []

    def name(self) -> str:
        return "RemovePlayersFromParty"

    def add_party_member(self, tm_account_id: str):
        self.party_members.append({"TmAccountId": tm_account_id})

    def payload(self):
        return {"PartyMembers": self.party_members}


class ClearPartyCommand(BaseResponse):
    def __init__(self):
        super().__init__()

    def name(self) -> str:
        return "ClearParty"

    def payload(self) -> dict:
        return {}

    def status_code(self):
        return 200

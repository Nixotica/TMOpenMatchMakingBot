from plugin.responses.base_response import BaseResponse


class PartyInviteResponse(BaseResponse):
    def __init__(self, tm_account_id: str):
        super().__init__()
        self.invitee_id = tm_account_id

    def name(self) -> str:
        return "PartyInviteResponse"

    def payload(self) -> dict:
        return {
            "TmAccountId": self.invitee_id,
        }

    def status_code(self):
        return 200


class CancelPartyInviteResponse(BaseResponse):
    def __init__(self, tm_account_id: str):
        super().__init__()
        self.invitee_id = tm_account_id

    def name(self) -> str:
        return "CancelPartyInviteResponse"

    def payload(self) -> dict:
        return {
            "TmAccountId": self.invitee_id,
        }

    def status_code(self):
        return 200


class AcceptPartyInviteResponse(BaseResponse):
    def __init__(self):
        super().__init__()
        self.party_members: list[dict] = []

    def name(self) -> str:
        return "AcceptPartyInviteResponse"

    def add_party_member(self, tm_account_id: str):
        self.party_members.append({"TmAccountId": tm_account_id})

    def payload(self):
        return {"PartyMembers": self.party_members}

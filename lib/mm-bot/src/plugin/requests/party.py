from plugin.requests.base_request import BaseRequest


class PartyInviteRequest(BaseRequest):
    invitee_id: str | None = None

    def __init__(self, user, invitee_id):
        super().__init__(user)
        self.invitee_id = invitee_id

    def name(cls) -> str:
        return "PartyInvite"


class CancelPartyInviteRequest(BaseRequest):
    invitee_id: str | None = None

    def __init__(self, user, invitee_id):
        super().__init__(user)
        self.invitee_id = invitee_id

    def name(cls) -> str:
        return "CancelPartyInvite"


class AcceptPartyInviteRequest(BaseRequest):
    inviter_id: str | None = None

    def __init__(self, user, inviter_id):
        super().__init__(user)
        self.inviter_id = inviter_id

    def name(cls) -> str:
        return "AcceptPartyInvite"


class LeavePartyRequest(BaseRequest):
    def __init__(self, user):
        super().__init__(user)

    def name(cls) -> str:
        return "LeaveParty"

from plugin.responses.base_response import BaseResponse


class InitializeResponse(BaseResponse):
    def __init__(self):
        super().__init__()
        self.queues: list[dict] = []
        self.party_members: list[dict] = []
        self.current_queue_id: str | None = None
        self.match: dict | None = None

    def name(self) -> str:
        return "InitializeResponse"

    def add_queues(self, queues):
        self.queues = queues

    def add_party_member(self, tm_account_id: str, points: int):
        self.party_members.append({"TmAccountId": tm_account_id, "Points": points})

    def add_current_queue(self, queue_id: str):
        self.current_queue_id = queue_id

    def add_match(self, match: dict):
        self.match = match

    def payload(self) -> dict:
        data: dict = {
            "Queues": self.queues,
            "PartyMembers": self.party_members,
        }

        if self.current_queue_id is not None:
            data["Queue"] = {"Id": self.current_queue_id}

        if self.match is not None:
            data["Match"] = self.match

        return data

    def status_code(self):
        return 200

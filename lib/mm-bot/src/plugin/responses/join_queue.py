from plugin.responses.base_response import BaseResponse


class JoinQueueResponse(BaseResponse):
    def __init__(self):
        super().__init__()
        self._queue = {}
        self._party_members = []

    def add_queue(self, queue_id: str, queue_name: str, points: int):
        self._queue = {
            "Id": queue_id,
            "Name": queue_name,
            "Count": 0,
            "Points": points,
        }

    def set_player_count(self, player_count: int):
        self._queue["Count"] = player_count

    def add_party_member(self, tm_account_id: str, points: int):
        self._party_members.append({"TmAccountId": tm_account_id, "Points": points})

    def name(self) -> str:
        return "JoinQueueResponse"

    def payload(self) -> dict:
        return {"Queue": self._queue, "PartyMembers": self._party_members}

    def status_code(self):
        return 200

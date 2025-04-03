from plugin.responses.base_response import BaseResponse

class JoinQueueResponse(BaseResponse):
    def __init__(self, player_count: int, party_members: list | None = None):
        super().__init__()
        self._player_count = player_count
        self._party_members = party_members

    def name(self) -> str:
        return "JoinQueueResponse"
    
    def payload(self) -> dict:
        data = {
            "Queue": {
                "Count": self._player_count
            }
        }

        if self._party_members is not None:
            data["PartyMembers"] = self._party_members

        return data
    
    def status_code(self):
        return 200
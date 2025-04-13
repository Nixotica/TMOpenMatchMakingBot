from plugin.responses.base_response import BaseResponse


class GetQueuesResponse(BaseResponse):
    def __init__(self):
        super().__init__()
        self.queues: list[dict] = []

    def add_queue(self, id: str, name: str, player_count: int, points: int):
        self.queues.append(
            {
                "Id": id,
                "Name": name,
                "Count": player_count,
                "Points": points,
            }
        )

    def name(self) -> str:
        return "GetQueuesResponse"

    def payload(self) -> dict:
        return {"Queues": self.queues}

    def status_code(self):
        return 200

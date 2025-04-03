from plugin.responses.base_response import BaseResponse


class GetQueuesResponse(BaseResponse):
    def __init__(self, queues):
        super().__init__()
        self._queues: list[dict] = queues

    def name(self) -> str:
        return "GetQueuesResponse"

    def payload(self) -> dict:
        return {"Queues": self._queues}

    def status_code(self):
        return 200

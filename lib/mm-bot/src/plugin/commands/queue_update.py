from plugin.responses.base_response import BaseResponse


class QueueUpdateCommand(BaseResponse):
    def __init__(self, queue_id, player_count):
        super().__init__()
        self._queue_id = queue_id
        self._player_count = player_count

    def name(self) -> str:
        return "QueueUpdate"

    def payload(self) -> dict:
        return {"Queue": {"Id": self._queue_id, "Count": self._player_count}}

    def status_code(self):
        return 200

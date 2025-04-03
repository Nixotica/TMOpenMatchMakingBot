from plugin.responses.base_response import BaseResponse

class PingResponse(BaseResponse):
    def __init__(self, queue_id: str | None = None, player_count: int | None = None):
        super().__init__()
        self._queue_id = queue_id
        self._player_count = player_count

    def name(self) -> str:
        return "PingResponse"
    
    def payload(self) -> dict:
        if self._queue_id is None:
            return {}
        
        return {
            "Queue": {
                "Id": self._queue_id,
                "Count": self._player_count
            }
        }
    
    def status_code(self):
        return 200
from plugin.requests.base_request import BaseRequest

class LeaveQueueRequest(BaseRequest):
    queue_id: str = None

    def __init__(self, user, queue_id):
        super().__init__(user)
        self.queue_id = queue_id

    def name(cls) -> str:
        return "LeaveQueue"
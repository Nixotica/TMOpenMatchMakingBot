from plugin.requests.base_request import BaseRequest


class GetQueuesRequest(BaseRequest):
    def __init__(self, user):
        super().__init__(user)

    def name(cls) -> str:
        return "GetQueues"

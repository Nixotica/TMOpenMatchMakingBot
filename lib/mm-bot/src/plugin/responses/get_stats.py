from plugin.responses.base_response import BaseResponse


class GetStatsResponse(BaseResponse):
    def __init__(self):
        super().__init__()

    def name(self) -> str:
        return "GetStatsResponse"

    def payload(self) -> dict:
        return {}

    def status_code(self):
        return 200

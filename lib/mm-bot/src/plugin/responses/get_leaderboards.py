from plugin.responses.base_response import BaseResponse


class GetLeaderboardsResponse(BaseResponse):
    def __init__(self, leaderboards):
        super().__init__()
        self._leaderboards: list[dict] = leaderboards

    def name(self) -> str:
        return "GetLeaderboardsResponse"

    def payload(self) -> dict:
        return {"Leaderboards": self._leaderboards}

    def status_code(self):
        return 200

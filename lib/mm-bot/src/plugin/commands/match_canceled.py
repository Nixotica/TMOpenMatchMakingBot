from plugin.responses.base_response import BaseResponse


class MatchCanceledCommand(BaseResponse):
    def __init__(self, match_id: str):
        super().__init__()
        self._match_id = match_id

    def name(self) -> str:
        return "MatchCanceled"

    def payload(self) -> dict:
        return {
            "Id": self._match_id,
        }

    def status_code(self):
        return 200

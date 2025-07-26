from plugin.responses.base_response import BaseResponse


class CheckRegistrationResponse(BaseResponse):
    def __init__(self, is_registered: bool):
        super().__init__()
        self._is_registered = is_registered

    def name(self) -> str:
        return "CheckRegistrationResponse"

    def payload(self) -> dict:
        return {"IsRegistered": self._is_registered}

    def status_code(self):
        return 200

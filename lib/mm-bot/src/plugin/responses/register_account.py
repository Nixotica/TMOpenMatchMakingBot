from plugin.responses.base_response import BaseResponse


class RegisterAccountResponse(BaseResponse):
    def __init__(self):
        super().__init__()

    def name(self) -> str:
        return "RegisterAccountResponse"

    def payload(self) -> dict:
        result = {
            "Success": True,
        }
        return result

    def status_code(self):
        return 200

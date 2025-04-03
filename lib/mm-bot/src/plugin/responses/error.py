from plugin.responses.base_response import BaseResponse

class ErrorResponse(BaseResponse):
    def __init__(self, error_message):
        super().__init__()
        self._error_message = error_message

    def name(self) -> str:
        return "ErrorResponse"
    
    def payload(self) -> dict:
        return {
            "ErrorMessage": self._error_message
        }
    
    def status_code(self):
        return 500
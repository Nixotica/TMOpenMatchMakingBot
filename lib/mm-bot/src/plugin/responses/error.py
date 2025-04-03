from plugin.responses.base_response import BaseResponse

class ErrorResponse(BaseResponse):
    def __init__(self, error_message, keep_alive = False):
        super().__init__()
        self._error_message = error_message
        self._keep_alive = keep_alive

    def name(self) -> str:
        return "ErrorResponse"
    
    def payload(self) -> dict:
        return {
            "ErrorMessage": self._error_message,
            "KeepAlive": self._keep_alive
        }
    
    def status_code(self):
        return 500
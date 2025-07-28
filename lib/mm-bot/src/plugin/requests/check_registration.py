from plugin.requests.base_request import BaseRequest


class CheckRegistrationRequest(BaseRequest):
    def __init__(self, user: str, ubisoft_account_id: str):
        super().__init__(user)
        self.ubisoft_account_id = ubisoft_account_id

    def name(self) -> str:
        return "CheckRegistration"

from plugin.requests.base_request import BaseRequest


class RegisterAccountRequest(BaseRequest):
    def __init__(self, user: str, discord_username: str, ubisoft_account_id: str):
        super().__init__(user)
        self.discord_username = discord_username
        self.ubisoft_account_id = ubisoft_account_id

    def name(self) -> str:
        return "RegisterAccount"

import os

import requests
from nadeo.constants import NADEO_AUTH_URL, UBI_SESSION_URL
from nadeo.enums import NadeoService
from aws.s3 import S3ClientManager


class UbiTokenManager:
    _instance = None
    _nadeo_live_token = None
    _nadeo_club_token = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UbiTokenManager, cls).__new__(cls)
        return cls._instance

    def authenticate(self, ubi_auth: str, service: NadeoService) -> str:
        """
        Authenticates with the provided Nadeo service given authorization
        and returns an access token.

        :param ubi_auth: Authorization (Basic <user:pass> base 64) request for account
        :param service: Audience (e.g. "NadeoClubServices", "NadeoLiveServices")
        :return: Access token
        """
        self._active_ubi_auth = ubi_auth
        headers = {
            "Content-Type": "application/json",
            "Ubi-AppId": "86263886-327a-4328-ac69-527f0d20a237",
            "Authorization": ubi_auth,
            "User-Agent": "https://github.com/Nixotica/TMOpenMatchMakingBot",
        }
        result = requests.post(UBI_SESSION_URL, headers=headers).json()

        ticket = result["ticket"]
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"ubi_v1 t={ticket}",
        }
        body = {"audience": service.value}
        auth = requests.post(NADEO_AUTH_URL, headers=headers, json=body).json()[
            "accessToken"
        ]
        if service == NadeoService.LIVE:
            self._nadeo_live_token = auth
        elif service == NadeoService.CLUB:
            self._nadeo_club_token = auth
        return auth

    @property
    def nadeo_live_token(self) -> str:
        if self._nadeo_live_token is None:
            self._nadeo_live_token = self.authenticate(self._active_ubi_auth, NadeoService.LIVE)
        return self._nadeo_live_token

    @property
    def nadeo_club_token(self) -> str:
        if self._nadeo_club_token is None:
            self._nadeo_club_token = self.authenticate(self._active_ubi_auth, NadeoService.CLUB)
        return self._nadeo_club_token
    
    @property
    def active_ubi_auth(self) -> str:
        if self._active_ubi_auth is None:
            self._active_ubi_auth = S3ClientManager().get_secrets().ubi_auths[0] # TODO - manager should support multiple ubi auths (aka accounts)
        return self._active_ubi_auth

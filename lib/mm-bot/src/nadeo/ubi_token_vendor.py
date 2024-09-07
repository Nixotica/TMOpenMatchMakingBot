import logging
import random
import time
from typing import Dict, List
from nadeo_event_api.api.authenticate import UbiTokenManager
from aws.s3 import S3ClientManager
from nadeo_event_api.api.enums import NadeoService
from nadeo.constants import TOKEN_MAX_FRESHNESS_SEC


class UbiTokenRefresher:
    """Keeps all tokens refreshed for a set of authorized users. 
    """
    _instance = None 
    
    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'): # Ensure __init__ is only run once
            self._initialized = True
            self._club_tokens: Dict[str, str] = {}
            self._live_tokens: Dict[str, str] = {}
            self._ubi_auths: List[str] = S3ClientManager().get_secrets().ubi_auths
            self._last_refresh_time = 0
            self.refresh_tokens()

    def refresh_tokens(self):
        """Refreshes all tokens.
        """
        current_time = time.time()
        if current_time - self._last_refresh_time > TOKEN_MAX_FRESHNESS_SEC:
            logging.info("Refreshing Nadeo service tokens...")
            self._last_refresh_time = current_time
            for auth in self._ubi_auths:  
                self._club_tokens[auth] = UbiTokenManager().authenticate(NadeoService.CLUB, auth)
                self._live_tokens[auth] = UbiTokenManager().authenticate(NadeoService.LIVE, auth)
    
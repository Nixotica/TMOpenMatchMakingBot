import logging
import random
import threading
import time
from typing import Dict, List
from nadeo_event_api.api.authenticate import UbiTokenManager
from nadeo_event_api.api.enums import NadeoService
from nadeo.constants import TOKEN_MAX_FRESHNESS_SEC


class UbiTokenVendor:
    """Keeps all tokens refreshed for a set of authorized users. 
    """
    _instance = None 
    _instance_lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._instance_lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, ubi_auths: List[str]):
        if not hasattr(self, '_initialized'): # Ensure __init__ is only run once
            self._initialized = True
            self._tokens: Dict[str, str] = {}
            self._ubi_auths: List[str] = ubi_auths
            self._lock = threading.Lock()
            self._last_refresh_time = time.time()
            self._refresh_tokens()

    def _refresh_tokens(self):
        """Refreshes all tokens.
        """
        with self._lock:
            current_time = time.time()
            if current_time - self._last_refresh_time < TOKEN_MAX_FRESHNESS_SEC:
                self._last_refresh_time = current_time
                for auth in self._ubi_auths:  
                    self._tokens[auth] = UbiTokenManager().authenticate(NadeoService.CLUB, auth)
            logging.info("Refreshed Club Service tokens...")

    def get_token(self, auth: str) -> str:
        """Returns the token for the given auth.
        """
        self._refresh_tokens()
        return self._tokens[auth]
    
    def get_random_token(self) -> str:
        """Returns a random token.
        """
        self._refresh_tokens()
        return self._tokens[self._ubi_auths[random.randint(0, len(self._tokens) - 1)]]  
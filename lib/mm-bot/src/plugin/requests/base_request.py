import json
from abc import abstractmethod

class BaseRequest:
    def __init__(self, user: str):
        self._user = user
    
    def identifier(self) -> str:
        return self._user


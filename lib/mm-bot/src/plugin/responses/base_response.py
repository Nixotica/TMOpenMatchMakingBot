import json
from abc import abstractmethod


class BaseResponse:
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def payload(self) -> dict:
        pass

    @abstractmethod
    def status_code(self) -> int:
        return 200

    @abstractmethod
    def length(self) -> int:
        return len(self.encode())

    @abstractmethod
    def encode(self) -> bytes:
        return json.dumps(
            {
                "Command": self.name(),
                "Payload": self.payload(),
                "StatusCode": self.status_code(),
            }
        ).encode()

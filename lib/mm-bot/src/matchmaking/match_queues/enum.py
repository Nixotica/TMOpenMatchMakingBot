from enum import Enum


class QueueType(Enum):
    Queue1v1v1v1 = "1v1v1v1"
    Queue2v2 = "2v2"
    QueueSoloTest = "solo"
    QueueLSC = "lsc"

    @classmethod
    def from_str(cls, value: str):
        if value == QueueType.Queue1v1v1v1.value:
            return QueueType.Queue1v1v1v1
        elif value == QueueType.Queue2v2.value:
            return QueueType.Queue2v2
        elif value == QueueType.QueueSoloTest.value:
            return QueueType.QueueSoloTest
        elif value == QueueType.QueueLSC.value:
            return QueueType.QueueLSC
        else:
            raise ValueError(f"Invalid queue type: {value}")

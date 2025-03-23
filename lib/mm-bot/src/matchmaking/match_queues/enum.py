from enum import Enum


class QueueType(Enum):
    Queue1v1v1v1 = "1v1v1v1"
    Queue2v2 = "2v2"
    QueueSoloTest = "solo"
    QueueLSC = "lsc"
    QueueSim2v2 = "Sim2v2"

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
        elif value == QueueType.QueueSim2v2.value:
            return QueueType.QueueSim2v2
        else:
            raise ValueError(f"Invalid queue type: {value}")

    def is_2v2(self) -> bool:
        return self == QueueType.Queue2v2 or self == QueueType.QueueSim2v2

    def is_simulated(self) -> bool:
        """Returns true if this queue type generates simulated matches. These
            are matches which bypass the Nadeo API and run in memory with a
            randomized result that mimics a real Nadeo match.

        Returns:
            bool: True if queue is for simulated matches, False otherwise.
        """
        return self == QueueType.QueueSim2v2

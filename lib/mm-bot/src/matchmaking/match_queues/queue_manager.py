import asyncio
import logging
from typing import List
from matchmaking.match_queues.active_match_queue import ActiveMatchQueue

class QueueManager:
    def __init__(self):
        self.active_queues: List[ActiveMatchQueue] = []

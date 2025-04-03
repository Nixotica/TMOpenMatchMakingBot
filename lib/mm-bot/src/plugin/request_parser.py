import json
from json.decoder import JSONDecodeError
import logging
from plugin.requests.base_request import BaseRequest
from plugin.requests.get_queues import GetQueuesRequest
from plugin.requests.join_queue import JoinQueueRequest
from plugin.requests.leave_queue import LeaveQueueRequest
from plugin.requests.get_leaderboards import GetLeaderboardsRequest
from plugin.requests.get_stats import GetStatsRequest
from plugin.requests.ping import PingRequest

class RequestParser:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(RequestParser, cls).__new__(cls)
        return cls._instance
    
    def from_buffer(self, buffer: str) -> BaseRequest:
        try:
            obj: dict = json.loads(buffer)
        except JSONDecodeError:
            obj = {}

        if "User" not in obj or "Command" not in obj:
            logging.info(f"Invalid command received: {obj}")
            return None
        
        user: str = obj.get('User')
        command: str = obj.get('Command')
        payload: dict = obj.get('Payload')

        match command:
            case "GetQueues":
                return GetQueuesRequest(user)
            case "JoinQueue":
                return JoinQueueRequest(user, payload.get("QueueId"))
            case "LeaveQueue":
                return LeaveQueueRequest(user, payload.get("QueueId"))
            case "GetLeaderboards":
                return GetLeaderboardsRequest(user)
            case "GetStats":
                return GetStatsRequest(user)
            case "Ping":
                return PingRequest(user)
            case _:
                return None
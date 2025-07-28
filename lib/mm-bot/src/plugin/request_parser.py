import json
from json.decoder import JSONDecodeError
import logging
from packaging.version import parse, InvalidVersion
from plugin.constants import MIN_VERSION
from plugin.requests.base_request import BaseRequest
from plugin.requests.initialize import InitializeRequest
from plugin.requests.get_queues import GetQueuesRequest
from plugin.requests.invalid_version import InvalidVersionRequest
from plugin.requests.join_queue import JoinQueueRequest
from plugin.requests.leave_queue import LeaveQueueRequest
from plugin.requests.get_leaderboards import GetLeaderboardsRequest
from plugin.requests.get_stats import GetStatsRequest
from plugin.requests.party import (
    PartyInviteRequest,
    CancelPartyInviteRequest,
    AcceptPartyInviteRequest,
    LeavePartyRequest,
)
from plugin.requests.ping import PingRequest
from plugin.requests.register_account import RegisterAccountRequest
from plugin.requests.check_registration import CheckRegistrationRequest


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

        user: str = obj.get("User", "")
        if not self.is_valid_version(obj):
            return InvalidVersionRequest(user)

        command: str = obj.get("Command", "")
        payload: dict = obj.get("Payload", {})

        match command:
            case "Initialize":
                return InitializeRequest(user)
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
            case "PartyInvite":
                return PartyInviteRequest(user, payload.get("TmAccountId"))
            case "CancelPartyInvite":
                return CancelPartyInviteRequest(user, payload.get("TmAccountId"))
            case "AcceptPartyInvite":
                return AcceptPartyInviteRequest(user, payload.get("TmAccountId"))
            case "LeaveParty":
                return LeavePartyRequest(user)
            case "Ping":
                return PingRequest(user)
            case "RegisterAccount":
                return RegisterAccountRequest(
                    user,
                    payload.get("DiscordUsername") or "",
                    payload.get("UbisoftAccountId") or "",
                )
            case "CheckRegistration":
                return CheckRegistrationRequest(
                    user, payload.get("UbisoftAccountId") or ""
                )
            case _:
                return None

    def is_valid_version(self, obj: dict) -> bool:
        if "Version" not in obj:
            return False

        try:
            version = parse(obj.get("Version"))
            if version not in MIN_VERSION:
                return False
        except InvalidVersion:
            return False

        return True

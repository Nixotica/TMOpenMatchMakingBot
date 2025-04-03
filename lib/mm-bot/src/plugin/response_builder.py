from aws.dynamodb import DynamoDbManager
from cogs.matchmaking_manager_v2 import MatchmakingManagerV2
from matchmaking.match_queues.enum import QueueType
from models.player_profile import PlayerProfile
from plugin.requests.base_request import BaseRequest
from plugin.requests.base_request import BaseRequest
from plugin.requests.get_queues import GetQueuesRequest
from plugin.requests.join_queue import JoinQueueRequest
from plugin.requests.leave_queue import LeaveQueueRequest
from plugin.requests.get_leaderboards import GetLeaderboardsRequest
from plugin.requests.get_stats import GetStatsRequest
from plugin.requests.ping import PingRequest
from plugin.responses.base_response import BaseResponse
from plugin.responses.error import ErrorResponse
from plugin.responses.get_queues import GetQueuesResponse

class ResponseBuilder:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(ResponseBuilder, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, "_initialized"):  # Avoid re-initializing the instance
            self._initialized = True
            self._mm_manager = MatchmakingManagerV2()
            self._ddb_manager = DynamoDbManager()

    def build_response(self, request: BaseRequest) -> BaseResponse:
        profile: PlayerProfile = self._ddb_manager.query_player_profile_for_tm_account_id(request.identifier())
        if not profile:
            return ErrorResponse("You have not registered your account yet")

        match request:
            case GetQueuesRequest():
                return self._get_queues_response(profile, request)
            case JoinQueueRequest():
                return self._join_queue_response(profile, request)
            case LeaveQueueRequest():
                return self._leave_queue_response(profile, request)
            case GetLeaderboardsRequest():
                return self._get_leaderboards_response(profile, request)
            case GetStatsRequest():
                return self._get_stats_response(profile, request)
            case PingRequest():
                return self._ping_response(profile, request)
            case _:
                return ErrorResponse("Invalid request received")
            
    def _get_queues_response(self, profile: PlayerProfile, request: GetQueuesRequest) -> BaseResponse:
        queues: list[dict] = []
        for active_queue in self._mm_manager.active_queues:
            num_players = 0
            for party in active_queue.player_parties:
                num_players += len(party.players())

            player_elo = self._ddb_manager.get_or_create_player_elo(profile.tm_account_id, active_queue.queue.primary_leaderboard_id)
                
            queues.append({
                "Id": active_queue.queue.queue_id,
                "Name": active_queue.queue.display_name,
                "Count": num_players,
                "Points": player_elo.elo
            })

        return GetQueuesResponse(queues)
    
    def _join_queue_response(self, profile: PlayerProfile, request: JoinQueueRequest):
        return None
    
    def _leave_queue_response(self, profile: PlayerProfile, request: LeaveQueueRequest):
        return None
    
    def _get_leaderboards_response(self, profile: PlayerProfile, request: GetLeaderboardsRequest):
        return None
    
    def _get_stats_response(self, profile: PlayerProfile, request: GetStatsRequest):
        return None
    
    def _ping_response(self, profile: PlayerProfile, request: PingRequest):
        return None
        
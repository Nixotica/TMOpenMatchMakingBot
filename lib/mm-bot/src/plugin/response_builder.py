from aws.dynamodb import DynamoDbManager
from cogs.matchmaking_manager_v2 import get_matchmaking_manager_v2
from cogs.party_manager import get_party_manager
from matchmaking.match_queues.active_match_queue import ActiveMatchQueue
from models.player_profile import PlayerProfile
from plugin.command_builder import CommandBuilder
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
from plugin.responses.join_queue import JoinQueueResponse
from plugin.responses.leave_queue import LeaveQueueResponse
from plugin.responses.get_leaderboards import GetLeaderboardsResponse
from plugin.responses.get_stats import GetStatsResponse
from plugin.responses.ping_response import PingResponse


class ResponseBuilder:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(ResponseBuilder, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):  # Avoid re-initializing the instance
            self._initialized = True
            self._mm_manager = get_matchmaking_manager_v2()
            self._ddb_manager = DynamoDbManager()
            self._command_builder = CommandBuilder()

    def build_response(self, request: BaseRequest) -> BaseResponse:
        profile: PlayerProfile = (
            self._ddb_manager.query_player_profile_for_tm_account_id(
                request.identifier()
            )
        )
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

    def _get_queues_response(
        self, profile: PlayerProfile, request: GetQueuesRequest
    ) -> BaseResponse:
        response = GetQueuesResponse()

        sorted_queues: list[ActiveMatchQueue] = sorted(
            self._mm_manager.active_queues, key=lambda x: x.queue.display_name
        )
        for active_queue in sorted_queues:
            player_elo = 0
            try:
                player_elo = self._ddb_manager.get_or_create_player_elo(
                    profile.tm_account_id, active_queue.queue.get_primary_leaderboard()
                ).elo
            except Exception:
                pass

            response.add_queue(
                active_queue.queue.queue_id,
                active_queue.queue.display_name,
                active_queue.player_count(),
                player_elo,
            )

        return response

    def _join_queue_response(self, profile: PlayerProfile, request: JoinQueueRequest):
        active_match = self._mm_manager.find_match_with_player(profile)
        if active_match:
            return self._command_builder.build_match_ready(active_match)

        queue = self._mm_manager.get_queue(request.queue_id)
        if not queue:
            return ErrorResponse(
                "Unable to find requested queue. Please refresh queues"
            )

        num_players = queue.player_count()
        add_count = 0

        party_manager = get_party_manager()
        if party_manager:
            player_party = party_manager.get_player_party(profile)

        if player_party is not None:
            party_manager.update_party_activity(player_party)
            if not queue.queue.type.is_2v2():
                return ErrorResponse(
                    "This queue does not allow parties. Unparty in discord first"
                )

            teammate = player_party.teammate(profile)
            if self._mm_manager.is_player_in_match(teammate):
                return ErrorResponse(
                    "Your teammate is in a match. Please wait for their match to finish"
                )

            if not queue.is_player_queued(profile):
                result = self._mm_manager.add_party_to_queue(
                    player_party.players(), queue.queue.queue_id
                )
                if result is None:
                    return ErrorResponse("Unable to add your party to queue")
                add_count = len(player_party.players())

            party_members: list[dict] = []
            for player in player_party:
                player_elo = self._ddb_manager.get_or_create_player_elo(
                    player.tm_account_id, queue.queue.get_primary_leaderboard()
                )
                party_members.append(
                    {"TmAccountId": player.tm_account_id, "Points": player_elo.elo}
                )

            return JoinQueueResponse(num_players + add_count, party_members)
        else:
            if not queue.is_player_queued(profile):
                result = self._mm_manager.add_party_to_queue(
                    [profile], queue.queue.queue_id
                )
                if result is None:
                    return ErrorResponse("Unable to join queue")
                add_count = 1

            return JoinQueueResponse(num_players + add_count)

    def _leave_queue_response(self, profile: PlayerProfile, request: LeaveQueueRequest):
        if self._mm_manager.is_player_in_match(profile):
            return ErrorResponse("Cannot leave queue while in a match", True)

        party_manager = get_party_manager()
        if party_manager:
            player_party = party_manager.get_player_party(profile)

        if player_party is not None:
            self._mm_manager.remove_party_from_queue(
                player_party.players(), request.queue_id
            )
        else:
            self._mm_manager.remove_party_from_queue([profile], request.queue_id)

        return LeaveQueueResponse()

    def _get_leaderboards_response(
        self, profile: PlayerProfile, request: GetLeaderboardsRequest
    ):
        leaderboards: list[dict] = []
        leaderboard_ids: set[str] = set(
            [
                aq.queue.get_primary_leaderboard()
                for aq in self._mm_manager.active_queues
            ]
        )

        for leaderboard_id in leaderboard_ids:
            leaderboard = self._ddb_manager.get_leaderboard(leaderboard_id)

            player_elo = self._ddb_manager.get_or_create_player_elo(
                profile.tm_account_id, leaderboard.leaderboard_id
            )
            leaderboard_elos = self._ddb_manager.get_top_25_players_by_elo(
                leaderboard.leaderboard_id
            )

            leaderboards.append(
                {
                    "Id": leaderboard.display_name,
                    "Self": {
                        "TmAccountId": request.identifier(),
                        "Points": player_elo.elo,
                    },
                    "Players": [
                        {"TmAccountId": p.tm_account_id, "Points": p.elo}
                        for p in leaderboard_elos
                    ],
                }
            )

        return GetLeaderboardsResponse(leaderboards)

    def _get_stats_response(self, profile: PlayerProfile, request: GetStatsRequest):
        return GetStatsResponse()

    def _ping_response(self, profile: PlayerProfile, request: PingRequest):
        for active_queue in self._mm_manager.active_queues:
            if active_queue.is_player_queued(profile):
                return PingResponse(
                    active_queue.queue.queue_id, active_queue.player_count()
                )
        return PingResponse()

from aws.dynamodb import DynamoDbManager
from cogs.matchmaking_manager_v2 import get_matchmaking_manager_v2
from cogs.party_manager import get_party_manager
from matchmaking.match_queues.active_match_queue import ActiveMatchQueue
from models.player_profile import PlayerProfile
from plugin.command_builder import CommandBuilder
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
    LeavePartyRequest,
    AcceptPartyInviteRequest,
    CancelPartyInviteRequest,
)
from plugin.requests.ping import PingRequest
from plugin.responses.base_response import BaseResponse
from plugin.responses.error import ErrorResponse
from plugin.responses.initialize import InitializeResponse
from plugin.responses.get_queues import GetQueuesResponse
from plugin.responses.join_queue import JoinQueueResponse
from plugin.responses.leave_queue import LeaveQueueResponse
from plugin.responses.get_leaderboards import GetLeaderboardsResponse
from plugin.responses.get_stats import GetStatsResponse
from plugin.responses.party import (
    PartyInviteResponse,
    AcceptPartyInviteResponse,
    CancelPartyInviteResponse,
)
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

    async def build_response(self, request: BaseRequest) -> BaseResponse:
        profile: PlayerProfile = (
            self._ddb_manager.query_player_profile_for_tm_account_id(
                request.identifier()
            )
        )
        if not profile:
            return ErrorResponse("You have not registered your account yet", False)

        match request:
            case InitializeRequest():
                return self._get_initialize_response(profile, request)
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
            case PartyInviteRequest():
                return await self._get_party_invite_response(profile, request)
            case CancelPartyInviteRequest():
                return self._get_cancel_party_invite_response(profile, request)
            case AcceptPartyInviteRequest():
                return await self._get_accept_party_invite_response(profile, request)
            case LeavePartyRequest():
                return self._get_leave_party_response(profile, request)
            case PingRequest():
                return self._ping_response(profile, request)
            case InvalidVersionRequest():
                return ErrorResponse(
                    "Your plugin is out of date. Please update to the latest version!",
                    False,
                )
            case _:
                return ErrorResponse("Invalid request received", False)

    def _get_initialize_response(
        self, profile: PlayerProfile, request: InitializeRequest
    ) -> InitializeResponse:
        response = InitializeResponse()

        queues = self._get_queues_response(profile, request)
        response.add_queues(queues.payload().get("Queues"))

        current_queue = None
        for active_queue in self._mm_manager.active_queues:
            if active_queue.is_player_queued(profile):
                current_queue = active_queue
                break

        if current_queue is not None:
            response.add_current_queue(current_queue.queue.queue_id)

        party_manager = get_party_manager()
        if party_manager:
            player_party = party_manager.get_player_party(profile)
            if player_party is not None:
                party_manager.update_party_activity(player_party)

                if current_queue is not None:
                    for player in player_party:
                        player_elo = 0
                        try:
                            player_elo = self._ddb_manager.get_or_create_player_elo(
                                player.tm_account_id,
                                current_queue.queue.get_primary_leaderboard(),
                            ).elo
                        except Exception:
                            pass

                        response.add_party_member(player.tm_account_id, player_elo)
                else:
                    for player in player_party:
                        response.add_party_member(player.tm_account_id, -1)

        active_match = self._mm_manager.find_match_with_player(profile)
        if active_match:
            match_ready_command = self._command_builder.build_match_ready(active_match)
            response.add_match(match_ready_command.payload())

        return response

    def _get_queues_response(
        self, profile: PlayerProfile, request: GetQueuesResponse
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
        queue = self._mm_manager.get_queue(request.queue_id)
        if not queue:
            return ErrorResponse(
                "Unable to find requested queue. Please refresh queues"
            )

        my_elo = 0
        try:
            my_elo = self._ddb_manager.get_or_create_player_elo(
                profile.tm_account_id, queue.queue.get_primary_leaderboard()
            ).elo
        except Exception:
            pass

        response = JoinQueueResponse()
        response.add_queue(queue.queue.queue_id, queue.queue.display_name, my_elo)

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

            for player in player_party:
                player_elo = 0
                try:
                    player_elo = self._ddb_manager.get_or_create_player_elo(
                        player.tm_account_id, queue.queue.get_primary_leaderboard()
                    ).elo
                except Exception:
                    pass

                response.add_party_member(player.tm_account_id, player_elo)
        else:
            if not queue.is_player_queued(profile):
                result = self._mm_manager.add_party_to_queue(
                    [profile], queue.queue.queue_id
                )
                if result is None:
                    return ErrorResponse("Unable to join queue")
                add_count = 1

        response.set_player_count(num_players + add_count)
        return response

    def _leave_queue_response(self, profile: PlayerProfile, request: LeaveQueueRequest):
        if self._mm_manager.is_player_in_match(profile):
            return ErrorResponse("Cannot leave queue while in a match")

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
            if leaderboard_id is None:
                continue

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

    async def _get_party_invite_response(
        self, profile: PlayerProfile, request: PartyInviteRequest
    ) -> BaseResponse:
        invitee: PlayerProfile = (
            self._ddb_manager.query_player_profile_for_tm_account_id(request.invitee_id)
        )
        if not invitee:
            return ErrorResponse(
                "The player you invited has not registered with Better Matchmaking"
            )

        party_manager = get_party_manager()
        if party_manager:
            player_party = party_manager.get_player_party(profile)
            if player_party and invitee in player_party.players():
                return ErrorResponse("You are already in a party with this player!")

            await party_manager.add_outstanding_party_request(profile, invitee)

        return PartyInviteResponse(invitee.tm_account_id)

    def _get_cancel_party_invite_response(
        self, profile: PlayerProfile, request: CancelPartyInviteRequest
    ) -> BaseResponse:
        invitee: PlayerProfile = (
            self._ddb_manager.query_player_profile_for_tm_account_id(request.invitee_id)
        )
        if not invitee:
            return CancelPartyInviteResponse(request.invitee_id)

        party_manager = get_party_manager()
        if party_manager:
            active_requests = party_manager.get_outstanding_party_requests(profile)
            for party_request in active_requests:
                if party_request.accepter == invitee:
                    party_manager.remove_outstanding_party_request(party_request)
                    break

        return CancelPartyInviteResponse(invitee.tm_account_id)

    async def _get_accept_party_invite_response(
        self, profile: PlayerProfile, request: AcceptPartyInviteRequest
    ) -> BaseResponse:
        inviter: PlayerProfile = (
            self._ddb_manager.query_player_profile_for_tm_account_id(request.inviter_id)
        )

        found_invite = False
        party_manager = get_party_manager()
        if party_manager:
            active_requests = party_manager.get_outstanding_party_requests(inviter)
            for party_request in active_requests:
                if party_request.accepter == profile:
                    found_invite = True
                    await party_manager.add_accepted_party_request(party_request)
                    break

        if not found_invite:
            return ErrorResponse(
                "The invite you are trying to accept is no longer valid"
            )

        party = party_manager.get_player_party(profile)
        if party:
            response = AcceptPartyInviteResponse()
            for player in party.players():
                response.add_party_member(player.tm_account_id)

            return response

        return ErrorResponse("The party you are trying to join does not exist")

    def _get_leave_party_response(
        self, profile: PlayerProfile, request: LeavePartyRequest
    ) -> BaseRequest:
        party_manager = get_party_manager()
        if party_manager:
            party_manager.remove_party(profile)

        return self._command_builder.build_clear_party()

    def _ping_response(self, profile: PlayerProfile, request: PingRequest):
        for active_queue in self._mm_manager.active_queues:
            if active_queue.is_player_queued(profile):
                return PingResponse(
                    active_queue.queue.queue_id, active_queue.player_count()
                )
        return PingResponse()

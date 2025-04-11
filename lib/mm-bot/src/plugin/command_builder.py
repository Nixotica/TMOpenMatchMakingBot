from aws.dynamodb import DynamoDbManager
from matchmaking.match_queues.active_match_queue import ActiveMatchQueue
from matchmaking.matches.active_match import ActiveMatch
from matchmaking.matches.completed_match import CompletedMatch
from plugin.commands.queue_update import QueueUpdateCommand
from plugin.commands.match_ready import MatchReadyCommand
from plugin.commands.match_canceled import MatchCanceledCommand
from plugin.commands.match_results import MatchResultsCommand
from plugin.responses.leave_queue import LeaveQueueResponse


class CommandBuilder:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(CommandBuilder, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):  # Avoid re-initializing the instance
            self._initialized = True
            self._ddb_manager = DynamoDbManager()

    def build_queue_update(self, queue: ActiveMatchQueue) -> QueueUpdateCommand:
        return QueueUpdateCommand(
            queue_id=queue.queue.queue_id, player_count=queue.player_count()
        )

    def build_leave_queue(self) -> LeaveQueueResponse:
        return LeaveQueueResponse()

    def build_match_ready(self, match: ActiveMatch) -> MatchReadyCommand:
        command = MatchReadyCommand(
            match_id=match.match_id,
            club_name="Better Matchmaking",  # TODO: This should be retrieved by the club_id
            activity_name=match.event_name,
            is_team_mode=match.match_queue.type.is_2v2(),
        )

        join_link = match.get_match_join_link()
        if join_link:
            command.add_join_link(join_link)

        leaderboard_id = match.match_queue.get_primary_leaderboard()
        if match.match_queue.type.is_2v2():
            team_id = 0
            for team in match.teams():
                player_a_elo = self._ddb_manager.get_or_create_player_elo(
                    team.player_a.tm_account_id, leaderboard_id
                )
                player_b_elo = self._ddb_manager.get_or_create_player_elo(
                    team.player_b.tm_account_id, leaderboard_id
                )
                command.add_player(
                    team.player_a.tm_account_id, player_a_elo.elo, team_id
                )
                command.add_player(
                    team.player_b.tm_account_id, player_b_elo.elo, team_id
                )
                team_id += 1
        else:
            for player in match.participants():
                player_elo = self._ddb_manager.get_or_create_player_elo(
                    player.tm_account_id, leaderboard_id
                )
                command.add_player(player.tm_account_id, player_elo.elo)

        return command

    def build_match_results(self, match: CompletedMatch):
        if match.canceled:
            return MatchCanceledCommand(match_id=match.active_match.match_id)

        command = MatchResultsCommand(
            match_id=match.active_match.match_id,
            is_team_mode=match.active_match.match_queue.type.is_2v2(),
        )

        player_map = {}
        for player in match.updated_elo_ratings:
            player_map[player.tm_account_id] = player.elo

        if match.active_match.match_queue.type.is_2v2():
            for player in match.elo_differences:
                team_id = 0
                if player.tm_account_id in match.active_match.teams().team_b:
                    team_id = 1

                command.add_player(
                    player.tm_account_id,
                    player_map[player.tm_account_id],
                    player.elo,
                    team_id,
                )
        else:
            for player in match.elo_differences:
                command.add_player(
                    player.tm_account_id, player_map[player.tm_account_id], player.elo
                )

        return command

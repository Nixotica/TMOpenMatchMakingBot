from plugin.responses.base_response import BaseResponse


class MatchResultsCommand(BaseResponse):
    def __init__(self, match_id: str, is_team_mode: bool):
        super().__init__()
        self._match_id = match_id
        self._is_team_mode = is_team_mode
        self._players: list[dict] = []

    def name(self) -> str:
        return "MatchResults"

    def payload(self) -> dict:
        return {
            "MatchId": self._match_id,
            "IsTeamMode": self._is_team_mode,
            "Players": self._players,
        }

    def status_code(self):
        return 200

    def add_player(
        self, tm_account_id: str, new_elo: int, elo_diff: int, team: int = -1
    ):
        player = {
            "TmAccountId": tm_account_id,
            "Points": new_elo,
            "EloChange": elo_diff,
        }

        if team != -1:
            player["Team"] = team

        self._players.append(player)

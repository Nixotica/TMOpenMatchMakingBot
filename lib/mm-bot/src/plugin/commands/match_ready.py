from plugin.responses.base_response import BaseResponse


class MatchReadyCommand(BaseResponse):
    def __init__(
        self,
        match_id: str,
        club_name: str,
        activity_name: str,
        is_team_mode: str,
        join_link: str,
    ):
        super().__init__()
        self._match_id = match_id
        self._club_name = club_name
        self._activity_name = activity_name
        self._is_team_mode = is_team_mode
        self._join_link: str = join_link
        self._players: list[dict] = []

    def name(self) -> str:
        return "MatchReady"

    def payload(self) -> dict:
        data = {
            "Id": self._match_id,
            "ClubName": self._club_name,
            "ActivityName": self._activity_name,
            "IsTeamMode": self._is_team_mode,
            "Players": self._players,
            "Joinlink": self._join_link,
        }

        return data

    def status_code(self):
        return 200

    def add_player(self, tm_account_id: str, elo: int, team: int = -1):
        player = {"TmAccountId": tm_account_id, "Points": elo}

        if team != -1:
            player["Team"] = team

        self._players.append(player)

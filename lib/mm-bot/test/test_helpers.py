import unittest

from src.helpers import get_rank_for_player
from src.models.leaderboard_rank import LeaderboardRank

class TestHelpers(unittest.TestCase):
    def test_get_rank_for_player(self):
        player_elo = 100

        leaderboard_ranks = [
            LeaderboardRank("below", "test_lb", "Name", 0),
            LeaderboardRank("correct", "test_lb", "Name", 90),
            LeaderboardRank("wrong_lb", "wrong_lb", "Name", 95),
            LeaderboardRank("above", "test_lb", "Name", 110)
        ]

        lb = get_rank_for_player(player_elo, "test_lb", leaderboard_ranks)

        self.assertTrue(lb is not None)
        self.assertEqual(lb.rank_id, "correct")  # type: ignore

    def test_get_rank_for_player_no_rank(self):
        player_elo = 100

        leaderboard_ranks = [
            LeaderboardRank("wrong_lb", "wrong_lb", "Name", 95),
            LeaderboardRank("above", "test_lb", "Name", 110)
        ]

        lb = get_rank_for_player(player_elo, "test_lb", leaderboard_ranks)

        self.assertTrue(lb is None)
import unittest
from src.matchmaking.match_queues.active_match_queue import ActiveMatchQueue
from src.models.match_queue import MatchQueue
from src.models.player_profile import PlayerProfile
from src.matchmaking.match_queues.enum import QueueType


class TestActiveMatchQueues(unittest.TestCase):
    def setUp(self):
        self.player1 = PlayerProfile(
            tm_account_id="p1",
            discord_account_id=1,
            matches_played=2
        )
        self.player2 = PlayerProfile(
            tm_account_id="p2",
            discord_account_id=2,
            matches_played=1
        )

        self.active_match_queue = ActiveMatchQueue(
            match_queue=MatchQueue(
                queue_id="queue",
                campaign_id=1,
                campaign_club_id=1,
                match_club_id=1,
                type=QueueType.Queue1v1v1v1,
                active=True,
                channel_id=1,
                leaderboard_ids=["l1"],
                primary_leaderboard_id=None,
                ping_role_id=None,
            )
        )

    def test_add_player(self):
        added = self.active_match_queue.add_player(self.player1)
        self.assertTrue(added)

        added = self.active_match_queue.add_player(self.player2)
        self.assertTrue(added)

        player1_more_matches = PlayerProfile(
            tm_account_id="p1",
            discord_account_id=1,
            matches_played=3
        )
        added = self.active_match_queue.add_player(player1_more_matches)
        self.assertFalse(added)
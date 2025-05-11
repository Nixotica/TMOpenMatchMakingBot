import unittest
from unittest.mock import MagicMock, patch

from models.player_elo import PlayerElo
from src.matchmaking.match_queues.active_match_queue import ActiveMatchQueue
from src.matchmaking.match_queues.enum import QueueType
from src.models.match_queue import MatchQueue
from src.models.player_profile import PlayerProfile


class TestActiveMatchQueues(unittest.TestCase):
    def setUp(self):
        self.player1 = PlayerProfile(
            tm_account_id="p1", discord_account_id=1, matches_played=2
        )
        self.player2 = PlayerProfile(
            tm_account_id="p2", discord_account_id=2, matches_played=1
        )
        self.player3 = PlayerProfile(
            tm_account_id="p3", discord_account_id=3, matches_played=0
        )
        self.player4 = PlayerProfile(
            tm_account_id="p4", discord_account_id=4, matches_played=0
        )

        self.primary_leaderboard_id = "my_leaderboard_id"
        self.active_match_queue_1v1v1v1 = ActiveMatchQueue(
            match_queue=MatchQueue(
                queue_id="queue",
                campaign_id=1,
                campaign_club_id=1,
                match_club_id=1,
                type=QueueType.Queue1v1v1v1,
                active=True,
                channel_id=1,
                leaderboard_ids=["l1"],
                primary_leaderboard_id=self.primary_leaderboard_id,
                ping_role_id=None,
                display_name=None,
                category_id=None,
            )
        )

        self.active_match_queue_2v2 = ActiveMatchQueue(
            match_queue=MatchQueue(
                queue_id="queue",
                campaign_id=1,
                campaign_club_id=1,
                match_club_id=1,
                type=QueueType.Queue2v2,
                active=True,
                channel_id=1,
                leaderboard_ids=["l1"],
                primary_leaderboard_id=self.primary_leaderboard_id,
                ping_role_id=None,
                display_name=None,
                category_id=None,
            )
        )

    def test_add_party_single_player(self):
        added = self.active_match_queue_1v1v1v1.add_party(
            [
                self.player1,
            ]
        )
        self.assertTrue(added)

        added = self.active_match_queue_1v1v1v1.add_party(
            [
                self.player1,
            ]
        )
        self.assertFalse(added)

    def test_add_party_multiple_players(self):
        added = self.active_match_queue_1v1v1v1.add_party(
            [
                self.player1,
                self.player2,
            ]
        )
        self.assertTrue(added)

        # This fails because player1 is already in the queue
        added = self.active_match_queue_1v1v1v1.add_party(
            [
                self.player1,
                self.player3,
            ]
        )
        self.assertFalse(added)

    @patch.object(ActiveMatchQueue, "_get_ddb_manager")
    def test_get_2v2_teams_from_parties(self, mock_ddb_manager):
        mock_ddb = MagicMock()

        # Test the case where players are all solo queued
        mock_ddb.get_or_create_player_elo.side_effect = [
            PlayerElo(self.player1.tm_account_id, self.primary_leaderboard_id, 900),
            PlayerElo(self.player2.tm_account_id, self.primary_leaderboard_id, 1000),
            PlayerElo(self.player3.tm_account_id, self.primary_leaderboard_id, 1100),
            PlayerElo(self.player4.tm_account_id, self.primary_leaderboard_id, 1200),
        ]
        mock_ddb_manager.return_value = mock_ddb

        self.active_match_queue_2v2.add_party([self.player1])
        self.active_match_queue_2v2.add_party([self.player2])
        self.active_match_queue_2v2.add_party([self.player3])
        self.active_match_queue_2v2.add_party([self.player4])
        teams = self.active_match_queue_2v2._get_2v2_teams_from_parties()
        self.assertIsNotNone(teams)
        self.assertEqual(teams.team_a.player_a, self.player1)  # type: ignore
        self.assertEqual(teams.team_a.player_b, self.player4)  # type: ignore
        self.assertEqual(teams.team_b.player_a, self.player2)  # type: ignore
        self.assertEqual(teams.team_b.player_b, self.player3)  # type: ignore

        # Cleanup
        self.active_match_queue_2v2.remove_party([self.player1])
        self.active_match_queue_2v2.remove_party([self.player2])
        self.active_match_queue_2v2.remove_party([self.player3])
        self.active_match_queue_2v2.remove_party([self.player4])

        # Test the case where players are all in parties
        self.active_match_queue_2v2.add_party([self.player1, self.player2])
        self.active_match_queue_2v2.add_party([self.player3, self.player4])
        teams = self.active_match_queue_2v2._get_2v2_teams_from_parties()
        self.assertIsNotNone(teams)
        self.assertEqual(teams.team_a.player_a, self.player1)  # type: ignore
        self.assertEqual(teams.team_a.player_b, self.player2)  # type: ignore
        self.assertEqual(teams.team_b.player_a, self.player3)  # type: ignore
        self.assertEqual(teams.team_b.player_b, self.player4)  # type: ignore

        # Cleanup
        self.active_match_queue_2v2.remove_party([self.player1, self.player2])
        self.active_match_queue_2v2.remove_party([self.player3, self.player4])

        # Test the case where there are mixex parties and solo players
        self.active_match_queue_2v2.add_party([self.player1, self.player2])
        self.active_match_queue_2v2.add_party([self.player3])
        self.active_match_queue_2v2.add_party([self.player4])
        teams = self.active_match_queue_2v2._get_2v2_teams_from_parties()
        self.assertIsNotNone(teams)
        self.assertEqual(teams.team_a.player_a, self.player1)  # type: ignore
        self.assertEqual(teams.team_a.player_b, self.player2)  # type: ignore
        self.assertEqual(teams.team_b.player_a, self.player3)  # type: ignore
        self.assertEqual(teams.team_b.player_b, self.player4)  # type: ignore

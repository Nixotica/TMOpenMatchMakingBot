import datetime
import unittest
from unittest.mock import patch, MagicMock

from matchmaking.match_queues.enum import QueueType
from matchmaking.matches.active_match import ActiveMatch
from models.match_queue import MatchQueue
from models.player_profile import PlayerProfile


class TestActiveMatch(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.match_queue = MatchQueue(
            queue_id="test_queue",
            campaign_club_id=0,
            campaign_id=1,
            match_club_id=2,
            type=QueueType.Queue1v1,
            active=True,
            channel_id=0,
            leaderboard_ids=None,
            primary_leaderboard_id=None,
            ping_role_id=None,
            display_name=None,
            category_id=None,
        )

        self.player = PlayerProfile(
            tm_account_id="test_account", discord_account_id=123, matches_played=0
        )

        self.active_match = ActiveMatch(
            event_id=1,
            event_name="Test Event",
            round_id=1,
            match_id=1,
            match_live_id="test_live_id",
            match_join_link="http://test.link",
            bot_match_id=1,
            player_profiles=[self.player],
            match_queue=self.match_queue,
        )

    def test_creation_time_is_set(self):
        """Test that creation_time is set when ActiveMatch is created."""
        now = datetime.datetime.now(datetime.timezone.utc)
        self.assertIsInstance(self.active_match.creation_time, datetime.datetime)
        self.assertAlmostEqual(
            self.active_match.creation_time.timestamp(),
            now.timestamp(),
            delta=1.0  # Allow 1 second difference
        )

    def test_should_auto_cancel_not_enough_time_passed(self):
        """Test that should_auto_cancel returns False when not enough time has passed."""
        # Set creation time to now (should not auto-cancel)
        self.active_match.creation_time = datetime.datetime.now(datetime.timezone.utc)
        
        result = self.active_match.should_auto_cancel(timeout_minutes=5)
        self.assertFalse(result)

    @patch('matchmaking.matches.active_match.get_match_info')
    def test_should_auto_cancel_time_passed_not_ongoing_not_completed(self, mock_get_match_info):
        """Test auto-cancel when time has passed and match is neither ONGOING nor COMPLETED."""
        # Set creation time to 6 minutes ago
        six_minutes_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=6)
        self.active_match.creation_time = six_minutes_ago
        
        # Mock match info to return a status that should trigger cancellation
        mock_match_info = MagicMock()
        mock_match_info.status = "WAITING"
        mock_get_match_info.return_value = mock_match_info
        
        result = self.active_match.should_auto_cancel(timeout_minutes=5)
        self.assertTrue(result)
        mock_get_match_info.assert_called_once_with("test_live_id")

    @patch('matchmaking.matches.active_match.get_match_info')
    def test_should_auto_cancel_time_passed_but_ongoing(self, mock_get_match_info):
        """Test that ongoing matches are not auto-cancelled even if time has passed."""
        # Set creation time to 6 minutes ago
        six_minutes_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=6)
        self.active_match.creation_time = six_minutes_ago
        
        # Mock match info to return ONGOING status
        mock_match_info = MagicMock()
        mock_match_info.status = "ONGOING"
        mock_get_match_info.return_value = mock_match_info
        
        result = self.active_match.should_auto_cancel(timeout_minutes=5)
        self.assertFalse(result)

    @patch('matchmaking.matches.active_match.get_match_info')
    def test_should_auto_cancel_time_passed_but_completed(self, mock_get_match_info):
        """Test that completed matches are not auto-cancelled even if time has passed."""
        # Set creation time to 6 minutes ago
        six_minutes_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=6)
        self.active_match.creation_time = six_minutes_ago
        
        # Mock match info to return COMPLETED status
        mock_match_info = MagicMock()
        mock_match_info.status = "COMPLETED"
        mock_get_match_info.return_value = mock_match_info
        
        result = self.active_match.should_auto_cancel(timeout_minutes=5)
        self.assertFalse(result)

    def test_should_auto_cancel_simulated_match(self):
        """Test that simulated matches are never auto-cancelled."""
        # Create a simulated match queue
        sim_queue = MatchQueue(
            queue_id="sim_queue",
            campaign_club_id=0,
            campaign_id=1,
            match_club_id=2,
            type=QueueType.QueueSim2v2,
            active=True,
            channel_id=0,
            leaderboard_ids=None,
            primary_leaderboard_id=None,
            ping_role_id=None,
            display_name=None,
            category_id=None,
        )

        sim_match = ActiveMatch(
            event_id=1,
            event_name="Sim Test Event",
            round_id=1,
            match_id=1,
            match_live_id="sim_live_id",
            match_join_link="http://sim.link",
            bot_match_id=2,
            player_profiles=[self.player],
            match_queue=sim_queue,
        )

        # Set creation time to 10 minutes ago (well past timeout)
        ten_minutes_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)
        sim_match.creation_time = ten_minutes_ago
        
        result = sim_match.should_auto_cancel(timeout_minutes=5)
        self.assertFalse(result)

    def test_should_auto_cancel_custom_timeout(self):
        """Test should_auto_cancel with a custom timeout value."""
        # Set creation time to 2 minutes ago
        two_minutes_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=2)
        self.active_match.creation_time = two_minutes_ago
        
        # Should not auto-cancel with 5 minute timeout
        result_5min = self.active_match.should_auto_cancel(timeout_minutes=5)
        self.assertFalse(result_5min)
        
        # Should auto-cancel with 1 minute timeout (need to mock get_match_info)
        with patch('matchmaking.matches.active_match.get_match_info') as mock_get_match_info:
            mock_match_info = MagicMock()
            mock_match_info.status = "WAITING"
            mock_get_match_info.return_value = mock_match_info
            
            result_1min = self.active_match.should_auto_cancel(timeout_minutes=1)
            self.assertTrue(result_1min)


if __name__ == '__main__':
    unittest.main()
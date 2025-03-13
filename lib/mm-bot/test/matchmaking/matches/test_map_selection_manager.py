import unittest
from unittest.mock import MagicMock, patch

from matchmaking.match_queues.enum import QueueType
from matchmaking.matches.map_selection_manager import MapSelectionManager
from models.match_queue import MatchQueue


@patch("matchmaking.matches.map_selection_manager.MapSelectionManager._get_campaign")
class TestMapSelectionManager(unittest.TestCase):
    def setUp(self):
        self.campaign = MagicMock()
        self.campaign._playlist = [MagicMock(_uuid="map1"), MagicMock(_uuid="map2")]
        self.match_queue_1 = MatchQueue(
            "queue_1",
            0,
            0,
            0,
            QueueType.Queue1v1v1v1,
            True,
            0,
            None,
            None,
            None,
            None,
            None,
        )
        self.match_queue_2 = MatchQueue(
            "queue_2",
            0,
            0,
            0,
            QueueType.Queue2v2,
            True,
            0,
            None,
            None,
            None,
            None,
            None,
        )
        self.map_selection_manager = MapSelectionManager()

    @patch(
        "random.randint", side_effect=[0, 0, 1, 0]
    )  # Return map 0, then return map 1 (avoid repeat), then 0 again (not direct repeat)
    def test_get_random_map_avoid_repeats_same_queue(self, _, mock_get_campaign):
        MapSelectionManager().last_played_maps_by_queue = {}
        mock_get_campaign.return_value = self.campaign

        first_map = self.map_selection_manager.get_random_map(self.match_queue_1)
        self.assertEqual(first_map._uuid, "map1")

        second_map = self.map_selection_manager.get_random_map(self.match_queue_1)
        self.assertEqual(second_map._uuid, "map2")

        third_map = self.map_selection_manager.get_random_map(self.match_queue_1)
        self.assertEqual(third_map._uuid, "map1")

    @patch(
        "random.randint", side_effect=[0, 0]
    )  # Return map 0, then return map 0 (allow repeat different queue)
    def test_get_random_map_avoid_repeats_different_queue_allow_same_map(
        self, _, mock_get_campaign
    ):
        MapSelectionManager().last_played_maps_by_queue = {}
        mock_get_campaign.return_value = self.campaign

        first_map_queue_1 = self.map_selection_manager.get_random_map(
            self.match_queue_1
        )
        self.assertEqual(first_map_queue_1._uuid, "map1")

        first_map_queue_2 = self.map_selection_manager.get_random_map(
            self.match_queue_2
        )
        self.assertEqual(first_map_queue_2._uuid, "map1")

    @patch(
        "random.randint", side_effect=[0, 0]
    )  # Return map 0, then return map 0 (allow repeat same queue)
    def test_get_random_map_allow_repeats_allow_same_map(self, _, mock_get_campaign):
        MapSelectionManager().last_played_maps_by_queue = {}
        mock_get_campaign.return_value = self.campaign

        first_map = self.map_selection_manager.get_random_map(self.match_queue_1)
        self.assertEqual(first_map._uuid, "map1")

        second_map = self.map_selection_manager.get_random_map(
            self.match_queue_1, avoid_repeats=False
        )
        self.assertEqual(second_map._uuid, "map1")

    @patch(
        "random.randint", side_effect=[0, 0]
    )  # Return map 0, then return map 0 (allow repeat if only 1 map in campaign)
    def test_get_random_map_allow_repeats_if_only_1_map_in_campaign(
        self, _, mock_get_campaign
    ):
        MapSelectionManager().last_played_maps_by_queue = {}
        campaign_one_map = MagicMock()
        campaign_one_map._playlist = [MagicMock(_uuid="map1")]
        mock_get_campaign.return_value = campaign_one_map

        first_map = self.map_selection_manager.get_random_map(self.match_queue_1)
        self.assertEqual(first_map._uuid, "map1")

        second_map = self.map_selection_manager.get_random_map(self.match_queue_1)
        self.assertEqual(second_map._uuid, "map1")

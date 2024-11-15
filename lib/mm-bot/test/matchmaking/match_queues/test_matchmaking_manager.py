import unittest
from unittest.mock import MagicMock, patch

import pytest
from src.matchmaking.match_queues.matchmaking_manager import MatchmakingManager
from src.models.player_profile import PlayerProfile
from src.models.match_queue import MatchQueue
from src.models.leaderboard import Leaderboard
from src.matchmaking.match_queues.enum import QueueType
from src.matchmaking.matches.active_match import ActiveMatch

# TODO - enable this test later if there are issues 
# class TestMatchmakingManager:
#     @pytest.mark.asyncio
#     async def test_check_if_should_queue_matches_generated_match_removes_players_from_all_active_queues(
#         self,
#     ):
#         self.leaderboard_1 = Leaderboard("leaderboard_1", 1)
#         self.leaderboard_2 = Leaderboard("leaderboard_2", 2)

#         self.queue_1 = MatchQueue(
#             "queue_1",
#             1,
#             2,
#             3,
#             QueueType.Queue1v1v1v1,
#             True,
#             1,
#             [self.leaderboard_1.leaderboard_id],
#         )
#         self.queue_2 = MatchQueue(
#             "queue_2",
#             2,
#             2,
#             3,
#             QueueType.Queue1v1v1v1,
#             True,
#             2,
#             [self.leaderboard_1.leaderboard_id, self.leaderboard_2.leaderboard_id],
#         )

#         # Setup matchmaking manager with 2 queues with two leaderboards (one global, one for queue 2 only)
#         with patch(
#             "src.matchmaking.match_queues.matchmaking_manager.DynamoDbManager"
#         ) as MockDdbManager:
#             mock_ddb_instance = MagicMock()
#             mock_ddb_instance.get_active_match_queues.return_value = [
#                 self.queue_1,
#                 self.queue_2,
#             ]

#             MockDdbManager.return_value = mock_ddb_instance

#             self.mm_manager = MatchmakingManager()

#         self.player_1 = PlayerProfile("tm_1", 1, 0)
#         self.player_2 = PlayerProfile("tm_2", 2, 0)
#         self.player_3 = PlayerProfile("tm_3", 3, 0)
#         self.player_4 = PlayerProfile("tm_4", 4, 0)

#         # Add the queues to mm manager
#         self.mm_manager.add_queue(self.queue_1)
#         self.mm_manager.add_queue(self.queue_2)

#         # Simulate 3 players joining queue 1
#         self.mm_manager.add_player_to_queue(self.player_1, self.queue_1.queue_id)
#         self.mm_manager.add_player_to_queue(self.player_2, self.queue_1.queue_id)
#         self.mm_manager.add_player_to_queue(self.player_3, self.queue_1.queue_id)

#         # Simulate 2 players joining queue 2
#         self.mm_manager.add_player_to_queue(self.player_1, self.queue_2.queue_id)
#         self.mm_manager.add_player_to_queue(self.player_2, self.queue_2.queue_id)

#         # Verify that there are 3 players in queue 1 and 2 players in queue 2
#         active_queue_1 = self.mm_manager.get_active_queue_by_id(self.queue_1.queue_id)
#         assert active_queue_1 is not None
#         assert len(active_queue_1.players) == 3

#         active_queue_2 = self.mm_manager.get_active_queue_by_id(self.queue_2.queue_id)
#         assert active_queue_2 is not None
#         assert len(active_queue_2.players) == 2

#         # Run method under test
#         mock_active_match = ActiveMatch(
#             0,
#             0,
#             0,
#             "live_id",
#             0,
#             [self.player_1, self.player_2, self.player_3, self.player_4],
#             self.queue_1,
#         )
#         with patch.object(
#             active_queue_1, "try_generate_match", return_value=mock_active_match
#         ):
#             await self.mm_manager._check_if_should_queue_matches()

#             # Verify the mock active match was added to the list of new active matches
#             new_active_matches = self.mm_manager.new_active_matches
#             assert len(new_active_matches) == 1
#             assert new_active_matches[0] == mock_active_match

#             # Verify the queue length of both queues is 0
#             updated_active_queue_1 = self.mm_manager.get_active_queue_by_id(
#                 self.queue_1.queue_id
#             )
#             assert len(updated_active_queue_1.players) == 0  # type: ignore

#             updated_active_queue_2 = self.mm_manager.get_active_queue_by_id(
#                 self.queue_2.queue_id
#             )
#             assert len(updated_active_queue_2.players) == 0  # type: ignore

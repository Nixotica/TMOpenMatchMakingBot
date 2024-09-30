import unittest
from typing import Dict
from src.models.player_elo import PlayerElo
from src.matchmaking.match_complete.calculate_elo import calculate_elo_ratings  # Assuming this code is in a module called elo_system

class TestEloSystem(unittest.TestCase):
    
    def setUp(self):
        # Create player profiles 
        self.player1 = PlayerElo(
            "tm_acc_1",
            "leaderboard_id",
            1200,
        )
        self.player2 = PlayerElo(
            "tm_acc_2",
            "leaderboard_id",
            1300,
        )
        self.player3 = PlayerElo(
            "tm_acc_3",
            "leaderboard_id",
            1100,
        )
        self.player4 = PlayerElo(
            "tm_acc_4",
            "leaderboard_id",
            1000,
        )

        self.match_positions = {
            self.player1: 1,
            self.player2: 2,
            self.player3: 3,
            self.player4: 4,
        }

    def test_calculate_elo_ratings(self):
        # Test calculating Elo ratings for multiple players based on match positions
        updated_ratings, elo_differences = calculate_elo_ratings(self.match_positions)

        # Make sure the returned data is in the correct format
        self.assertIsInstance(updated_ratings, dict)
        self.assertIsInstance(elo_differences, dict)

        # Check if updated Elo ratings and differences are correctly calculated
        # These values depend on the Elo calculation, but the expected behavior can be checked
        self.assertIn(self.player1, updated_ratings)
        self.assertIn(self.player2, updated_ratings)
        self.assertIn(self.player3, updated_ratings)
        self.assertIn(self.player4, updated_ratings)

        # Ensure that the Elo difference isn't zero for all players, indicating change
        self.assertNotEqual(elo_differences[self.player1], 0)
        self.assertNotEqual(elo_differences[self.player2], 0)
        self.assertNotEqual(elo_differences[self.player3], 0)

    def test_elo_differences_sum_to_zero(self):
        # Ensure that the sum of all Elo differences is approximately zero (conservation principle)
        updated_ratings, elo_differences = calculate_elo_ratings(self.match_positions)

        # The sum of differences should be approximately zero
        total_difference = sum(elo_differences.values())
        self.assertAlmostEqual(total_difference, 0, places=5)

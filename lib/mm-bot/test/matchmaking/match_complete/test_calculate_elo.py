import unittest

from matchmaking.match_complete.match_positions_2v2 import MatchPositions2v2
from matchmaking.matches.team_2v2 import Team2v2, Teams2v2
from models.player_profile import PlayerProfile
from nadeo_event_api.objects.inbound.match_results import (
    MatchResults,
    RankedParticipant,
    RankedTeam,
)
from src.matchmaking.match_complete.calculate_elo import (  # Assuming this code is in a module called elo_system
    UpdatedElos,
    calculate_elo_2v2_ratings,
    calculate_elo_ratings,
    get_team_points_multiplier,
)
from src.models.player_elo import PlayerElo


class TestEloSystem(unittest.TestCase):
    def setUp(self):
        # Create player profiles
        p1_acc = "tm_acc_1"
        self.player1 = PlayerProfile(
            tm_account_id=p1_acc,
            discord_account_id=1,
            matches_played=0,
        )
        self.player1_elo = PlayerElo(
            p1_acc,
            "leaderboard_id",
            1200,
        )

        p2_acc = "tm_acc_2"
        self.player2 = PlayerProfile(
            tm_account_id=p2_acc,
            discord_account_id=2,
            matches_played=0,
        )
        self.player2_elo = PlayerElo(
            p2_acc,
            "leaderboard_id",
            1300,
        )

        p3_acc = "tm_acc_3"
        self.player3 = PlayerProfile(
            tm_account_id=p3_acc,
            discord_account_id=3,
            matches_played=0,
        )
        self.player3_elo = PlayerElo(
            p3_acc,
            "leaderboard_id",
            1100,
        )

        p4_acc = "tm_acc_4"
        self.player4 = PlayerProfile(
            tm_account_id=p4_acc,
            discord_account_id=4,
            matches_played=0,
        )
        self.player4_elo = PlayerElo(
            p4_acc,
            "leaderboard_id",
            1000,
        )

        self.player_elos = [
            self.player1_elo,
            self.player2_elo,
            self.player3_elo,
            self.player4_elo,
        ]

        self.match_positions = {
            self.player1_elo: 1,
            self.player2_elo: 2,
            self.player3_elo: 3,
            self.player4_elo: 4,
        }

        self.match_positions_2v2: MatchPositions2v2 = MatchPositions2v2(
            teams=Teams2v2(
                team_a=Team2v2(
                    name="team_a",
                    player_a=self.player1,
                    player_b=self.player2,
                ),
                team_b=Team2v2(
                    name="team_b",
                    player_a=self.player3,
                    player_b=self.player4,
                ),
            ),
            # Team A (P1, P2) loses, player order P1, P4, P3, P2
            results=MatchResults(
                match_live_id="abc",
                round_position=0,
                results=[
                    RankedParticipant(
                        participant=p1_acc, rank=1, score=0, zone=None, team="team_a"
                    ),
                    RankedParticipant(
                        participant=p2_acc, rank=4, score=0, zone=None, team="team_a"
                    ),
                    RankedParticipant(
                        participant=p3_acc, rank=3, score=1, zone=None, team="team_b"
                    ),
                    RankedParticipant(
                        participant=p4_acc, rank=2, score=1, zone=None, team="team_b"
                    ),
                ],
                teams=[
                    RankedTeam(
                        position=2,
                        team="team_a",
                        rank=2,
                        score=0,
                    ),
                    RankedTeam(
                        position=1,
                        team="team_b",
                        rank=1,
                        score=1,
                    ),
                ],
            ),
        )

    def test_get_team_points_multiplier(self):
        # Test getting the points multiplier for a player based on their position relative to teammate
        player_elo = PlayerElo("acc", "lb", 1000)

        # Always 50/50 split for 1st and 2nd win or lose
        self.assertEqual(get_team_points_multiplier(player_elo, 1, 2, True), 0.5)
        self.assertEqual(get_team_points_multiplier(player_elo, 1, 2, False), 0.5)
        self.assertEqual(get_team_points_multiplier(player_elo, 2, 1, True), 0.5)
        self.assertEqual(get_team_points_multiplier(player_elo, 2, 1, False), 0.5)

        # Always 50/50 split for 2nd/3rd win or lose
        self.assertEqual(get_team_points_multiplier(player_elo, 2, 3, True), 0.5)
        self.assertEqual(get_team_points_multiplier(player_elo, 2, 3, False), 0.5)
        self.assertEqual(get_team_points_multiplier(player_elo, 3, 2, True), 0.5)
        self.assertEqual(get_team_points_multiplier(player_elo, 3, 2, False), 0.5)

        # Always 50/50 split for 3rd/4th win or lose
        self.assertEqual(get_team_points_multiplier(player_elo, 3, 4, True), 0.5)
        self.assertEqual(get_team_points_multiplier(player_elo, 3, 4, False), 0.5)

        # 60/40 split for 1st/3rd win
        self.assertEqual(get_team_points_multiplier(player_elo, 1, 3, True), 0.6)

        # 40/60 split for 1st/3rd lose
        self.assertEqual(get_team_points_multiplier(player_elo, 1, 3, False), 0.4)

        # 80/20 split for 1st/4th win
        self.assertEqual(get_team_points_multiplier(player_elo, 1, 4, True), 0.8)

        # 20/80 split for 1st/4th lose
        self.assertEqual(get_team_points_multiplier(player_elo, 1, 4, False), 0.2)

        # 70/30 split for 2nd/4th win
        self.assertEqual(get_team_points_multiplier(player_elo, 2, 4, True), 0.7)

        # 30/70 split for 2nd/4th lose
        self.assertEqual(get_team_points_multiplier(player_elo, 2, 4, False), 0.3)

    def test_calculate_elo_2v2_ratings(self):
        # Test calculating Elo ratings for 2v2 matches also accounting for match positions
        updated_elos: UpdatedElos = calculate_elo_2v2_ratings(
            self.match_positions_2v2, self.player_elos
        )
        updated_ratings = updated_elos.updated_elo_ratings
        elo_differences = updated_elos.elo_differences

        # Ensure all players are in the updated elo
        self.assertIn(self.player1_elo, updated_ratings)
        self.assertIn(self.player2_elo, updated_ratings)
        self.assertIn(self.player3_elo, updated_ratings)
        self.assertIn(self.player4_elo, updated_ratings)

        # Make sure the returned data is in the correct format
        self.assertIsInstance(updated_ratings, dict)
        self.assertIsInstance(elo_differences, dict)

        # Ensure both players of the winning team have positive elo diff
        self.assertGreater(elo_differences[self.player3_elo], 0)
        self.assertGreater(elo_differences[self.player4_elo], 0)

        # Ensure both players of the losing team have negative elo diff
        self.assertLess(elo_differences[self.player1_elo], 0)
        self.assertLess(elo_differences[self.player2_elo], 0)

        # Ensure that since P1 came in last and P2 came in first, P2 elo diff is approx 4x P1 elo diff
        # (0.8/0.2) - accounting for the fact we have to round (-3.2 -> -3, -12.8 -> -13)
        self.assertAlmostEqual(
            elo_differences[self.player1_elo] * 4,
            elo_differences[self.player2_elo],
            delta=1,
        )

        # Ensure that since P3 came in third and P4 came in second, P3 and P4 have same elo diff (0.5/0.5)
        self.assertAlmostEqual(
            elo_differences[self.player3_elo],
            elo_differences[self.player4_elo],
            places=5,
        )

        # Ensure that the sum of all Elo differences is approximately zero (conservation principle)
        total_difference = sum(elo_differences.values())
        self.assertAlmostEqual(total_difference, 0, places=5)

    def test_calculate_elo_ratings(self):
        # Test calculating Elo ratings for multiple players based on match positions
        updated_elos: UpdatedElos = calculate_elo_ratings(self.match_positions)
        updated_ratings = updated_elos.updated_elo_ratings
        elo_differences = updated_elos.elo_differences

        # Make sure the returned data is in the correct format
        self.assertIsInstance(updated_ratings, dict)
        self.assertIsInstance(elo_differences, dict)

        # Check if updated Elo ratings and differences are correctly calculated
        # These values depend on the Elo calculation, but the expected behavior can be checked
        self.assertIn(self.player1_elo, updated_ratings)
        self.assertIn(self.player2_elo, updated_ratings)
        self.assertIn(self.player3_elo, updated_ratings)
        self.assertIn(self.player4_elo, updated_ratings)

        # Ensure that the Elo difference isn't zero for all players, indicating change
        self.assertNotEqual(elo_differences[self.player1_elo], 0)
        self.assertNotEqual(elo_differences[self.player2_elo], 0)
        self.assertNotEqual(elo_differences[self.player3_elo], 0)

    def test_elo_differences_sum_to_zero(self):
        # Ensure that the sum of all Elo differences is approximately zero (conservation principle)
        updated_elos: UpdatedElos = calculate_elo_ratings(self.match_positions)
        updated_ratings = updated_elos.updated_elo_ratings
        elo_differences = updated_elos.elo_differences

        # The sum of differences should be approximately zero
        total_difference = sum(elo_differences.values())
        self.assertAlmostEqual(total_difference, 0, places=5)

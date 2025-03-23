from datetime import timedelta
import time
import unittest

from matchmaking.match_complete.match_positions_2v2 import MatchPositions2v2
from matchmaking.match_queues.enum import QueueType
from matchmaking.matches.simulator import MatchSimulator
from matchmaking.matches.team_2v2 import Team2v2, Teams2v2
from models.match_queue import MatchQueue
from models.player_profile import PlayerProfile


class TestSimulator(unittest.TestCase):
    def test_round_trip_2v2_match_simulation(self):
        # Set up the circumstances
        match_queue = MatchQueue(
            queue_id="test_queue",
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

        bot_match_id = 1

        p1 = PlayerProfile(
            tm_account_id="tmacc_1", discord_account_id=0, matches_played=0
        )
        p2 = PlayerProfile(
            tm_account_id="tmacc_2", discord_account_id=0, matches_played=0
        )
        p3 = PlayerProfile(
            tm_account_id="tmacc_3", discord_account_id=0, matches_played=0
        )
        p4 = PlayerProfile(
            tm_account_id="tmacc_4", discord_account_id=0, matches_played=0
        )

        team_a = Team2v2(
            name="team_a",
            player_a=p1,
            player_b=p2,
        )
        team_b = Team2v2(
            name="team_b",
            player_a=p3,
            player_b=p4,
        )
        teams = Teams2v2(
            team_a=team_a,
            team_b=team_b,
        )

        match_duration = timedelta(seconds=1)

        # Create a simulated 2v2 match
        active_match = MatchSimulator().create_sim_2v2_match(
            match_queue=match_queue,
            bot_match_id=bot_match_id,
            teams=teams,
            duration=match_duration,
        )

        # Immediately check if it's complete (should be False)
        self.assertFalse(MatchSimulator().is_match_complete(bot_match_id))

        # Wait for the duration, then check again (should be True)
        time.sleep(match_duration.total_seconds())
        self.assertTrue(MatchSimulator().is_match_complete(bot_match_id))

        # Verify that the simulated match has been purged
        self.assertEqual(MatchSimulator().get_simulated_matches(), [])

        # Check the match results
        match_results = MatchSimulator().get_match_results(bot_match_id)
        match_positions = MatchPositions2v2(teams=teams, results=match_results)

        # Verify that blue team won, red team lost
        team_results = match_positions.team_results()
        self.assertEqual(team_results.get(team_a), 1)
        self.assertEqual(team_results.get(team_b), 2)

        # Verify that all players are present in individual results
        individual_results = match_positions.individual_results()
        self.assertTrue(p1 in individual_results.keys())
        self.assertTrue(p2 in individual_results.keys())
        self.assertTrue(p3 in individual_results.keys())
        self.assertTrue(p4 in individual_results.keys())

        # Verify that the match results were deleted
        self.assertEqual(MatchSimulator().get_match_results(bot_match_id), None)

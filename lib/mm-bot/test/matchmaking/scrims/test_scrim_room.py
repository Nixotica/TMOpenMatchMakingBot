import unittest
from unittest.mock import AsyncMock, patch

from matchmaking.match_queues.constants import TEAM_BLUE, TEAM_RED
from matchmaking.match_queues.enum import QueueType
from matchmaking.scrims.constants import SCRIM_INVITE_EXPIRATION_SEC
from matchmaking.scrims.scrim_mappack import ScrimMappack
from matchmaking.scrims.scrim_mode import ScrimMode
from matchmaking.scrims.scrim_room import ScrimRoom
from models.player_profile import PlayerProfile


def make_player(idx: int) -> PlayerProfile:
    return PlayerProfile(
        tm_account_id=f"p{idx}", discord_account_id=idx, matches_played=0
    )


class TestScrimRoom(unittest.TestCase):
    def setUp(self):
        self.p1, self.p2, self.p3, self.p4, self.p5 = [
            make_player(i) for i in range(1, 6)
        ]
        self.mappack = ScrimMappack("Mappack", 10, 20, match_club_id=30)
        self.room = ScrimRoom(room_id=123, host=self.p1)
        self.room.add_player(self.p1, TEAM_BLUE)

    def test_add_player_balances_sides(self):
        # Invited players join the host's opponents first, then whichever side is short
        self.assertTrue(self.room.add_player(self.p2))
        self.assertEqual(self.room.side_of(self.p2.discord_account_id), TEAM_RED)

        self.assertTrue(self.room.add_player(self.p3))
        self.assertEqual(self.room.side_of(self.p3.discord_account_id), TEAM_RED)

        self.assertTrue(self.room.add_player(self.p4))
        self.assertEqual(self.room.side_of(self.p4.discord_account_id), TEAM_BLUE)

    def test_add_player_on_given_side(self):
        # A party teammate joins their teammate's side, even if it makes the sides uneven
        self.assertTrue(self.room.add_player(self.p2, TEAM_BLUE))
        self.assertTrue(self.room.add_player(self.p3, TEAM_BLUE))
        self.assertEqual(len(self.room.players_on(TEAM_BLUE)), 3)
        self.assertEqual(self.room.players_on(TEAM_RED), [])

    def test_add_player_rejects_duplicates_and_full_room(self):
        self.assertFalse(self.room.add_player(self.p1))

        for player in (self.p2, self.p3, self.p4):
            self.assertTrue(self.room.add_player(player))
        self.assertTrue(self.room.is_full())
        self.assertFalse(self.room.add_player(self.p5))
        self.assertEqual(len(self.room.players()), 4)

    def test_add_player_clears_their_invite(self):
        self.assertTrue(self.room.add_invite(self.p2, self.p1))
        self.assertFalse(self.room.add_invite(self.p2, self.p1))

        self.room.add_player(self.p2)
        self.assertNotIn(self.p2.discord_account_id, self.room.invites)

        # Players in the room can't be invited
        self.assertFalse(self.room.add_invite(self.p2, self.p1))

    def test_remove_player(self):
        self.room.add_player(self.p2)

        removed = self.room.remove_player(self.p2.discord_account_id)
        self.assertEqual(removed, self.p2)
        self.assertFalse(self.room.has_player(self.p2.discord_account_id))
        self.assertIsNone(self.room.remove_player(self.p2.discord_account_id))

    def test_switch_side(self):
        self.room.add_player(self.p2)

        self.assertTrue(self.room.switch_side(self.p2.discord_account_id))
        self.assertEqual(self.room.side_of(self.p2.discord_account_id), TEAM_BLUE)
        self.assertTrue(self.room.switch_side(self.p2.discord_account_id))
        self.assertEqual(self.room.side_of(self.p2.discord_account_id), TEAM_RED)

        self.assertFalse(self.room.switch_side(self.p5.discord_account_id))

    def test_expired_invites(self):
        self.room.add_invite(self.p2, self.p1)
        sent_time = self.room.invites[self.p2.discord_account_id].sent_time

        self.assertEqual(self.room.expired_invites(sent_time + 1), [])

        expired = self.room.expired_invites(sent_time + SCRIM_INVITE_EXPIRATION_SEC + 1)
        self.assertEqual([invite.invitee for invite in expired], [self.p2])

    def test_start_blockers_need_mode_and_mappack(self):
        blockers = self.room.start_blockers()
        self.assertIn("Choose a mode.", blockers)
        self.assertIn("Choose a mappack.", blockers)

    def test_start_blockers_player_count(self):
        self.room.mode = ScrimMode.Mode1v1
        self.room.mappack = self.mappack
        self.assertEqual(len(self.room.start_blockers()), 1)

        self.room.add_player(self.p2)
        self.assertEqual(self.room.start_blockers(), [])

        self.room.add_player(self.p3)
        self.assertEqual(len(self.room.start_blockers()), 1)

    def test_start_blockers_team_mode_needs_even_teams(self):
        self.room.mode = ScrimMode.Mode2v2
        self.room.mappack = self.mappack
        for player in (self.p2, self.p3, self.p4):
            self.room.add_player(player, TEAM_RED)
        self.assertEqual(len(self.room.start_blockers()), 1)

        self.room.switch_side(self.p4.discord_account_id)
        self.assertEqual(self.room.start_blockers(), [])

        # Free for all modes ignore sides
        self.room.switch_side(self.p4.discord_account_id)
        self.room.mode = ScrimMode.Mode1v1v1v1
        self.assertEqual(self.room.start_blockers(), [])

    def test_teams(self):
        self.room.add_player(self.p2)
        self.room.add_player(self.p3)
        with self.assertRaises(ValueError):
            self.room.teams()

        self.room.add_player(self.p4)
        teams = self.room.teams()
        self.assertEqual(teams.team_a.name, TEAM_BLUE)
        self.assertEqual(list(teams.team_a), [self.p1, self.p4])
        self.assertEqual(teams.team_b.name, TEAM_RED)
        self.assertEqual(list(teams.team_b), [self.p2, self.p3])

    def test_to_match_queue_is_unranked_scrim(self):
        with self.assertRaises(ValueError):
            self.room.to_match_queue(match_club_id=1)

        self.room.mode = ScrimMode.Mode2v2Bo5
        self.room.mappack = self.mappack
        queue = self.room.to_match_queue(match_club_id=99)

        self.assertTrue(queue.is_scrim)
        self.assertEqual(queue.queue_id, "scrim-123")
        self.assertEqual(queue.type, QueueType.QueueScrim2v2)
        self.assertEqual(queue.campaign_club_id, 10)
        self.assertEqual(queue.campaign_id, 20)
        self.assertEqual(queue.match_club_id, 99)
        self.assertIsNone(queue.leaderboard_ids)
        self.assertIsNone(queue.get_primary_leaderboard())

        # Scrim flag isn't stored, since scrim queues never are
        self.assertNotIn("is_scrim", queue.to_dict())


class TestScrimRoomCreateMatch(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.players = [make_player(i) for i in range(1, 5)]
        self.room = ScrimRoom(room_id=1, host=self.players[0])
        for player in self.players:
            self.room.add_player(player)
        self.room.mappack = ScrimMappack("Mappack", 10, 20)

    async def test_create_match_dispatches_on_mode(self):
        cases = [
            (ScrimMode.Mode2v2, "create_2v2", self.room.teams()),
            (ScrimMode.Mode2v2Bo5, "create_2v2_scrim", self.room.teams()),
            (ScrimMode.Mode1v1v1v1, "create_1v1v1v1", self.players),
        ]
        for mode, create_method, participants in cases:
            self.room.mode = mode
            with patch(
                f"matchmaking.scrims.scrim_room.ActiveMatch.{create_method}",
                new_callable=AsyncMock,
            ) as create:
                await self.room.create_match(match_club_id=5, bot_match_id=7)

                match_queue, bot_match_id, match_participants = create.call_args.args
                self.assertTrue(match_queue.is_scrim)
                self.assertEqual(match_queue.type, mode.queue_type())
                self.assertEqual(bot_match_id, 7)
                self.assertEqual(match_participants, participants)


class TestScrimMode(unittest.TestCase):
    def test_modes(self):
        self.assertEqual(ScrimMode("2v2"), ScrimMode.Mode2v2)
        self.assertTrue(ScrimMode.Mode2v2.is_team_mode())
        self.assertTrue(ScrimMode.Mode2v2Bo5.is_team_mode())
        self.assertFalse(ScrimMode.Mode1v1v1v1.is_team_mode())
        self.assertFalse(ScrimMode.Mode1v1.is_team_mode())

        self.assertEqual(ScrimMode.Mode2v2.num_players(), 4)
        self.assertEqual(ScrimMode.Mode1v1v1v1.num_players(), 4)
        self.assertEqual(ScrimMode.Mode1v1.num_players(), 2)

        for mode in ScrimMode:
            self.assertLessEqual(len(mode.description()), 100)  # Discord's limit

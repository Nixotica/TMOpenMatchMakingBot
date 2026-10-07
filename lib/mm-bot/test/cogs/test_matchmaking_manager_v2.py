import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from cogs.matchmaking_manager_v2 import MatchmakingManagerV2
from discord.ext import commands
from matchmaking.match_queues.enum import QueueType
from matchmaking.matches.active_match import ActiveMatch
from models.match_queue import MatchQueue
from models.player_profile import PlayerProfile


def make_match(bot_match_id: int, is_scrim: bool) -> ActiveMatch:
    queue = MatchQueue(
        queue_id="scrim-1" if is_scrim else "queue",
        campaign_club_id=1,
        campaign_id=2,
        match_club_id=3,
        type=QueueType.Queue1v1,
        active=True,
        channel_id=0,
        leaderboard_ids=None if is_scrim else ["lb"],
        primary_leaderboard_id=None,
        ping_role_id=None,
        display_name=None,
        category_id=None,
        is_scrim=is_scrim,
    )
    players = [
        PlayerProfile(tm_account_id=f"p{i}", discord_account_id=i, matches_played=0)
        for i in (1, 2)
    ]
    return ActiveMatch(
        event_id=bot_match_id,
        event_name=f"BMM - #{bot_match_id}",
        round_id=0,
        match_id=bot_match_id,
        match_live_id=str(bot_match_id),
        match_join_link="",
        bot_match_id=bot_match_id,
        player_profiles=players,
        match_queue=queue,
    )


@patch("cogs.matchmaking_manager_v2.persist_match")
@patch("cogs.matchmaking_manager_v2.get_persisted_matches", return_value=[])
@patch("cogs.matchmaking_manager_v2.S3ClientManager")
@patch("cogs.matchmaking_manager_v2.DynamoDbManager")
class TestMatchmakingManagerV2Scrims(unittest.IsolatedAsyncioTestCase):
    def make_manager(self, mock_ddb) -> MatchmakingManagerV2:
        mock_ddb.return_value.get_match_queues.return_value = []
        bot = commands.Bot(command_prefix="/", intents=discord.Intents.none())
        return MatchmakingManagerV2(bot)

    def test_register_active_match_persists_only_queue_matches(
        self, mock_ddb, _, __, mock_persist_match
    ):
        manager = self.make_manager(mock_ddb)
        scrim_match = make_match(1, is_scrim=True)
        queue_match = make_match(2, is_scrim=False)

        manager.register_active_match(scrim_match)
        mock_persist_match.assert_not_called()

        manager.register_active_match(queue_match)
        mock_persist_match.assert_called_once_with(queue_match)

        self.assertEqual(manager.active_matches, [scrim_match, queue_match])
        self.assertTrue(manager.is_player_in_match(scrim_match.participants()[0]))

    @patch("cogs.matchmaking_manager_v2.CompletedMatch")
    @patch.object(ActiveMatch, "is_match_complete", return_value=True)
    async def test_completed_scrim_matches_are_unranked(
        self, _, mock_completed_match, mock_ddb, __, ___, ____
    ):
        manager = self.make_manager(mock_ddb)
        manager.distribute_elos_and_notify_players = AsyncMock()  # type: ignore

        def complete(active_match):
            completed_match = MagicMock()
            completed_match.active_match = active_match
            completed_match.match_results.get_rank.return_value = 1
            return completed_match

        mock_completed_match.side_effect = complete

        scrim_match = make_match(1, is_scrim=True)
        manager.register_active_match(scrim_match)
        await manager.check_active_matches_to_complete()

        manager.distribute_elos_and_notify_players.assert_not_called()
        mock_ddb.return_value.update_player_matches_played.assert_not_called()
        mock_ddb.return_value.put_match_results.assert_called_once()
        self.assertEqual(manager.active_matches, [])

        queue_match = make_match(2, is_scrim=False)
        manager.register_active_match(queue_match)
        await manager.check_active_matches_to_complete()

        manager.distribute_elos_and_notify_players.assert_awaited_once()
        self.assertEqual(
            mock_ddb.return_value.update_player_matches_played.call_count, 2
        )
        self.assertEqual(manager.active_matches, [])

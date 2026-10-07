import unittest

from matchmaking.match_queues.enum import QueueType
from matchmaking.scrims.scrim_mappack import (
    ScrimMappack,
    mappacks_from_queues,
    parse_campaign_reference,
)
from models.match_queue import MatchQueue


def make_queue(
    queue_id: str, campaign_club_id: int, campaign_id: int, display_name=None
) -> MatchQueue:
    return MatchQueue(
        queue_id=queue_id,
        campaign_club_id=campaign_club_id,
        campaign_id=campaign_id,
        match_club_id=1,
        type=QueueType.Queue2v2,
        active=True,
        channel_id=0,
        leaderboard_ids=None,
        primary_leaderboard_id=None,
        ping_role_id=None,
        display_name=display_name,
        category_id=None,
    )


class TestScrimMappack(unittest.TestCase):
    def test_parse_campaign_reference(self):
        self.assertEqual(
            parse_campaign_reference("https://trackmania.io/#/campaigns/12345/678"),
            (12345, 678),
        )
        self.assertEqual(
            parse_campaign_reference(
                "https://trackmania.io/#/campaigns/12345/678/leaderboard/abc-123"
            ),
            (12345, 678),
        )
        self.assertEqual(parse_campaign_reference("12345/678"), (12345, 678))
        self.assertEqual(parse_campaign_reference(" 12345 678 "), (12345, 678))

        self.assertIsNone(parse_campaign_reference("my favorite maps"))
        self.assertIsNone(parse_campaign_reference("12345"))
        self.assertIsNone(
            parse_campaign_reference("https://trackmania.io/#/clubs/12345")
        )

    def test_mappacks_from_queues_dedupes_campaigns(self):
        queues = [
            make_queue("2v2", 1, 2, display_name="2v2 Pack"),
            make_queue("2v2_bo5", 1, 2, display_name="2v2 Bo5"),
            make_queue("ffa", 3, 4),
        ]

        mappacks = mappacks_from_queues(queues)

        self.assertEqual(
            mappacks,
            [
                ScrimMappack("2v2 Pack", 1, 2, match_club_id=1),
                ScrimMappack("ffa", 3, 4, match_club_id=1),
            ],
        )
        self.assertEqual(mappacks[0].key(), "1/2")
        self.assertEqual(mappacks[0].link(), "https://trackmania.io/#/campaigns/1/2")

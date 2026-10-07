from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from models.match_queue import MatchQueue
from nadeo.ubi_token_vendor import UbiTokenRefresher
from nadeo_event_api.api.club.campaign import Campaign

TMIO_CAMPAIGN_URL_FMT = "https://trackmania.io/#/campaigns/{}/{}"

# Matches a trackmania.io campaign link, e.g. https://trackmania.io/#/campaigns/<club_id>/<campaign_id>
_TMIO_CAMPAIGN_REGEX = re.compile(r"campaigns/(\d+)/(\d+)")
# Matches "<club_id>/<campaign_id>" (or separated by a space or comma)
_CAMPAIGN_IDS_REGEX = re.compile(r"^\s*(\d+)\s*[/\s,]\s*(\d+)\s*$")


@dataclass(frozen=True)
class ScrimMappack:
    """A club campaign whose maps a scrim is played on."""

    name: str
    campaign_club_id: int
    campaign_id: int
    # The club hosting matches for the queue this mappack was taken from, if any
    match_club_id: Optional[int] = None

    def key(self) -> str:
        return f"{self.campaign_club_id}/{self.campaign_id}"

    def link(self) -> str:
        return TMIO_CAMPAIGN_URL_FMT.format(self.campaign_club_id, self.campaign_id)

    @classmethod
    def from_queue(cls, queue: MatchQueue) -> ScrimMappack:
        return cls(
            name=queue.display_name or queue.queue_id,
            campaign_club_id=queue.campaign_club_id,
            campaign_id=queue.campaign_id,
            match_club_id=queue.match_club_id,
        )


def mappacks_from_queues(queues: Iterable[MatchQueue]) -> List[ScrimMappack]:
    """Gets the distinct mappacks played by the given queues, in queue order.

    Args:
        queues (Iterable[MatchQueue]): The queues to take mappacks from.

    Returns:
        List[ScrimMappack]: One mappack per distinct campaign, named after the first queue using it.
    """
    mappacks: Dict[str, ScrimMappack] = {}
    for queue in queues:
        mappack = ScrimMappack.from_queue(queue)
        mappacks.setdefault(mappack.key(), mappack)
    return list(mappacks.values())


def parse_campaign_reference(text: str) -> Optional[Tuple[int, int]]:
    """Parses a trackmania.io campaign link or "<club_id>/<campaign_id>".

    Args:
        text (str): The text a player entered to identify a campaign.

    Returns:
        Optional[Tuple[int, int]]: The (club ID, campaign ID), or None if the text isn't a campaign reference.
    """
    match = _TMIO_CAMPAIGN_REGEX.search(text) or _CAMPAIGN_IDS_REGEX.match(text)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def count_campaign_maps(club_id: int, campaign_id: int) -> int:
    """Fetches a club campaign from Nadeo to count its maps.

    Args:
        club_id (int): The club the campaign belongs to.
        campaign_id (int): The campaign to count maps of.

    Returns:
        int: The number of maps in the campaign, 0 if it couldn't be loaded.
    """
    UbiTokenRefresher().refresh_tokens()

    try:
        campaign = Campaign(club_id, campaign_id)
    except Exception as e:
        logging.warning(f"Failed to load campaign {club_id}/{campaign_id}: {e}")
        return 0

    return len(campaign._playlist or [])

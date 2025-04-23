import random
from typing import Dict, List

from models.match_queue import MatchQueue
from nadeo.ubi_token_vendor import UbiTokenRefresher
from nadeo_event_api.api.club.campaign import Campaign
from nadeo_event_api.api.structure.maps import Map


class MapSelectionManager:
    """
    The backbone of handling map selection for each queue, avoiding repeat maps.
    """

    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(MapSelectionManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):  # Avoid re-initializing the instance
            self._initialized = True

            # Store the last map returned for matches by each queue (queue_id : map_uuid)
            self.last_played_maps_by_queue: Dict[str, str] = {}

    def get_random_map(
        self, match_queue: MatchQueue, avoid_repeats: bool = True
    ) -> Map:
        """Get a random map for a given match queue.

        Args:
            match_queue (MatchQueue): The match queue containing the campaign from which a map should be chosen.
            avoid_repeats (bool): Flag to avoid returning the same map as was
                previously returned for this match queue. (Default True)

        Returns:
            Map: A random map from the campaign.
        """
        campaign = self._get_campaign(match_queue)
        campaign_playlist = campaign._playlist
        if not campaign_playlist:
            raise Exception(
                f"No campaign playlist found with club id {match_queue.campaign_club_id} "
                f"and campaign id {match_queue.campaign_id}."
            )

        map_pool = [Map(playlist_map._uuid) for playlist_map in campaign_playlist]

        if len(map_pool) == 1:
            return map_pool[0]

        map_to_use = map_pool[random.randint(0, len(map_pool) - 1)]
        if not avoid_repeats:
            return map_to_use

        prev_used_map_uuid = self.last_played_maps_by_queue.get(match_queue.queue_id)

        while map_to_use._uuid == prev_used_map_uuid:
            map_to_use = map_pool[random.randint(0, len(map_pool) - 1)]

        self.last_played_maps_by_queue[match_queue.queue_id] = map_to_use._uuid

        return map_to_use

    def get_five_maps(self, match_queue: MatchQueue) -> List[Map]:
        """Gets 5 maps or all maps in the campaign for a match queue, whichever is less.

        Args:
            match_queue (MatchQueue): _description_

        Raises:
            Exception: _description_

        Returns:
            List[Map]: _description_
        """
        campaign = self._get_campaign(match_queue)
        maps = campaign._playlist
        if maps is None:
            raise Exception(
                f"No campaign playlist found with club id {match_queue.campaign_club_id} "
                f"and campaign id {match_queue.campaign_id}."
            )

        maps_to_use = maps[: min(5, len(maps))]
        return [Map(map._uuid) for map in maps_to_use]

    def _get_campaign(self, match_queue: MatchQueue) -> Campaign:
        UbiTokenRefresher().refresh_tokens()

        return Campaign(match_queue.campaign_club_id, match_queue.campaign_id)

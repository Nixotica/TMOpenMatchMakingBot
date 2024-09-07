import logging
import random
import time
from typing import List
from nadeo_event_api.api.structure.event import Event
from nadeo_event_api.api.structure.round.round import Round, RoundConfig
from nadeo_event_api.api.structure.enums import ScriptType
from nadeo_event_api.api.structure.settings.script_settings import CupScriptSettings, BaseScriptSettings
from nadeo_event_api.api.structure.settings.plugin_settings import ClassicPluginSettings
from nadeo_event_api.api.structure.round.match import Match
from nadeo_event_api.api.structure.enums import AutoStartMode
from nadeo_event_api.api.structure.round.match_spot import SeedMatchSpot
from nadeo_event_api.api.club.campaign import Campaign
from nadeo_event_api.api.structure.maps import Map
from nadeo_event_api.api.event_api import post_event, get_rounds_for_event, get_matches_for_round, get_match_results
from models.match_queue import MatchQueue
from models.player_profile import PlayerProfile
from matchmaking.constants import NUM_1v1v1v1_PLAYERS
from nadeo.ubi_token_vendor import UbiTokenRefresher
import datetime as dt

def create_1v1v1v1_match(match_queue: MatchQueue, players: List[PlayerProfile]) -> tuple[int, int, int, str]:
    """Create a 1v1v1v1 match using Trackmania competition tool. 

    Returns:
        (int, int, int, str): The event ID, round ID, match ID, and match Live ID of the created match. 
    """

    event_name = "Better MM Match"
    match_start_time = dt.datetime.utcnow() + dt.timedelta(seconds=10)

    UbiTokenRefresher().refresh_tokens()

    campaign_playlist = Campaign(match_queue.campaign_club_id, match_queue.campaign_id)._playlist
    map_pool = [Map(playlist_map._uuid) for playlist_map in campaign_playlist] # type: ignore
    map_to_use = map_pool[random.randint(0, len(map_pool) - 1)]

    event = Event(
        name=event_name,
        club_id=match_queue.match_club_id,
        rounds=[Round(
            name="Match",
            start_date=match_start_time,
            end_date=match_start_time + dt.timedelta(hours=1),
            matches=[Match(spots=[SeedMatchSpot(x) for x in range(1, len(players) + 1)])],
            config=RoundConfig(
                map_pool=[map_to_use],
                script=ScriptType.CUP,
                max_players=len(players),
                script_settings=CupScriptSettings(
                    base_script_settings=BaseScriptSettings(
                        warmup_number=1,
                        warmup_duration=60,
                    ),
                    points_repartition="10,6,4,3",
                    finish_timeout=10,
                    points_limit=40,
                    rounds_per_map=99,
                ),
                plugin_settings=ClassicPluginSettings(
                    auto_start_mode=AutoStartMode.DISABLED,
                )
            )
        )]
    )

    # TODO - error handling 
    event_id = post_event(event)

    # Add players before event actually starts 
    for idx in range(len(players)):
        event.add_participant(players[idx].tm_account_id, idx + 1)

    round_id = get_rounds_for_event(event_id)[0].id # type: ignore
    matches = get_matches_for_round(round_id, 1, 0)
    while matches == []:
        time.sleep(5)
        matches = get_matches_for_round(round_id, 1, 0)
    match_id = matches[0].id 
    match_live_id = matches[0].club_match_live_id

    return (event_id, round_id, match_id, match_live_id) # type: ignore
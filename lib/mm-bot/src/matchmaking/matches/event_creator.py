import logging
import random
import time
from typing import List
from nadeo_event_api.api.structure.event import Event
from nadeo_event_api.api.structure.round.round import Round, RoundConfig
from nadeo_event_api.api.structure.enums import ScriptType, ParticipantType
from nadeo_event_api.api.structure.settings.script_settings import (
    CupSpecialScriptSettings,
    RoundsScriptSettings,
    BaseScriptSettings,
    TMWTScriptSettings,
)
from nadeo_event_api.api.structure.settings.plugin_settings import (
    ClassicPluginSettings,
    TMWTPluginSettings,
)
from nadeo_event_api.api.structure.round.match import Match
from nadeo_event_api.api.structure.enums import AutoStartMode
from nadeo_event_api.api.structure.round.match_spot import SeedMatchSpot
from nadeo_event_api.api.club.campaign import Campaign
from nadeo_event_api.api.structure.maps import Map
from nadeo_event_api.api.event_api import (
    post_event,
    get_rounds_for_event,
    get_matches_for_round,
)
from nadeo_event_api.api.structure.round.match_spot import TeamMatchSpot
from models.match_queue import MatchQueue
from matchmaking.matches.team_2v2 import Teams2v2
from models.player_profile import PlayerProfile
from nadeo.ubi_token_vendor import UbiTokenRefresher
from matchmaking.matches.created_match_info import CreatedMatchInfo
from matchmaking.constants import POINTS_LIMIT_1v1v1v1
import datetime as dt


def get_random_map(match_queue: MatchQueue) -> Map:
    """Get a random map for the given match queue.

    Args:
        match_queue (MatchQueue): The match queue containing the campaign from which a map should be chosen.

    Returns:
        Map: A random map from the campaign.
    """
    UbiTokenRefresher().refresh_tokens()

    campaign_playlist = Campaign(
        match_queue.campaign_club_id, match_queue.campaign_id
    )._playlist
    if not campaign_playlist:
        error = f"No campaign playlist found with club id {match_queue.campaign_club_id} campaign id {match_queue.campaign_id}"
        logging.error(error)
        raise Exception(error)
    map_pool = [Map(playlist_map._uuid) for playlist_map in campaign_playlist]
    map_to_use = map_pool[random.randint(0, len(map_pool) - 1)]

    return map_to_use


def create_1v1v1v1_match(
    match_queue: MatchQueue, bot_match_id: int, players: List[PlayerProfile]
) -> CreatedMatchInfo:
    """Create a 1v1v1v1 match using Trackmania competition tool.

    Returns:
        (int, int, int, str): The event ID, round ID, match ID, and match Live ID of the created match.
    """

    event_name = f"BMM - #{bot_match_id}"
    match_start_time = dt.datetime.utcnow() + dt.timedelta(seconds=10)

    map_to_use = get_random_map(match_queue)

    event = Event(
        name=event_name,
        club_id=match_queue.match_club_id,
        rounds=[
            Round(
                name="Match",
                start_date=match_start_time,
                end_date=match_start_time + dt.timedelta(hours=1),
                matches=[
                    Match(spots=[SeedMatchSpot(x) for x in range(1, len(players) + 1)])
                ],
                config=RoundConfig(
                    map_pool=[map_to_use],
                    script=ScriptType.CUP_CLASSIC,
                    max_players=len(players) + 1,
                    script_settings=CupSpecialScriptSettings(
                        base_script_settings=BaseScriptSettings(
                            warmup_number=1,
                        ),
                        points_repartition="10,6,4,3",
                        number_of_winners=3,
                        finish_timeout=15,
                        points_limit=POINTS_LIMIT_1v1v1v1,
                        cup_points_limit=POINTS_LIMIT_1v1v1v1,
                        rounds_per_map=99,
                        ko_checkpoint_number=0,
                    ),
                    plugin_settings=ClassicPluginSettings(
                        auto_start_mode=AutoStartMode.DISABLED,
                    ),
                ),
            )
        ],
    )

    # TODO - error handling
    event_id = post_event(event)

    # Add players before event actually starts
    for idx in range(len(players)):
        event.add_participant(players[idx].tm_account_id, idx + 1)

    round_id = get_rounds_for_event(event_id)[0].id  # type: ignore
    matches = get_matches_for_round(round_id, 1, 0)
    while matches == []:
        time.sleep(5)
        matches = get_matches_for_round(round_id, 1, 0)
    match_id = matches[0].id
    match_live_id = matches[0].club_match_live_id

    return CreatedMatchInfo(event_id, round_id, match_id, match_live_id)  # type: ignore


def create_lsc_match(
    match_queue: MatchQueue, bot_match_id: int, players: List[PlayerProfile]
) -> CreatedMatchInfo:
    """Creates a LSC match (6 lapper - 1 round)

    Args:
        match_queue (MatchQueue): The match queue from which the map, club, and campaign are derived.
        bot_match_id (int): The bot match ID
        players (List[PlayerProfile]): List of players to add to the match

    Returns:
        CreatedMatchInfo: Info about the created match
    """

    event_name = f"BMM - #{bot_match_id}"
    match_start_time = dt.datetime.utcnow() + dt.timedelta(seconds=10)

    map_to_use = get_random_map(match_queue)

    event = Event(
        name=event_name,
        club_id=match_queue.match_club_id,
        rounds=[
            Round(
                name="Match",
                start_date=match_start_time,
                end_date=match_start_time + dt.timedelta(hours=1),
                matches=[
                    Match(spots=[SeedMatchSpot(x) for x in range(1, len(players) + 1)])
                ],
                config=RoundConfig(
                    map_pool=[map_to_use],
                    script=ScriptType.ROUNDS,
                    max_players=len(players) + 1,
                    script_settings=RoundsScriptSettings(
                        base_script_settings=BaseScriptSettings(
                            warmup_number=1,
                            warmup_duration=66,
                        ),
                        points_repartition="4,3,2,1",
                        points_limit=4,
                        rounds_per_map=1,
                        maps_per_match=1,
                    ),
                    plugin_settings=ClassicPluginSettings(
                        auto_start_mode=AutoStartMode.DISABLED,
                    ),
                ),
            )
        ]
    )

    # TODO - error handling
    event_id = post_event(event)

    # Add players before event actually starts
    for idx in range(len(players)):
        event.add_participant(players[idx].tm_account_id, idx + 1)

    round_id = get_rounds_for_event(event_id)[0].id  # type: ignore
    matches = get_matches_for_round(round_id, 1, 0)
    while matches == []:
        time.sleep(5)
        matches = get_matches_for_round(round_id, 1, 0)
    match_id = matches[0].id
    match_live_id = matches[0].club_match_live_id

    return CreatedMatchInfo(event_id, round_id, match_id, match_live_id)  # type: ignore


def create_2v2_match(match_queue: MatchQueue, bot_match_id: int, teams: Teams2v2) -> CreatedMatchInfo:
    """Create a 2v2 match using Trackmania competition tool.

    Args:
        match_queue (MatchQueue): The match queue from which the map, club, and campaign are derived.
        team_a (tuple[PlayerProfile, PlayerProfile]): Team A player profiles.
        team_b (tuple[PlayerProfile, PlayerProfile]): Team B player profiles.

    Returns:
        CreatedMatchInfo: The info for the created match.
    """

    event_name = f"BMM - #{bot_match_id}"
    match_start_time = dt.datetime.utcnow() + dt.timedelta(seconds=10)

    map_to_use = get_random_map(match_queue)

    event = Event(
        name=event_name,
        club_id=match_queue.match_club_id,
        rounds=[
            Round(
                name="Match",
                start_date=match_start_time,
                end_date=match_start_time + dt.timedelta(hours=1),
                matches=[
                    Match(
                        spots=[TeamMatchSpot(1), TeamMatchSpot(2)],
                    )
                ],
                config=RoundConfig(
                    map_pool=[map_to_use],
                    script=ScriptType.TMWT_TEAMS,
                    max_players=4,
                    script_settings=TMWTScriptSettings(
                        base_script_settings=BaseScriptSettings(
                            warmup_number=1,
                        ),
                        match_points_limit=1,
                    ),
                    plugin_settings=TMWTPluginSettings(
                        ready_minimum_team_size=1,
                        pick_ban_start_auto=False,
                        pick_ban_order="",
                    ),
                ),
            )
        ],
        participant_type=ParticipantType.TEAM,
    )

    # TODO - error handling
    event_id = post_event(event)

    # Add players before event actually starts
    event.add_team(
        "team_a",
        [teams.team_a.player_a.tm_account_id, teams.team_a.player_b.tm_account_id],
        1,
    )
    event.add_team(
        "team_b",
        [teams.team_b.player_a.tm_account_id, teams.team_b.player_b.tm_account_id],
        2,
    )

    round_id = get_rounds_for_event(event_id)[0].id  # type: ignore
    matches = get_matches_for_round(round_id, 1, 0)
    while matches == []:
        time.sleep(5)
        matches = get_matches_for_round(round_id, 1, 0)
    match_id = matches[0].id
    match_live_id = matches[0].club_match_live_id

    return CreatedMatchInfo(event_id, round_id, match_id, match_live_id)  # type: ignore


def create_solo_match(
    match_queue: MatchQueue,
    bot_match_id: int,
    player: PlayerProfile,
) -> CreatedMatchInfo:
    """Create a solo match using Trackmania competition tool for testing purposes.

    Returns:
        (int, int, int, str): The event ID, round ID, match ID, and match Live ID of the created match.
    """

    event_name = f"BMM - #{bot_match_id}"
    match_start_time = dt.datetime.utcnow() + dt.timedelta(seconds=10)

    map_to_use = get_random_map(match_queue)

    event = Event(
        name=event_name,
        club_id=match_queue.match_club_id,
        rounds=[
            Round(
                name="Match",
                start_date=match_start_time,
                end_date=match_start_time + dt.timedelta(hours=1),
                matches=[Match(spots=[SeedMatchSpot(1)])],
                config=RoundConfig(
                    map_pool=[map_to_use],
                    script=ScriptType.ROUNDS,
                    max_players=2,
                    script_settings=RoundsScriptSettings(
                        base_script_settings=BaseScriptSettings(
                            warmup_number=0,
                        ),
                        points_repartition="1,0",
                        points_limit=1,
                        rounds_per_map=1,
                    ),
                    plugin_settings=ClassicPluginSettings(
                        auto_start_mode=AutoStartMode.DISABLED,
                    ),
                ),
            )
        ],
    )

    # TODO - error handling
    event_id = post_event(event)

    # Add player before event actually start
    event.add_participant(player.tm_account_id, 1)

    round_id = get_rounds_for_event(event_id)[0].id  # type: ignore
    matches = get_matches_for_round(round_id, 1, 0)
    while matches == []:
        time.sleep(5)
        matches = get_matches_for_round(round_id, 1, 0)
    match_id = matches[0].id
    match_live_id = matches[0].club_match_live_id

    return CreatedMatchInfo(event_id, round_id, match_id, match_live_id)  # type: ignore

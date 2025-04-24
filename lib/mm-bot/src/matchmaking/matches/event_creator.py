import asyncio
import datetime as dt
from typing import List

from matchmaking.constants import POINTS_LIMIT_1v1v1v1
from matchmaking.matches.created_match_info import CreatedMatchInfo
from matchmaking.matches.map_selection_manager import MapSelectionManager
from matchmaking.matches.team_2v2 import Teams2v2
from models.match_queue import MatchQueue
from models.player_profile import PlayerProfile
from nadeo_event_api.api.event_api import (
    get_matches_for_round,
    get_rounds_for_event,
    post_event,
)
from nadeo_event_api.api.structure.enums import (
    AutoStartMode,
    ParticipantType,
    ScriptType,
)
from nadeo_event_api.api.structure.event import Event
from nadeo_event_api.api.structure.round.match import Match
from nadeo_event_api.api.structure.round.match_spot import SeedMatchSpot, TeamMatchSpot
from nadeo_event_api.api.structure.round.round import Round, RoundConfig
from nadeo_event_api.api.structure.settings.plugin_settings import (
    ClassicPluginSettings,
    TMWTPluginSettings,
)
from nadeo_event_api.api.structure.settings.script_settings import (
    BaseScriptSettings,
    CupSpecialScriptSettings,
    RoundsScriptSettings,
    TMWT2025ScriptSettings,
    BaseTMWTScriptSettings,
)
from nadeo_event_api.objects.outbound.pastebin.tmwt_2v2 import (
    Tmwt2v2Paste,
    Tmwt2v2PasteTeam,
)
from nadeo_event_api.api.pastefy.pastefy_api import post_tmwt_2v2


async def create_1v1v1v1_match(
    match_queue: MatchQueue, bot_match_id: int, players: List[PlayerProfile]
) -> CreatedMatchInfo:
    """Create a 1v1v1v1 match using Trackmania competition tool.

    Returns:
        (int, int, int, str): The event ID, round ID, match ID, and match Live ID of the created match.
    """

    event_name = f"BMM - #{bot_match_id}"
    match_start_time = dt.datetime.utcnow() + dt.timedelta(seconds=10)

    map_to_use = MapSelectionManager().get_random_map(match_queue)

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
                        hide_scores_header=True,
                    ),
                    plugin_settings=ClassicPluginSettings(
                        auto_start_mode=AutoStartMode.DISABLED,
                        enable_ready_manager=True,
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
        await asyncio.sleep(5)
        matches = get_matches_for_round(round_id, 1, 0)
    match_id = matches[0].id
    match_live_id = matches[0].club_match_live_id

    return CreatedMatchInfo(event_id, event_name, round_id, match_id, match_live_id)  # type: ignore


async def create_1v1_match(
    match_queue: MatchQueue, bot_match_id: int, players: List[PlayerProfile]
) -> CreatedMatchInfo:
    """Creates a 1v1 match using Trackmania CupShort script.

    Args:
        match_queue (MatchQueue): The match queue from which the map, club, and campaign are derived.
        bot_match_id (int): The bot match ID
        players (List[PlayerProfile]): List of players to add to the match

    Returns:
        CreatedMatchInfo: Info about the created match
    """

    event_name = f"BMM - #{bot_match_id}"
    match_start_time = dt.datetime.utcnow() + dt.timedelta(seconds=10)

    map_to_use = MapSelectionManager().get_random_map(match_queue)

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
                    script=ScriptType.CUP_SHORT,
                    max_players=len(players) + 1,
                    script_settings=CupSpecialScriptSettings(
                        base_script_settings=BaseScriptSettings(
                            warmup_number=1,
                        ),
                        points_repartition="1,0",
                        number_of_winners=1,
                        finish_timeout=5,
                        points_limit=4,
                        cup_points_limit=4,
                        rounds_per_map=99,
                        ko_checkpoint_number=0,
                        hide_scores_header=True,
                    ),
                    plugin_settings=ClassicPluginSettings(
                        auto_start_mode=AutoStartMode.DISABLED,
                        enable_ready_manager=True,
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
        await asyncio.sleep(5)
        matches = get_matches_for_round(round_id, 1, 0)
    match_id = matches[0].id
    match_live_id = matches[0].club_match_live_id

    return CreatedMatchInfo(event_id, event_name, round_id, match_id, match_live_id)  # type: ignore


async def create_lsc_match(
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

    map_to_use = MapSelectionManager().get_random_map(match_queue)

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
                        finish_timeout=-1,
                    ),
                    plugin_settings=ClassicPluginSettings(
                        auto_start_mode=AutoStartMode.DISABLED,
                        enable_ready_manager=True,
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
        await asyncio.sleep(5)
        matches = get_matches_for_round(round_id, 1, 0)
    match_id = matches[0].id
    match_live_id = matches[0].club_match_live_id

    return CreatedMatchInfo(event_id, event_name, round_id, match_id, match_live_id)  # type: ignore


async def create_2v2_match(
    match_queue: MatchQueue, bot_match_id: int, teams: Teams2v2
) -> CreatedMatchInfo:
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

    map_to_use = MapSelectionManager().get_random_map(match_queue)

    team_a = Tmwt2v2PasteTeam(
        teams.team_a.name,
        teams.team_a.name,
        teams.team_a.player_a.tm_account_id,
        teams.team_a.player_b.tm_account_id,
    )
    team_b = Tmwt2v2PasteTeam(
        teams.team_b.name,
        teams.team_b.name,
        teams.team_b.player_a.tm_account_id,
        teams.team_b.player_b.tm_account_id,
    )
    teams_paste = Tmwt2v2Paste(
        team_a,
        team_b,
    )

    # Doesn't require auth since Matrix whitelisted the IPs of devs and the service stack
    teams_url = post_tmwt_2v2(
        teams_paste,
        f"BMM{bot_match_id}",
    )

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
                    script=ScriptType.TMWT_2025,
                    max_players=4,
                    script_settings=TMWT2025ScriptSettings(
                        base_tmwt_script_settings=BaseTMWTScriptSettings(
                            base_script_settings=BaseScriptSettings(
                                warmup_number=1,
                            ),
                            match_points_limit=1,
                            teams_url=teams_url,
                            match_info=event_name,
                        ),
                    ),
                    plugin_settings=TMWTPluginSettings(
                        auto_start_mode=AutoStartMode.DISABLED,
                        ready_minimum_team_size=2,
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
        team_a.team_name,
        team_a.members(),
        1,
    )
    event.add_team(
        team_b.team_name,
        team_b.members(),
        2,
    )

    round_id = get_rounds_for_event(event_id)[0].id  # type: ignore
    matches = get_matches_for_round(round_id, 1, 0)
    while matches == []:
        await asyncio.sleep(5)
        matches = get_matches_for_round(round_id, 1, 0)
    match_id = matches[0].id
    match_live_id = matches[0].club_match_live_id

    return CreatedMatchInfo(event_id, event_name, round_id, match_id, match_live_id)  # type: ignore


async def create_2v2_bo5_match(
    match_queue: MatchQueue, bot_match_id: int, teams: Teams2v2
) -> CreatedMatchInfo:
    """Create a 2v2 Best of 5 match using Trackmania competition tool.

    Args:
        match_queue (MatchQueue): The match queue from which the map, club, and campaign are derived.
        team_a (tuple[PlayerProfile, PlayerProfile]): Team A player profiles.
        team_b (tuple[PlayerProfile, PlayerProfile]): Team B player profiles.

    Returns:
        CreatedMatchInfo: The info for the created match.
    """

    event_name = f"BMM - #{bot_match_id}"
    match_start_time = dt.datetime.utcnow() + dt.timedelta(seconds=10)

    maps_to_use = MapSelectionManager().get_five_maps(match_queue)

    team_a = Tmwt2v2PasteTeam(
        teams.team_a.name,
        teams.team_a.name,
        teams.team_a.player_a.tm_account_id,
        teams.team_a.player_b.tm_account_id,
    )
    team_b = Tmwt2v2PasteTeam(
        teams.team_b.name,
        teams.team_b.name,
        teams.team_b.player_a.tm_account_id,
        teams.team_b.player_b.tm_account_id,
    )
    teams_paste = Tmwt2v2Paste(
        team_a,
        team_b,
    )

    # Doesn't require auth since Matrix whitelisted the IPs of devs and the service stack
    teams_url = post_tmwt_2v2(
        teams_paste,
        f"BMM{bot_match_id}",
    )

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
                    map_pool=maps_to_use,
                    script=ScriptType.TMWT_2025,
                    max_players=4,
                    script_settings=TMWT2025ScriptSettings(
                        base_tmwt_script_settings=BaseTMWTScriptSettings(
                            base_script_settings=BaseScriptSettings(
                                warmup_number=1,
                                pick_ban_enable=True,
                            ),
                            match_points_limit=3,
                            teams_url=teams_url,
                            match_info=event_name,
                        ),
                        disable_match_intro=False,
                        is_matchmaking=True,
                    ),
                    plugin_settings=TMWTPluginSettings(
                        auto_start_mode=AutoStartMode.DISABLED,
                        ready_minimum_team_size=2,
                        pick_ban_start_auto=True,
                        pick_ban_order="p:1,p:0,p:0,p:1,p:r",
                        use_auto_ready=True,
                        pick_ban_use_gamepad_version=True,
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
        team_a.team_name,
        team_a.members(),
        1,
    )
    event.add_team(
        team_b.team_name,
        team_b.members(),
        2,
    )

    round_id = get_rounds_for_event(event_id)[0].id  # type: ignore
    matches = get_matches_for_round(round_id, 1, 0)
    while matches == []:
        await asyncio.sleep(5)
        matches = get_matches_for_round(round_id, 1, 0)
    match_id = matches[0].id
    match_live_id = matches[0].club_match_live_id

    return CreatedMatchInfo(event_id, event_name, round_id, match_id, match_live_id)  # type: ignore


async def create_solo_match(
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

    map_to_use = MapSelectionManager().get_random_map(match_queue)

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
                        enable_ready_manager=True,
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
        await asyncio.sleep(5)
        matches = get_matches_for_round(round_id, 1, 0)
    match_id = matches[0].id
    match_live_id = matches[0].club_match_live_id

    return CreatedMatchInfo(event_id, event_name, round_id, match_id, match_live_id)  # type: ignore

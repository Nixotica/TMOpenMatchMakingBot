import asyncio
import datetime as dt
import logging
from typing import List, Optional

from aws.s3 import S3ClientManager
from matchmaking.constants import POINTS_LIMIT_1v1v1v1
from matchmaking.matches.created_match_info import CreatedMatchInfo
from matchmaking.matches.map_selection_manager import MapSelectionManager
from matchmaking.matches.team_2v2 import Teams2v2
from models.match_queue import MatchQueue
from models.player_profile import PlayerProfile
from nadeo_event_api.api.event_api import (
    get_match_info,
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
from nadeo_event_api.api.pastefy.pastefy_api import post_tmwt_2v2, get_auth


class CreateMatchError(Exception):
    """Custom exception for match creation errrors."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        logging.error(f"CreateMatchError: {message}")


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
                            warmup_duration=15,
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

    return await create_match(event, players=players)


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
                            warmup_duration=15,
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

    return await create_match(event, players=players)


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

    return await create_match(event, players=players)


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

    secrets = S3ClientManager().get_secrets()

    teams_url = post_tmwt_2v2(
        teams_paste,
        f"BMM{bot_match_id}",
        basic_auth=get_auth(secrets.pastefy_login, secrets.pastefy_password),
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
                                warmup_duration=15,
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

    return await create_match(event, teams=[team_a, team_b])


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

    secrets = S3ClientManager().get_secrets()

    teams_url = post_tmwt_2v2(
        teams_paste,
        f"BMM{bot_match_id}",
        basic_auth=get_auth(secrets.pastefy_login, secrets.pastefy_password),
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
                                warmup_duration=15,
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

    return await create_match(event, teams=[team_a, team_b])


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

    return await create_match(event, players=[player])


async def create_match(
    event: Event,
    players: Optional[List[PlayerProfile]] = None,
    teams: Optional[List[Tmwt2v2PasteTeam]] = None,
) -> CreatedMatchInfo:
    """Creates a match using the Trackmania competition tool.

    Args:
        event (Event): The event structure for the match. Assumes that there is 1 round and 1 match.
        players (Optional[List[PlayerProfile]], optional): Players to add to the match. Leave None if teams match.
        teams (Optional[List[Tmwt2v2PasteTeam]], optional): Teams to add to the match. Leave None if solo players match.

    Returns:
        CreatedMatchInfo: The info for the created match.
    """
    if players is None and teams is None:
        raise ValueError("Either players or teams must be provided.")

    if players is not None and teams is not None:
        raise ValueError("Only one of players or teams can be provided.")

    event_id = post_event(event)
    if event_id is None:
        raise Exception("Failed to create event.")

    # Add players or teams before event starts
    if players is not None:
        for idx in range(len(players)):
            event.add_participant(players[idx].tm_account_id, idx + 1)
    elif teams is not None:
        event.add_team(
            teams[0].team_name,
            teams[0].members(),
            1,
        )
        event.add_team(
            teams[1].team_name,
            teams[1].members(),
            2,
        )

    max_retries = 10
    attempt = 0

    round_id = get_rounds_for_event(event_id)[0].id
    matches = get_matches_for_round(round_id, 1, 0)
    while matches == []:
        attempt += 1
        if attempt > max_retries:
            raise CreateMatchError(
                f"Failed to create match after max attempts ({max_retries})."
            )
        logging.info(
            f"Matches are empty, waiting for 5 seconds then retrying (attempt {attempt})..."
        )
        await asyncio.sleep(5)
        matches = get_matches_for_round(round_id, 1, 0)
    match_id = matches[0].id
    match_live_id = matches[0].club_match_live_id

    attempt = 0
    match_info = get_match_info(match_live_id)
    while match_info.join_link is None:
        attempt += 1
        if attempt > max_retries:
            raise CreateMatchError(
                f"Failed to get match join link after max attempts ({max_retries})."
            )
        logging.info(
            f"Match join link is empty, waiting for 10 seconds then retrying (attempt {attempt})..."
        )
        await asyncio.sleep(10)
        match_info = get_match_info(match_live_id)

    return CreatedMatchInfo(
        event_id=event_id,
        event_name=event._name,
        round_id=round_id,
        match_id=match_id,
        match_live_id=match_live_id,
        match_join_link=match_info.join_link,
    )

import logging
from typing import List

from aws.dynamodb import DynamoDbManager
from matchmaking.constants import NUM_1v1v1v1_PLAYERS
from matchmaking.match_queues.enum import QueueType
from matchmaking.matches.active_match import ActiveMatch
from matchmaking.matches.team_2v2 import Team2v2, Teams2v2
from models.persisted_match import PersistedMatch
from nadeo.ubi_token_vendor import UbiTokenRefresher
from nadeo_event_api.api.event_api import (
    get_event_participants,
    get_event_teams,
    get_matches_for_round,
    get_rounds_for_event,
)


def active_match_from_persisted_match(persisted_match: PersistedMatch) -> ActiveMatch:
    """Given a persisted match from DDB, translate it into an ActiveMatch

    Args:
        persisted_match (PersistedMatch): A persisted match.

    Returns:
        ActiveMatch: The match as an ActiveMatch
    """
    UbiTokenRefresher().refresh_tokens()

    event_id = persisted_match.event_id
    round_id = get_rounds_for_event(event_id)[0].id
    matches = get_matches_for_round(round_id, 1, 0)
    match_id = matches[0].id
    match_live_id = matches[0].club_match_live_id

    ddb = DynamoDbManager()

    queue = ddb.get_match_queue(persisted_match.queue_id)
    if queue is None:
        raise LookupError(f"Could not find queue for {persisted_match.queue_id}")

    player_profiles = None
    if queue.type == QueueType.Queue2v2:
        event_teams = get_event_teams(event_id)

        team_a_p1_tmacc = event_teams[0].players[0].account_id
        team_a_p1 = ddb.query_player_profile_for_tm_account_id(team_a_p1_tmacc)
        if team_a_p1 is None:
            raise LookupError(f"Could not find discord for {team_a_p1_tmacc}")

        team_a_p2_tmacc = event_teams[0].players[1].account_id
        team_a_p2 = ddb.query_player_profile_for_tm_account_id(team_a_p2_tmacc)
        if team_a_p2 is None:
            raise LookupError(f"Could not find discord for {team_a_p2_tmacc}")

        team_b_p1_tmacc = event_teams[1].players[0].account_id
        team_b_p1 = ddb.query_player_profile_for_tm_account_id(team_b_p1_tmacc)
        if team_b_p1 is None:
            raise LookupError(f"Could not find discord for {team_b_p1_tmacc}")

        team_b_p2_tmacc = event_teams[1].players[1].account_id
        team_b_p2 = ddb.query_player_profile_for_tm_account_id(team_b_p2_tmacc)
        if team_b_p2 is None:
            raise LookupError(f"Could not find discord for {team_b_p2_tmacc}")

        teams_2v2 = Teams2v2(
            team_a=Team2v2(
                name=event_teams[0].name,
                player_a=team_a_p1,
                player_b=team_a_p2,
            ),
            team_b=Team2v2(
                name=event_teams[1].name,
                player_a=team_b_p1,
                player_b=team_b_p2,
            ),
        )

        player_profiles = teams_2v2
    else:
        event_participants = get_event_participants(event_id, NUM_1v1v1v1_PLAYERS, 0)

        player_profiles = []
        for participant in event_participants:
            player_profiles.append(
                ddb.query_player_profile_for_tm_account_id(participant.participant)
            )

    return ActiveMatch(
        event_id,
        round_id,
        match_id,
        match_live_id,
        persisted_match.bot_match_id,
        player_profiles,
        queue,
    )


def persisted_match_from_active_match(active_match: ActiveMatch) -> PersistedMatch:
    """Given an active match, translate it into a PersistedMatch

    Args:
        active_match (ActiveMatch): An active match.

    Returns:
        PersistedMatch: The match as a PersistedMatch
    """
    return PersistedMatch(
        active_match.bot_match_id,
        active_match.event_id,
        active_match.match_queue.queue_id,
    )


def get_persisted_matches() -> List[ActiveMatch]:
    """Gets matches persisted from the previous time the bot was up, saved in DDB.

    Returns:
        List[ActiveMatch]: List of active matches
    """
    persisted_matches = DynamoDbManager().get_persisted_matches()
    active_matches = []
    for persisted_match in persisted_matches:
        try:
            active_matches.append(active_match_from_persisted_match(persisted_match))
        except Exception as e:
            logging.warning(
                f"Failed to get persisted match {persisted_match.bot_match_id} from DDB: {e}. Deleting it."
            )
            DynamoDbManager().delete_persisted_match(persisted_match.bot_match_id)
    return active_matches


def persist_match(match: ActiveMatch) -> None:
    """Persists a match to DDB.

    Args:
        match (ActiveMatch): The match to persist.
    """
    persisted_match = persisted_match_from_active_match(match)
    DynamoDbManager().create_persisted_match(persisted_match)


def delete_persisted_match(bot_match_id: int) -> None:
    """Delete a match from DDB persistence.

    Args:
        match (ActiveMatch): The match to delete.
    """
    DynamoDbManager().delete_persisted_match(bot_match_id)

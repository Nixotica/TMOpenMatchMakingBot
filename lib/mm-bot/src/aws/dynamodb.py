import logging
import os
from datetime import datetime
from typing import List, Optional

import boto3
from aws.constants import (
    INDEX_DISCORD_ACCOUNT_ID,
    KEY_ACTIVE,
    KEY_BOT_MATCH_ID,
    KEY_CURRENT_VALUE,
    KEY_DISCORD_ACCOUNT_ID,
    KEY_ELO,
    KEY_LEADERBOARD_ID,
    KEY_LEADERBOARD_IDS,
    KEY_MATCHES_PLAYED,
    KEY_MATCHES_WON,
    KEY_QUEUE_ID,
    KEY_RANK_ID,
    KEY_RANK_ROLE_ID,
    KEY_TM_ACCOUNT_ID,
)
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError
from matchmaking.constants import DEFAULT_ELO
from models.leaderboard import Leaderboard
from models.leaderboard_rank import LeaderboardRank
from models.match_queue import MatchQueue
from models.match_results import DdbMatchResults
from models.matches_played import MatchesPlayed
from models.persisted_match import PersistedMatch
from models.player_elo import PlayerElo
from models.player_profile import PlayerProfile
from models.rank_role import RankRole
from mypy_boto3_dynamodb import DynamoDBClient, DynamoDBServiceResource


class DynamoDbManager:
    _instance = None
    _client = None
    _resource = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DynamoDbManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self._client = self._create_client()

        if self._resource is None:
            self._resource = self._create_resource()

        player_profiles_table = os.environ.get("PLAYER_PROFILES_TABLE")
        if player_profiles_table is None:
            raise ValueError("PLAYER_PROFILES_TABLE environment variable is not set")
        self._player_profiles_table = self._resource.Table(player_profiles_table)

        player_elos_table = os.environ.get("PLAYER_ELOS_TABLE")
        if player_elos_table is None:
            raise ValueError("PLAYER_ELOS_TABLE environment variable is not set")
        self._player_elos_table = self._resource.Table(player_elos_table)

        match_results_table = os.environ.get("MATCH_RESULTS_TABLE")
        if match_results_table is None:
            raise ValueError("MATCH_RESULTS_TABLE environment variable is not set")
        self._match_results_table = self._resource.Table(match_results_table)

        match_queues_table = os.environ.get("MATCH_QUEUES_TABLE")
        if match_queues_table is None:
            raise ValueError("MATCH_QUEUES_TABLE environment variable is not set")
        self._match_queues_table = self._resource.Table(match_queues_table)

        leaderboards_table = os.environ.get("LEADERBOARDS_TABLE")
        if leaderboards_table is None:
            raise ValueError("LEADERBOARDS_TABLE environment variable is not set")
        self._leaderboards_table = self._resource.Table(leaderboards_table)

        ranks_table = os.environ.get("RANKS_TABLE")
        if ranks_table is None:
            raise ValueError("RANKS_TABLE environment variable is not set")
        self._ranks_table = self._resource.Table(ranks_table)

        leaderboard_ranks_table = os.environ.get("LEADERBOARD_RANKS_TABLE")
        if leaderboard_ranks_table is None:
            raise ValueError("LEADERBOARD_RANKS_TABLE environment variable is not set")
        self._leaderboard_ranks_table = self._resource.Table(leaderboard_ranks_table)

        next_bot_match_id_table = os.environ.get("NEXT_BOT_MATCH_ID_TABLE")
        if next_bot_match_id_table is None:
            raise ValueError("NEXT_BOT_MATCH_ID_TABLE environment variable is not set")
        self._next_bot_match_id_table = self._resource.Table(next_bot_match_id_table)

        persisted_matches_table = os.environ.get("PERSISTED_MATCHES_TABLE")
        if persisted_matches_table is None:
            raise ValueError("PERSISTED_MATCHES_TABLE environment variable is not set")
        self._persisted_matches_table = self._resource.Table(persisted_matches_table)

        matches_played_table = os.environ.get("MATCHES_PLAYED_TABLE")
        if matches_played_table is None:
            raise ValueError("MATCHES_PLAYED_TABLE environment variable is not set")
        self._matches_played_table = self._resource.Table(matches_played_table)

    def _create_client(self) -> DynamoDBClient:
        try:
            dynamodb_client = boto3.client("dynamodb")
            return dynamodb_client  # type: ignore
        except Exception as e:
            logging.error(f"Error creating DynamoDB client: {e}")
            raise

    def _create_resource(self) -> DynamoDBServiceResource:
        try:
            dynamodb_resource = boto3.resource("dynamodb")
            return dynamodb_resource  # type: ignore
        except Exception as e:
            logging.error(f"Error creating DynamoDB resource: {e}")
            raise

    def query_player_profile_for_tm_account_id(
        self, tm_account_id: str
    ) -> Optional[PlayerProfile]:
        """
        Query the PlayerProfiles table for a player profile with the given TM account ID.
        :param tm_account_id: The TM account ID to query for
        :return: The player profile if found, None otherwise
        """
        try:
            response = self._player_profiles_table.query(
                KeyConditionExpression=Key(KEY_TM_ACCOUNT_ID).eq(tm_account_id)
            )
            items = response.get("Items", [])
            if not items:
                return None
            if len(items) > 1:
                logging.warning(
                    f"Multiple player profiles found for TM account ID {tm_account_id}: {items}"
                )
            return PlayerProfile.from_dict(items[0])
        except Exception as e:
            logging.error(f"Error getting player profile from DynamoDB: {e}")
            raise

    def query_player_profile_for_discord_account_id(
        self, discord_account_id: int
    ) -> Optional[PlayerProfile]:
        """
        Query the PlayerProfiles table for a player profile with the given Discord account ID.
        :param discord_account_id: The Discord account ID to query for
        :return: The player profile if found, None otherwise
        """
        try:
            response = self._player_profiles_table.query(
                IndexName=INDEX_DISCORD_ACCOUNT_ID,
                KeyConditionExpression=Key(KEY_DISCORD_ACCOUNT_ID).eq(
                    discord_account_id
                ),
            )
            items = response.get("Items", [])
            if not items:
                return None
            if len(items) > 1:
                logging.warning(
                    f"Multiple player profiles found for Discord account ID {discord_account_id}: {items}"
                )
            return PlayerProfile.from_dict(items[0])
        except Exception as e:
            logging.error(f"Error getting player profile from DynamoDB: {e}")
            raise

    def create_player_profile_for_tm_account_id(
        self,
        tm_account_id: str,
        discord_account_id: int,
    ) -> bool:
        """
        Create a player profile record in the PlayerProfiles table for a given TM account ID and Discord account ID.
        :param tm_account_id: The TM account ID to create a player profile for
        :param discord_account_id: The Discord account ID to create a player profile for
        :return: True if the profile was successfully created, False otherwise.
        """
        try:
            player_profile = PlayerProfile.from_dict(
                {
                    KEY_TM_ACCOUNT_ID: tm_account_id,
                    KEY_DISCORD_ACCOUNT_ID: discord_account_id,
                    KEY_MATCHES_PLAYED: 0,  # Deprecated, but keeping for schema consistency for now
                }
            )

            self._player_profiles_table.put_item(
                Item=player_profile.__dict__,
                ConditionExpression=Attr(KEY_TM_ACCOUNT_ID).not_exists()
                & Attr(KEY_DISCORD_ACCOUNT_ID).not_exists(),
            )

            return True
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":  # type: ignore
                logging.warning(
                    f"Player profile already exists for TM account ID {tm_account_id} "
                    f"and Discord account ID {discord_account_id}"
                )
                return False
            else:
                raise
        except Exception as e:
            logging.error(f"Error creating player profile in DynamoDB: {e}")
            raise

    def get_player_profiles(self) -> List[PlayerProfile]:
        """Gets all player profiles.

        Returns:
            List[PlayerProfile]: List of all registered players' profiles.
        """
        try:
            response = self._player_profiles_table.scan()
            items = response.get("Items", [])
            if not items:
                return []
            player_profiles = [
                PlayerProfile.from_dict(items[i]) for i in range(len(items))
            ]
            return player_profiles
        except Exception as e:
            logging.error(f"Error getting player profiles from DynamoDB: {e}")
            raise

    def update_player_matches_played(
        self, tm_account_id: str, queue_id: str, won: bool
    ) -> bool:
        """Updates the matches played info for a player on a given queue by incrementing the
            number of matches played by 1 and incrementing number of wins by 1 if the player
            won the match.

        Args:
            tm_account_id (str): The TM acccount for which the match was completed.
            queue_id (str): The queue ID of the match that was completed.
            won (bool): True if the player won the match, False otherwise.

        Returns:
            bool: True if the record was updated successfully, False otherwise.
        """
        try:
            self._matches_played_table.update_item(
                Key={
                    KEY_TM_ACCOUNT_ID: tm_account_id,
                    KEY_QUEUE_ID: queue_id,
                },
                UpdateExpression="""
                    SET
                        #matches_played = if_not_exists(#matches_played, :zero) + :incr_played,
                        #matches_won = if_not_exists(#matches_won, :zero) + :maybe_incr_won
                """,
                ExpressionAttributeNames={
                    "#matches_played": KEY_MATCHES_PLAYED,
                    "#matches_won": KEY_MATCHES_WON,
                },
                ExpressionAttributeValues={
                    ":zero": 0,
                    ":incr_played": 1,
                    ":maybe_incr_won": 1 if won else 0,
                },
                ReturnValues="UPDATED_NEW",
            )
            return True
        except Exception as e:
            logging.error(
                f"Error updating matches played for player {tm_account_id} "
                f"on queue {queue_id}: {e}"
            )
            return False

    def get_matches_played(self, tm_account_id: str) -> List[MatchesPlayed]:
        """Returns the matches played for every queue for a given player.

        Args:
            tm_account_id (str): The player to get matches played for.

        Returns:
            List[MatchesPlayed]: The matches played for every queue for the given player.
        """
        try:
            response = self._matches_played_table.query(
                KeyConditionExpression=Key(KEY_TM_ACCOUNT_ID).eq(tm_account_id)
            )
            items = response.get("Items", [])
            if not items:
                return []
            matches_played = [
                MatchesPlayed.from_dict(items[i]) for i in range(len(items))
            ]
            return matches_played
        except Exception as e:
            logging.error(f"Error getting matches played from DynamoDB: {e}")
            return []

    def update_player_elo(
        self, tm_account_id: str, leaderboard_id: str, new_elo: int
    ) -> bool:
        """Updates player elo for a given leaderboard.

        Args:
            tm_account_id (str): The TM account for which the elo should be updated.
            leaderboard_id (str): The leaderboard ID for which the elo should be updated.
            new_elo (int): The player's new elo.

        Returns:
            bool: True if the profile was successfully updated, False otherwise.
        """
        try:
            self._player_elos_table.update_item(
                Key={
                    KEY_TM_ACCOUNT_ID: tm_account_id,
                    KEY_LEADERBOARD_ID: leaderboard_id,
                },
                UpdateExpression="SET #elo = :new_elo",
                ExpressionAttributeNames={
                    "#elo": KEY_ELO,
                },
                ExpressionAttributeValues={
                    ":new_elo": new_elo,
                },
                ReturnValues="UPDATED_NEW",
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":  # type: ignore
                logging.warning(
                    f"Player profile for TM account ID {tm_account_id} does not exist."
                )
                return False
            else:
                logging.error(f"ClientError when updating player profile: {e}")
                raise
        except Exception as e:
            logging.error(f"Error updating player profile in DynamoDB: {e}")
            raise

    def get_match_queues(self, omit_disabled: bool = True) -> List[MatchQueue]:
        """Get a list of active match queues from the MatchQueues table.

        Args:
            omit_disabled (bool): Whether to return queues which have flag "active" set to False.

        Returns:
            List[MatchQueue]: List of match queues marked as "active" in DDB.
        """
        try:
            if omit_disabled:
                response = self._match_queues_table.scan(
                    FilterExpression=Attr(KEY_ACTIVE).eq(True)
                )
            else:
                response = self._match_queues_table.scan()
            items = response.get("Items", [])
            if not items:
                return []
            match_queues = [MatchQueue.from_dict(items[i]) for i in range(len(items))]
            return match_queues
        except Exception as e:
            logging.error(f"Error getting match queues from DynamoDB: {e}")
            raise

    def get_match_queue(self, queue_id: str) -> Optional[MatchQueue]:
        """Get a match queue from the MatchQueues table.

        Args:
            queue_id (str): The ID of the match queue to get.

        Returns:
            Optional[MatchQueue]: The match queue if found, None otherwise.
        """
        try:
            response = self._match_queues_table.get_item(Key={KEY_QUEUE_ID: queue_id})
            item = response.get("Item")
            if not item:
                return None
            return MatchQueue.from_dict(item)
        except Exception as e:
            logging.error(f"Error getting match queue from DynamoDB: {e}")
            raise

    def update_match_queue(self, queue: MatchQueue) -> None:
        """Update a match queue in the MatchQueues table.

        Args:
            queue (MatchQueue): The match queue to update.

        Returns:
            None
        """
        try:
            self._match_queues_table.put_item(Item=queue.to_dict())
        except Exception as e:
            logging.error(f"Error updating match queue in DynamoDB: {e}")
            raise

    def add_leaderboard_to_match_queue(
        self, queue_id: str, leaderboard_id: str
    ) -> None:
        """Add a leaderboard to a match queue.

        Args:
            queue_id (str): The ID of the match queue to add the leaderboard to.
            leaderboard_id (str): The ID of the leaderboard to add to the match queue.

        Returns:
            None
        """
        try:
            self._match_queues_table.update_item(
                Key={KEY_QUEUE_ID: queue_id},
                UpdateExpression="SET #leaderboard_ids = list_append"
                "(if_not_exists(#leaderboard_ids, :empty_list), :leaderboard)",
                ExpressionAttributeNames={
                    "#leaderboard_ids": KEY_LEADERBOARD_IDS,
                },
                ExpressionAttributeValues={
                    ":leaderboard": [leaderboard_id],
                    ":empty_list": [],
                },
                ReturnValues="UPDATED_NEW",
            )
        except Exception as e:
            logging.error(f"Error adding leaderboard to match queue in DynamoDB: {e}")
            raise

    def put_match_results(
        self,
        bot_match_id: int,
        queue_id: str,
        match_id: int,
        match_live_id: str,
        time_played: datetime,
        results_as_str: str,
    ) -> None:
        """Puts match results into the MatchResults table.

        Returns:
            None
        """
        try:
            self._match_results_table.put_item(
                Item=DdbMatchResults(
                    bot_match_id=bot_match_id,
                    queue_id=queue_id,
                    tm_match_id=match_id,
                    tm_match_live_id=match_live_id,
                    time_played=time_played.isoformat(),
                    results=results_as_str,
                ).to_dict()
            )
        except Exception as e:
            logging.error(f"Error putting match results into DynamoDB: {e}")
            raise

    def create_queue(self, queue: MatchQueue) -> bool:
        """Create a new matchmaking queue.

        Args:
            queue (MatchQueue): The queue to add to the database.

        Returns:
            bool: True if the queue was successfully created, False otherwise.
        """
        try:
            self._match_queues_table.put_item(
                Item=queue.to_dict(),
                ConditionExpression=Attr(KEY_QUEUE_ID).not_exists(),
            )

            return True
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":  # type: ignore
                logging.warning(f"Queue already exists for queue ID {queue.queue_id}")
                return False
            else:
                raise
        except Exception as e:
            logging.error(f"Error creating queue in DynamoDB: {e}")
            raise

    def create_leaderboard(self, leaderboard: Leaderboard) -> bool:
        """Create a new leaderboard.

        Args:
            leaderboard (Leaderboard): The leaderboard to add to the database.

        Returns:
            bool: True if the leaderboard was successfully created, False otherwise.
        """
        try:
            self._leaderboards_table.put_item(
                Item=leaderboard.to_dict(),
                ConditionExpression=Attr(KEY_LEADERBOARD_ID).not_exists(),
            )

            return True
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":  # type: ignore
                logging.warning(
                    f"Leaderboard already exists for leaderboard ID {leaderboard.leaderboard_id}"
                )
                return False
            else:
                raise
        except Exception as e:
            logging.error(f"Error creating leaderboard in DynamoDB: {e}")
            raise

    def get_leaderboards(self, omit_disabled: bool = True) -> List[Leaderboard]:
        """Get a list of leaderboards from the Leaderboards table.

        Args:
            omit_disabled (bool): Whether to return leaderboards which have flag "active" set to False.

        Returns:
            List[Leaderboard]: List of leaderboards in DDB.
        """
        try:
            if omit_disabled:
                response = self._leaderboards_table.scan(
                    FilterExpression=Attr(KEY_ACTIVE).eq(True)
                )
            else:
                response = self._leaderboards_table.scan()
            items = response.get("Items", [])
            if not items:
                return []
            leaderboards = [Leaderboard.from_dict(items[i]) for i in range(len(items))]
            return leaderboards
        except Exception as e:
            logging.error(f"Error getting leaderboards from DynamoDB: {e}")
            raise

    def get_leaderboard(self, leaderboard_id: str) -> Optional[Leaderboard]:
        """Get a leaderboard from the Leaderboards table.

        Args:
            leaderboard_id (str): The ID of the leaderboard to get.

        Returns:
            Optional[Leaderboard]: The leaderboard if found, None otherwise.
        """
        try:
            response = self._leaderboards_table.get_item(
                Key={KEY_LEADERBOARD_ID: leaderboard_id}
            )
            item = response.get("Item")
            if not item:
                return None
            return Leaderboard.from_dict(item)
        except Exception as e:
            logging.error(f"Error getting leaderboard from DynamoDB: {e}")
            raise

    def update_leaderboard(self, leaderboard: Leaderboard) -> None:
        """Update a leaderboard in the Leaderboards table.

        Args:
            leaderboard (Leaderboard): The leaderboard to update.

        Returns:
            None
        """
        try:
            self._leaderboards_table.put_item(Item=leaderboard.to_dict())
        except Exception as e:
            logging.error(f"Error updating leaderboard in DynamoDB: {e}")
            raise

    def get_or_create_player_elo(
        self, tm_account_id: str, leaderboard_id: str
    ) -> PlayerElo:
        """
        Get the elo for a given leaderboard ID for a specific player.
        If it doesn't exist, will create a record with the default elo.

        Args:
            tm_account_id (str): The TM account ID for which to return the given player's elo.
            leaderboard_id (str): The leaderboard ID for which to return the given player's elo.

        Returns:
            PlayerElo: The elo for a given leaderboard ID for a specific player.
        """
        try:
            get_response = self._player_elos_table.get_item(
                Key={
                    KEY_TM_ACCOUNT_ID: tm_account_id,
                    KEY_LEADERBOARD_ID: leaderboard_id,
                }
            )
            item = get_response.get("Item", {})
            if not item:
                logging.info(
                    f"No elo found for account ID {tm_account_id} and "
                    f"leaderbord ID {leaderboard_id}. Creating default one."
                )
                try:
                    item = PlayerElo(
                        tm_account_id=tm_account_id,
                        leaderboard_id=leaderboard_id,
                        elo=DEFAULT_ELO,
                    ).to_dict()
                    _ = self._player_elos_table.put_item(
                        Item=item,
                        ConditionExpression=Attr(KEY_TM_ACCOUNT_ID).not_exists()
                        & Attr(KEY_LEADERBOARD_ID).not_exists(),
                    )
                except Exception as e:
                    logging.error(f"Error creating player elo in DynamoDB: {e}")
                    raise
            player_elo = PlayerElo.from_dict(item)
            return player_elo
        except Exception as e:
            logging.error(f"Error getting player elo from DynamoDB: {e}")
            raise

    def get_player_elo_on_all_leaderboards(self, tm_account_id: str) -> List[PlayerElo]:
        """Get the elos for a specific player on all leaderboards. Omits leaderboards where player has no elo.

        Args:
            tm_account_id (str): The TM account ID for which to return the given player's elos.
            omit_disabled (bool, Optional): Whether to only include active leaderboards. Default False.

        Returns:
            List[PlayerElo]: The elos for a specific player across all their played leaderboards.
        """
        try:
            response = self._player_elos_table.query(
                KeyConditionExpression=Key(KEY_TM_ACCOUNT_ID).eq(tm_account_id),
            )
            items = response.get("Items", [])
            if not items:
                return []
            return [PlayerElo.from_dict(item) for item in items]
        except Exception as e:
            logging.error(f"Error getting player elos from DynamoDB: {e}")
            return []

    def get_top_25_players_by_elo(self, leaderboard_id: str) -> List[PlayerElo]:
        """Get a sorted list of the top 25 players by their elo in descending order for a given leaderboard.

        Args:
            leaderboard_id (str): The leaderboard ID to get player elos for.

        Returns:
            List[PlayerElo]: List of player elos for the leaderboard sorted in descending order.
        """
        try:
            response = self._player_elos_table.query(
                IndexName="leaderboard_id",
                KeyConditionExpression=Key(KEY_LEADERBOARD_ID).eq(leaderboard_id),
                ScanIndexForward=False,
                Limit=25,
            )
            items = response.get("Items", [])
            if not items:
                return []
            return [PlayerElo.from_dict(item) for item in items]
        except Exception as e:
            logging.error(f"Error getting top 25 player elos from DynamoDB: {e}")
            raise

    def get_nearby_players_by_elo(
        self, leaderboard_id: str, tm_account_id: str
    ) -> tuple[int, List[PlayerElo]]:
        """Get the players 3 places above and below a specific player by elo in descending order.

        Args:
            leaderboard_id (str): The leaderboard ID to get player elos for.
            player_id (str): The player ID to find nearby players for.

        Returns:
            tuple[int, List[PlayerElo]]: The first player's position in list and
                a list of 3 players above and 3 players below player.
        """
        try:
            # Query all players in the leaderboard sorted by elo
            response = self._player_elos_table.query(
                IndexName="leaderboard_id",
                KeyConditionExpression=Key(KEY_LEADERBOARD_ID).eq(leaderboard_id),
                ScanIndexForward=False,
            )
            items = response.get("Items", [])
            if not items:
                return (0, [])

            # Convert items to PlayerElo objects
            player_elos = [PlayerElo.from_dict(item) for item in items]

            # Find the target player index
            target_index = next(
                (
                    i
                    for i, player in enumerate(player_elos)
                    if player.tm_account_id == tm_account_id
                ),
                None,
            )
            if target_index is None:
                logging.warning(
                    f"Player {tm_account_id} not found in leaderboard {leaderboard_id}."
                )
                return (0, [])

            # Get players 3 places above and below
            start_index = max(0, target_index - 3)
            end_index = min(
                len(player_elos), target_index + 4
            )  # target + 3 (inclusive)
            return (start_index + 1, player_elos[start_index:end_index])
        except Exception as e:
            logging.error(f"Error getting nearby players from DynamoDB: {e}")
            raise

    def create_rank_role(self, rank_role: RankRole) -> bool:
        """Create a new rank role.

        Args:
            rank_role (RankRole): The rank role to add to the database.

        Returns:
            bool: True if the rank role was successfully created, False otherwise.
        """
        try:
            self._ranks_table.put_item(
                Item=rank_role.to_dict(),
                ConditionExpression=Attr(KEY_RANK_ROLE_ID).not_exists(),
            )

            return True
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":  # type: ignore
                logging.warning(
                    f"Rank role already exists for rank role ID {rank_role.rank_role_id}"
                )
                return False
            else:
                raise

    def get_rank_roles(self) -> List[RankRole]:
        """Get a list of ranks from the Ranks table.

        Returns:
            List[RankRole]: List of ranks in DDB.
        """
        try:
            response = self._ranks_table.scan()
            items = response.get("Items", [])
            if not items:
                return []
            ranks = [RankRole.from_dict(items[i]) for i in range(len(items))]
            return ranks
        except Exception as e:
            logging.error(f"Error getting ranks from DynamoDB: {e}")
            raise

    def create_leaderboard_rank(self, leaderboard_rank: LeaderboardRank) -> None:
        """Create a new leaderboard rank.

        Args:
            leaderboard_rank (LeaderboardRank): The leaderboard rank to add to the database.
        """
        try:
            self._leaderboard_ranks_table.put_item(
                Item=leaderboard_rank.to_dict(),
                ConditionExpression=Attr(KEY_RANK_ID).not_exists(),
            )
        except Exception as e:
            logging.error(f"Error creating leaderboard rank in DynamoDB: {e}")
            raise

    def get_ranks_for_leaderboard_by_min_elo_descending(
        self, leaderboard_id: str
    ) -> List[LeaderboardRank]:
        """Get a list of ranks from the LeaderboardRanks table in descending order of minimum elo.

        Args:
            leaderboard_id (str): The leaderboard ID to get ranks for.

        Returns:
            List[LeaderboardRank]: List of ranks for the leaderboard sorted in descending order of minimum elo.
        """
        try:
            response = self._leaderboard_ranks_table.query(
                IndexName="leaderboard_id",
                KeyConditionExpression=Key(KEY_LEADERBOARD_ID).eq(leaderboard_id),
                ScanIndexForward=False,
            )
            items = response.get("Items", [])
            if not items:
                return []
            ranks = [LeaderboardRank.from_dict(items[i]) for i in range(len(items))]
            return ranks
        except Exception as e:
            logging.error(f"Error getting ranks from DynamoDB: {e}")
            raise

    def get_next_bot_match_id_and_increment(self) -> int:
        """Get the next bot match ID and increment it in the database.

        Returns:
            int: The next bot match ID.
        """
        try:
            # Attempt to increment the current value
            response = self._next_bot_match_id_table.update_item(
                Key={KEY_BOT_MATCH_ID: KEY_BOT_MATCH_ID},
                UpdateExpression="SET #current_value = #current_value + :inc",
                ExpressionAttributeNames={"#current_value": KEY_CURRENT_VALUE},
                ExpressionAttributeValues={":inc": 1},
                ReturnValues="UPDATED_OLD",  # Return the value before it was updated
            )
            return int(response["Attributes"][KEY_CURRENT_VALUE]) + 1  # type: ignore

        except ClientError as e:
            if e.response["Error"]["Code"] == "ValidationException":  # type: ignore
                # This error can indicate that the item doesn't exist, so initialize it
                logging.info("Match ID not initialized yet. Initializing to 1.")
                try:
                    self._next_bot_match_id_table.put_item(
                        Item={KEY_BOT_MATCH_ID: KEY_BOT_MATCH_ID, KEY_CURRENT_VALUE: 1},
                        ConditionExpression=f"attribute_not_exists({KEY_BOT_MATCH_ID})",
                    )
                    return 1  # Return 1 since we are initializing it to 1
                except ClientError as init_e:
                    if (
                        init_e.response["Error"]["Code"]  # type: ignore
                        == "ConditionalCheckFailedException"
                    ):
                        # In the event of a race condition, just retry incrementing
                        return self.get_next_bot_match_id_and_increment()
                    else:
                        raise
            else:
                raise

    def get_persisted_matches(self) -> List[PersistedMatch]:
        """Get a list of persisted matches from the PersistedMatches table.

        Returns:
            List[PersistedMatch]: List of persisted matches in DDB.
        """
        try:
            response = self._persisted_matches_table.scan()
            items = response.get("Items", [])
            if not items:
                return []
            matches = [PersistedMatch.from_dict(items[i]) for i in range(len(items))]
            return matches
        except Exception as e:
            logging.error(f"Error getting persisted matches from DynamoDB: {e}")
            raise

    def create_persisted_match(self, persisted_match: PersistedMatch) -> bool:
        """Create a new persisted match.

        Args:
            persisted_match (PersistedMatch): The match to persist in the database.

        Returns:
            bool: True if the match was successfully created, False otherwise.
        """
        try:
            self._persisted_matches_table.put_item(
                Item=persisted_match.to_dict(),
                ConditionExpression=Attr(KEY_BOT_MATCH_ID).not_exists(),
            )
            return True
        except Exception as e:
            logging.error(f"Error creating persisted match in DynamoDB: {e}")
            return False

    def delete_persisted_match(self, bot_match_id: int) -> bool:
        """Delete a persisted match.

        Args:
            bot_match_id (int): The bot match ID of the match to delete.

        Returns:
            bool: True if the match was successfully deleted, False otherwise.
        """
        try:
            self._persisted_matches_table.delete_item(
                Key={KEY_BOT_MATCH_ID: bot_match_id},
            )
            return True
        except Exception as e:
            logging.error(f"Error deleting active match in DynamoDB: {e}")
            return False

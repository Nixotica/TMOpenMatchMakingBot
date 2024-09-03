import logging
import os
from typing import Optional

import boto3
from aws.constants import KEY_TM_ACCOUNT_ID, KEY_DISCORD_ACCOUNT_ID, KEY_ELO, KEY_MATCHES_PLAYED
from matchmaking.constants import DEFAULT_ELO
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from models.player_profile import PlayerProfile
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

        match_results_table = os.environ.get("MATCH_RESULTS_TABLE")
        if match_results_table is None:
            raise ValueError("MATCH_RESULTS_TABLE environment variable is not set")
        self._match_results_table = self._resource.Table(match_results_table)

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

    def create_player_profile_for_tm_account_id(
        self, tm_account_id: str, discord_account_id: int,
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
                    KEY_ELO: DEFAULT_ELO,
                    KEY_MATCHES_PLAYED: 0
                }
            )

            self._player_profiles_table.put_item(
                Item=player_profile.__dict__,
                ConditionExpression=Attr(KEY_TM_ACCOUNT_ID).not_exists() & Attr(KEY_DISCORD_ACCOUNT_ID).not_exists(),
            )

            return True
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":                
                logging.warning(
                    f"Player profile already exists for TM account ID {tm_account_id} and Discord account ID {discord_account_id}"
                )
                return False
            else:
                raise
        except Exception as e:
            logging.error(f"Error creating player profile in DynamoDB: {e}")
            raise

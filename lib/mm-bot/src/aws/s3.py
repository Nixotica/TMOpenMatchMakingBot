import json
import logging
import os
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError
from aws.constants import *
from models.bot_secrets import Secrets
from models.bot_configs import BotConfigs
from mypy_boto3_s3 import S3Client


class S3ClientManager:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(S3ClientManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self._client = self._create_client()

        secrets_bucket = os.environ.get("SECRETS_BUCKET")
        if secrets_bucket is None:
            raise ValueError("SECRETS_BUCKET environment variable is not set")
        self._secrets_bucket: str = secrets_bucket

    def _create_client(self) -> S3Client:
        try:
            s3_client = boto3.client("s3")
            return s3_client  # type: ignore
        except Exception as e:
            logging.error(f"Error creating S3 client: {e}")
            raise

    def _get_object_content(self, bucket_name: str, object_key: str) -> str:
        """
        Fetches the content of an S3 object as a string.
        """
        try:
            response = self._client.get_object(Bucket=bucket_name, Key=object_key)  # type: ignore
            content = response["Body"].read().decode("utf-8")
            return content
        except Exception as e:
            logging.error(
                f"Error fetching object {object_key} from bucket {bucket_name}: {e}"
            )
            raise

    def _get_json_as_dict(self, bucket_name: str, object_key: str) -> Dict[str, Any]:
        """
        Fetches and parses an S3 object as a JSON dictionary.
        """
        content = self._get_object_content(bucket_name, object_key)
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from object {object_key}: {e}")
            raise

    def get_secrets(self) -> Secrets:
        try:
            secrets_json = self._get_json_as_dict(self._secrets_bucket, SECRETS_JSON)
            return Secrets.from_dict(secrets_json)
        except Exception as e:
            logging.error(f"Error getting secrets: {e}")
            raise

    def get_configs(self) -> BotConfigs:
        try:
            configs_json = self._get_json_as_dict(self._secrets_bucket, CONFIGS_JSON)
            return BotConfigs.from_dict(configs_json)
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return BotConfigs.from_dict({})
            else:
                logging.error(f"Error getting configs: {e}")
                raise
        except Exception as e:
            logging.error(f"Error getting configs: {e}")
            raise

    def update_config(self, configs: BotConfigs) -> None:
        """Creates or overwrites the configs file in s3.

        Args:
            configs (BotConfigs): The configs to overwrite current configs with.
        """
        config_data = json.dumps(configs.to_dict())
        self._client.put_object(Bucket=self._secrets_bucket, Key=CONFIGS_JSON, Body=config_data)  # type: ignore

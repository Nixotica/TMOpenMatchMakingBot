import json
import os
from typing import Any, Dict
import boto3
from aws.bot_secrets import Secrets
from aws.constants import *


class S3:
    def __init__(self):
        self.s3_client = boto3.client("s3")

        secrets_bucket = os.environ.get("SECRETS_BUCKET")
        if secrets_bucket is None:
            raise ValueError("SECRETS_BUCKET environment variable is not set")
        self.secrets_bucket: str = secrets_bucket

    def _get_object_content(self, bucket_name: str, object_key: str) -> str:
        """
        Fetches the content of an S3 object as a string.
        """
        try:
            response = self.s3_client.get_object(Bucket=bucket_name, Key=object_key)
            content = response["Body"].read().decode("utf-8")
            return content
        except Exception as e:
            print(f"Error fetching object {object_key} from bucket {bucket_name}: {e}")
            raise

    def _get_json_as_dict(self, bucket_name: str, object_key: str) -> Dict[str, Any]:
        """
        Fetches and parses an S3 object as a JSON dictionary.
        """
        content = self._get_object_content(bucket_name, object_key)
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from object {object_key}: {e}")
            raise

    def get_secrets(self) -> Secrets:
        try:
            secrets_json = self._get_json_as_dict(self.secrets_bucket, SECRETS_JSON)
            return Secrets.from_dict(secrets_json)
        except Exception as e:
            print(f"Error getting secrets: {e}")
            raise

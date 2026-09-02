import json

import boto3

from portfolio_agent.config import settings

DEFAULT_SECRET_NAME = "portfolio-agent/schwab"


class SecretsTokenStorage:
    """Stores Schwab OAuth state in AWS Secrets Manager."""

    def __init__(
        self,
        secret_name: str = DEFAULT_SECRET_NAME,
        aws_profile: str | None = None,
    ):
        self.secret_name = secret_name

        if aws_profile:
            session = boto3.Session(profile_name=aws_profile)
        else:
            session = boto3.Session()

        self.client = session.client(
            "secretsmanager",
            region_name=settings.aws_region,
        )

    def _load_secret(self) -> dict:
        response = self.client.get_secret_value(SecretId=self.secret_name)

        return json.loads(response["SecretString"])

    def load_tokens(self) -> dict:
        """Load only the dynamic Schwab OAuth token state."""

        secret = self._load_secret()

        token_keys = {
            "access_token",
            "refresh_token",
            "expires_in",
            "access_token_created_at",
            "refresh_token_created_at",
        }

        return {key: secret[key] for key in token_keys if key in secret}

    def save_tokens(self, tokens: dict) -> None:
        """
        Update Schwab OAuth state while preserving
        the application's static Schwab credentials.
        """

        secret = self._load_secret()

        secret.update(tokens)

        self.client.put_secret_value(
            SecretId=self.secret_name,
            SecretString=json.dumps(secret),
        )

    def load_config(self) -> dict:
        """Load the static Schwab application configuration."""

        secret = self._load_secret()

        return {
            "client_id": secret.get("SCHWAB_CLIENT_ID"),
            "client_secret": secret.get("SCHWAB_CLIENT_SECRET"),
            "callback_url": secret.get("SCHWAB_CALLBACK_URL"),
        }

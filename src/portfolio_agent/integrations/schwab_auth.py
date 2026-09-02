import json
import os
import time
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests
from dotenv import load_dotenv

from portfolio_agent.integrations.auth_storage.secrets_token_storage import SecretsTokenStorage

PROJECT_ROOT = Path(__file__).resolve().parents[3]

TOKEN_FILE = PROJECT_ROOT / "tokens.json"
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)

AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"

ACCESS_TOKEN_LIFETIME = 30 * 60
REFRESH_TOKEN_LIFETIME = 7 * 24 * 60 * 60

EXPIRATION_BUFFER = 60


class ReauthorizationRequired(Exception):
    """
    Raised when automatic authentication is no longer
    possible and the user must complete Schwab OAuth again.
    """

    pass


def running_in_lambda():
    """Return True when the application is running in AWS Lambda."""

    return bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))


def get_secret_storage():
    """Create the Secrets Manager token storage backend."""

    return SecretsTokenStorage(secret_name="portfolio-agent/schwab")


def load_config():
    """
    Load Schwab application configuration.

    Local development uses .env. Lambda uses Secrets Manager.
    """

    if running_in_lambda():
        config = get_secret_storage().load_config()

        return {
            "client_id": config.get("client_id"),
            "client_secret": config.get("client_secret"),
            "callback_url": config.get("callback_url"),
        }

    return {
        "client_id": os.getenv("SCHWAB_CLIENT_ID"),
        "client_secret": os.getenv("SCHWAB_CLIENT_SECRET"),
        "callback_url": os.getenv("SCHWAB_CALLBACK_URL"),
    }


def validate_config():
    """Validate required Schwab application configuration."""

    config = load_config()

    if not config["client_id"]:
        raise ValueError("SCHWAB_CLIENT_ID is missing.")

    if not config["client_secret"]:
        raise ValueError("SCHWAB_CLIENT_SECRET is missing.")

    if not config["callback_url"]:
        raise ValueError("SCHWAB_CALLBACK_URL is missing.")

    return config


def load_tokens():
    """
    Load the currently stored Schwab OAuth state.

    Local development reads tokens.json. Lambda reads
    the shared Schwab secret from Secrets Manager.
    """

    if running_in_lambda():
        return get_secret_storage().load_tokens()

    if not TOKEN_FILE.exists():
        return None

    with open(TOKEN_FILE, "r") as file:
        return json.load(file)


def write_tokens(tokens):
    """
    Persist Schwab OAuth state to the active storage backend.
    """

    if running_in_lambda():
        get_secret_storage().save_tokens(tokens)
        return

    with open(TOKEN_FILE, "w") as file:
        json.dump(
            tokens,
            file,
            indent=4,
        )


def save_initial_tokens(tokens):
    """
    Save tokens received from a full OAuth authorization.

    Both token lifetime clocks begin when the authorization
    code is exchanged.
    """

    now = int(time.time())

    tokens["access_token_created_at"] = now
    tokens["refresh_token_created_at"] = now

    write_tokens(tokens)


def save_refreshed_tokens(
    new_tokens,
    old_tokens,
):
    """
    Save tokens received from an access-token refresh.

    The access-token clock restarts while the original
    refresh-token authorization clock is preserved.
    """

    now = int(time.time())

    new_tokens["access_token_created_at"] = now

    new_tokens["refresh_token_created_at"] = old_tokens["refresh_token_created_at"]

    write_tokens(new_tokens)


def access_token_is_valid(tokens):
    """Return True if the current access token is usable."""

    if not tokens:
        return False

    created_at = tokens.get("access_token_created_at")

    if created_at is None:
        return False

    expires_in = tokens.get(
        "expires_in",
        ACCESS_TOKEN_LIFETIME,
    )

    expires_at = int(created_at) + int(expires_in)

    return time.time() < (expires_at - EXPIRATION_BUFFER)


def refresh_token_is_valid(tokens):
    """
    Return True while the current Schwab refresh
    authorization is still valid.
    """

    if not tokens:
        return False

    created_at = tokens.get("refresh_token_created_at")

    if created_at is None:
        return False

    expires_at = int(created_at) + REFRESH_TOKEN_LIFETIME

    return time.time() < (expires_at - EXPIRATION_BUFFER)


def refresh_access_token(old_tokens):
    """
    Use the existing refresh token to obtain
    a fresh Schwab access token.
    """

    config = validate_config()

    if not refresh_token_is_valid(old_tokens):
        raise ReauthorizationRequired(
            "Schwab authorization has expired. Full OAuth reauthorization is required."
        )

    refresh_token = old_tokens.get("refresh_token")

    if not refresh_token:
        raise ReauthorizationRequired("No Schwab refresh token is available.")

    print("Access token expired. Refreshing...")

    response = requests.post(
        TOKEN_URL,
        auth=(
            config["client_id"],
            config["client_secret"],
        ),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )

    if not response.ok:
        raise ReauthorizationRequired(
            "Schwab rejected the refresh request. Full OAuth reauthorization may be required."
        )

    new_tokens = response.json()

    save_refreshed_tokens(
        new_tokens,
        old_tokens,
    )

    print("Access token refreshed successfully.")

    return new_tokens["access_token"]


def get_access_token():
    """
    Return a valid Schwab access token.

    Refresh the access token automatically when possible.
    """

    tokens = load_tokens()

    if not tokens:
        raise ReauthorizationRequired("No Schwab authorization exists.")

    if not refresh_token_is_valid(tokens):
        raise ReauthorizationRequired("Schwab authorization has expired.")

    if access_token_is_valid(tokens):
        return tokens["access_token"]

    return refresh_access_token(tokens)


def build_authorization_url():
    """Build the URL used to begin Schwab OAuth."""

    config = validate_config()

    return (
        f"{AUTH_URL}"
        f"?client_id="
        f"{quote(config['client_id'], safe='')}"
        f"&redirect_uri="
        f"{quote(config['callback_url'], safe='')}"
    )


def extract_authorization_code(
    redirect_url,
):
    """
    Extract Schwab's authorization code from
    the final callback URL.
    """

    parsed_url = urlparse(redirect_url)

    query = parse_qs(parsed_url.query)

    if "code" not in query:
        raise ValueError("No authorization code found in redirect URL.")

    return unquote(query["code"][0])


def exchange_code_for_tokens(code):
    """
    Exchange a Schwab authorization code for
    access and refresh tokens.
    """

    config = validate_config()

    response = requests.post(
        TOKEN_URL,
        auth=(
            config["client_id"],
            config["client_secret"],
        ),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config["callback_url"],
        },
        timeout=30,
    )

    if not response.ok:
        print("Schwab token request failed.")

        print(
            "Status:",
            response.status_code,
        )

        print(
            "Response:",
            response.text,
        )

        response.raise_for_status()

    return response.json()


def authenticate():
    """
    Run the interactive Schwab OAuth flow locally.

    Production reauthorization can later replace the
    browser-opening and URL-pasting steps with web endpoints.
    """

    if running_in_lambda():
        raise RuntimeError("Interactive Schwab authorization cannot run inside Lambda.")

    authorization_url = build_authorization_url()

    print("\nOpening Schwab authorization page...")

    webbrowser.open(authorization_url)

    print("\nLog into Schwab and authorize your account(s).")

    print("\nAfter Schwab redirects you, the page may fail to load.")

    print("Copy the ENTIRE URL from your browser's address bar.")

    redirect_url = input("\nPaste the redirect URL here:\n\n").strip()

    code = extract_authorization_code(redirect_url)

    print("\nAuthorization code received.")

    print("Exchanging code for tokens...")

    tokens = exchange_code_for_tokens(code)

    save_initial_tokens(tokens)

    print("\nSUCCESS: Schwab authorization completed.")

    print(
        "Access token expires in:",
        tokens.get("expires_in"),
        "seconds",
    )

    print("Refresh authorization valid for approximately 7 days.")

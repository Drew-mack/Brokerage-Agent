import json
from datetime import datetime
from pathlib import Path

from portfolio_agent.storage.serialization import (
    portfolio_to_snapshot,
    snapshot_to_portfolio,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = PROJECT_ROOT / "data"

SNAPSHOT_DIR = DATA_DIR / "portfolio_snapshots"


class LocalStorageError(Exception):
    """
    Raised when local portfolio storage fails.
    """

    pass


def save_snapshot(portfolio):
    """
    Save a Portfolio snapshot to a local JSON file.
    """

    SNAPSHOT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    snapshot = portfolio_to_snapshot(portfolio)

    timestamp = datetime.fromisoformat(snapshot["timestamp"])

    filename = timestamp.strftime("%Y-%m-%dT%H-%M-%SZ.json")

    output_file = SNAPSHOT_DIR / filename

    try:
        with open(
            output_file,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                snapshot,
                file,
                indent=4,
            )

    except OSError as error:
        raise LocalStorageError(f"Could not save portfolio snapshot: {error}") from error

    return output_file


def load_snapshot_file(filepath):
    """
    Load one local snapshot JSON file.
    """

    try:
        with open(
            filepath,
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except (
        OSError,
        json.JSONDecodeError,
    ) as error:
        raise LocalStorageError(f"Could not load portfolio snapshot: {error}") from error


def get_snapshot_files():
    """
    Return all local snapshot files chronologically.
    """

    if not SNAPSHOT_DIR.exists():
        return []

    return sorted(SNAPSHOT_DIR.glob("*.json"))


def get_latest_snapshot():
    """
    Return the latest local snapshot.
    """

    snapshot_files = get_snapshot_files()

    if not snapshot_files:
        return None

    return load_snapshot_file(snapshot_files[-1])


def get_latest_portfolio():
    """
    Return the latest locally stored Portfolio.
    """

    snapshot = get_latest_snapshot()

    if snapshot is None:
        return None

    return snapshot_to_portfolio(snapshot)


def get_all_snapshots():
    """
    Return all locally stored snapshots.
    """

    return [load_snapshot_file(filepath) for filepath in get_snapshot_files()]

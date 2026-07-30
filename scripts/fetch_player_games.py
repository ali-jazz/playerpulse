from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_BASE_URL = "https://api.chess.com/pub/player"
USER_AGENT = "PlayerPulse/0.1 (https://github.com/ali-jazz/playerpulse)"


def fetch_json(url: str) -> dict:
    """Send an HTTP request and return the JSON response."""
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_archive_urls(username: str) -> list[str]:
    """Return the monthly archive URLs available for a player."""
    url = f"{API_BASE_URL}/{username.lower()}/games/archives"
    data = fetch_json(url)
    return data.get("archives", [])


def save_monthly_archive(
    username: str,
    archive_url: str,
    output_dir: Path,
) -> int:
    """Download one monthly archive and save it as raw JSON."""
    year, month = archive_url.rstrip("/").split("/")[-2:]
    data = fetch_json(archive_url)
    games = data.get("games", [])

    output_file = (
        output_dir
        / f"{username.lower()}_games_{year}_{month}.json"
    )

    output_file.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        f"Downloaded {len(games)} games for "
        f"{year}-{month} -> {output_file}"
    )

    return len(games)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download monthly Chess.com game archives."
    )
    parser.add_argument("username", help="Chess.com username")
    parser.add_argument(
        "--months",
        type=int,
        default=1,
        help="Number of most recent monthly archives to download",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download every available monthly archive",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw"),
        help="Directory where raw JSON files will be saved",
    )
    args = parser.parse_args()

    if args.months < 1:
        raise SystemExit("--months must be at least 1.")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        archives = fetch_archive_urls(args.username)

        if not archives:
            raise SystemExit(
                f"No game archives found for {args.username}."
            )

        selected_archives = (
            archives if args.all else archives[-args.months:]
        )

        total_games = 0

        for archive_url in selected_archives:
            total_games += save_monthly_archive(
                args.username,
                archive_url,
                args.output_dir,
            )

            # Small pause to avoid sending requests too rapidly.
            time.sleep(0.25)

    except HTTPError as error:
        raise SystemExit(
            f"Chess.com returned HTTP {error.code}: {error.reason}"
        ) from error
    except URLError as error:
        raise SystemExit(
            f"Network error: {error.reason}"
        ) from error

    print(
        f"Finished: {total_games} games downloaded "
        f"from {len(selected_archives)} monthly archives."
    )


if __name__ == "__main__":
    main()

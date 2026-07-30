from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_BASE_URL = "https://api.chess.com/pub/player"
USER_AGENT = "PlayerPulse/0.1 (https://github.com/ali-jazz/playerpulse)"


def fetch_player_profile(username: str) -> dict:
    """Fetch a public Chess.com player profile."""
    url = f"{API_BASE_URL}/{username.lower()}"

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download a public Chess.com player profile."
    )
    parser.add_argument("username", help="Chess.com username")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw"),
        help="Directory where the raw JSON file will be saved",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_file = args.output_dir / f"{args.username.lower()}_profile.json"

    try:
        profile = fetch_player_profile(args.username)
    except HTTPError as error:
        raise SystemExit(
            f"Chess.com returned HTTP {error.code}: {error.reason}"
        ) from error
    except URLError as error:
        raise SystemExit(f"Network error: {error.reason}") from error

    output_file.write_text(
        json.dumps(profile, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Downloaded profile for {profile['username']}")
    print(f"Saved raw data to {output_file}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def unix_to_utc(timestamp: int | None) -> str | None:
    """Convert a Unix timestamp into an ISO 8601 UTC datetime."""
    if timestamp is None:
        return None

    return datetime.fromtimestamp(
        timestamp,
        tz=timezone.utc,
    ).isoformat()


def flatten_game(game: dict[str, Any]) -> dict[str, Any]:
    """Flatten one nested Chess.com game into an analytics-friendly record."""
    white = game.get("white", {})
    black = game.get("black", {})
    accuracies = game.get("accuracies", {})

    return {
        "game_id": game.get("uuid"),
        "game_url": game.get("url"),
        "end_time_unix": game.get("end_time"),
        "end_time_utc": unix_to_utc(game.get("end_time")),
        "rated": game.get("rated"),
        "time_control": game.get("time_control"),
        "time_class": game.get("time_class"),
        "rules": game.get("rules"),
        "eco": game.get("eco"),
        "white_username": white.get("username"),
        "white_rating": white.get("rating"),
        "white_result": white.get("result"),
        "white_accuracy": accuracies.get("white"),
        "black_username": black.get("username"),
        "black_rating": black.get("rating"),
        "black_result": black.get("result"),
        "black_accuracy": accuracies.get("black"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Flatten raw Chess.com game data into JSON Lines."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Raw monthly Chess.com games JSON file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
        help="Directory where transformed data will be saved",
    )
    args = parser.parse_args()

    raw_data = json.loads(
        args.input_file.read_text(encoding="utf-8")
    )
    games = raw_data.get("games", [])

    if not isinstance(games, list):
        raise SystemExit("Invalid input: 'games' must be a list.")

    flattened_games = [flatten_game(game) for game in games]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_file = (
        args.output_dir
        / f"{args.input_file.stem}_flattened.jsonl"
    )

    with output_file.open("w", encoding="utf-8") as file:
        for game in flattened_games:
            file.write(json.dumps(game, sort_keys=True) + "\n")

    print(f"Transformed {len(flattened_games)} games")
    print(f"Saved processed data to {output_file}")


if __name__ == "__main__":
    main()

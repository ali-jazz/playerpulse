from __future__ import annotations

import argparse
import json
from pathlib import Path

from transform_games import flatten_game


def transform_file(input_file: Path, output_dir: Path) -> int:
    """Transform one monthly raw archive into JSON Lines."""
    raw_data = json.loads(
        input_file.read_text(encoding="utf-8")
    )
    games = raw_data.get("games", [])

    if not isinstance(games, list):
        raise ValueError(
            f"Invalid input in {input_file}: 'games' must be a list."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{input_file.stem}_flattened.jsonl"

    with output_file.open("w", encoding="utf-8") as file:
        for game in games:
            flattened_game = flatten_game(game)
            file.write(
                json.dumps(flattened_game, sort_keys=True) + "\n"
            )

    print(
        f"Transformed {len(games)} games: "
        f"{input_file} -> {output_file}"
    )

    return len(games)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transform all raw monthly Chess.com archives."
    )
    parser.add_argument(
        "username",
        help="Chess.com username",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/raw"),
        help="Directory containing raw monthly archives",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
        help="Directory where JSONL files will be saved",
    )
    args = parser.parse_args()

    pattern = f"{args.username.lower()}_games_[0-9][0-9][0-9][0-9]_[0-9][0-9].json"
    input_files = sorted(args.input_dir.glob(pattern))

    if not input_files:
        raise SystemExit(
            f"No monthly archives found in {args.input_dir} "
            f"for username {args.username}."
        )

    total_games = 0

    for input_file in input_files:
        total_games += transform_file(
            input_file,
            args.output_dir,
        )

    print(
        f"Finished: transformed {total_games} games "
        f"from {len(input_files)} monthly archives."
    )


if __name__ == "__main__":
    main()

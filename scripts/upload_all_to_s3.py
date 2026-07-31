from __future__ import annotations

import argparse
import os
from pathlib import Path

from upload_to_s3 import upload_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload all monthly Chess.com archives to AWS S3."
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
        "--bucket",
        default=os.getenv("PLAYERPULSE_S3_BUCKET"),
        help=(
            "Destination S3 bucket. Can also be supplied through "
            "PLAYERPULSE_S3_BUCKET."
        ),
    )
    parser.add_argument(
        "--region",
        default=os.getenv(
            "AWS_DEFAULT_REGION",
            "ca-central-1",
        ),
        help="AWS region",
    )
    args = parser.parse_args()

    if not args.bucket:
        raise SystemExit(
            "Provide --bucket or set PLAYERPULSE_S3_BUCKET."
        )

    pattern = (
        f"{args.username.lower()}_games_"
        "[0-9][0-9][0-9][0-9]_[0-9][0-9].json"
    )
    input_files = sorted(args.input_dir.glob(pattern))

    if not input_files:
        raise SystemExit(
            f"No monthly archives found for {args.username} "
            f"in {args.input_dir}."
        )

    uploaded_files = 0

    for input_file in input_files:
        upload_file(
            input_file=input_file,
            bucket=args.bucket,
            region=args.region,
        )
        uploaded_files += 1
        print("-" * 60)

    print(
        f"Finished: uploaded {uploaded_files} monthly archives "
        f"to s3://{args.bucket}/chesscom/games/"
    )


if __name__ == "__main__":
    main()

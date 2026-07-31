from __future__ import annotations

import argparse
import mimetypes
import os
import re
from pathlib import Path

import boto3
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
)

FILE_PATTERN = re.compile(
    r"^(?P<username>.+)_games_"
    r"(?P<year>\d{4})_(?P<month>\d{2})\.json$"
)


def build_s3_key(input_file: Path) -> str:
    """Build a partitioned S3 key from a monthly archive filename."""
    match = FILE_PATTERN.match(input_file.name)

    if match is None:
        raise ValueError(
            "Expected filename format: "
            "<username>_games_<year>_<month>.json"
        )

    username = match.group("username")
    year = match.group("year")
    month = match.group("month")

    return (
        "chesscom/games/"
        f"username={username}/"
        f"year={year}/"
        f"month={month}/"
        "games.json"
    )


def upload_file(
    input_file: Path,
    bucket: str,
    region: str,
) -> str:
    """Upload one raw archive to a partitioned location in S3."""
    if not input_file.is_file():
        raise FileNotFoundError(f"File not found: {input_file}")

    s3_key = build_s3_key(input_file)
    content_type = (
        mimetypes.guess_type(input_file.name)[0]
        or "application/octet-stream"
    )

    s3_client = boto3.client("s3", region_name=region)

    s3_client.upload_file(
        str(input_file),
        bucket,
        s3_key,
        ExtraArgs={
            "ContentType": content_type,
            "ServerSideEncryption": "AES256",
        },
    )

    metadata = s3_client.head_object(
        Bucket=bucket,
        Key=s3_key,
    )

    print(f"Uploaded {input_file}")
    print(f"Destination: s3://{bucket}/{s3_key}")
    print(f"Size: {metadata['ContentLength']} bytes")
    print(
        "Encryption: "
        f"{metadata.get('ServerSideEncryption', 'unknown')}"
    )

    return s3_key


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload a monthly Chess.com archive to AWS S3."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Raw monthly archive to upload",
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

    try:
        upload_file(
            input_file=args.input_file,
            bucket=args.bucket,
            region=args.region,
        )
    except (
        FileNotFoundError,
        ValueError,
        NoCredentialsError,
        BotoCoreError,
        ClientError,
    ) as error:
        raise SystemExit(f"S3 upload failed: {error}") from error


if __name__ == "__main__":
    main()

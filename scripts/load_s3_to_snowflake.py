from __future__ import annotations

import os
import sys

import snowflake.connector
from snowflake.connector.errors import Error


SNOWFLAKE_ACCOUNT = os.getenv(
    "SNOWFLAKE_ACCOUNT",
    "WVWTAUJ-KP93476",
)
SNOWFLAKE_USER = os.getenv(
    "SNOWFLAKE_USER",
    "AJAZZAR",
)
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")

SNOWFLAKE_ROLE = os.getenv(
    "SNOWFLAKE_ROLE",
    "ACCOUNTADMIN",
)
SNOWFLAKE_WAREHOUSE = os.getenv(
    "SNOWFLAKE_WAREHOUSE",
    "PLAYERPULSE_WH",
)
SNOWFLAKE_DATABASE = os.getenv(
    "SNOWFLAKE_DATABASE",
    "PLAYERPULSE",
)

S3_STAGE_URL = (
    "s3://"
    "playerpulse-ali-jazz-raw-2026-218484443553-ca-central-1-an/"
    "chesscom/"
)

STORAGE_INTEGRATION = "PLAYERPULSE_S3_INT"


def connect_to_snowflake():
    """Create a Snowflake connection using environment credentials."""
    if not SNOWFLAKE_PASSWORD:
        raise RuntimeError(
            "SNOWFLAKE_PASSWORD environment variable is not set."
        )

    return snowflake.connector.connect(
        account=SNOWFLAKE_ACCOUNT,
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        role=SNOWFLAKE_ROLE,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
    )


def execute(cursor, sql: str) -> None:
    """Execute SQL and print the statement category."""
    cursor.execute(sql)


def main() -> None:
    connection = None

    try:
        connection = connect_to_snowflake()
        cursor = connection.cursor()

        execute(
            cursor,
            """
            CREATE SCHEMA IF NOT EXISTS PLAYERPULSE.RAW
            """,
        )

        execute(
            cursor,
            f"""
            CREATE STAGE IF NOT EXISTS
                PLAYERPULSE.RAW.PLAYERPULSE_S3_STAGE
            URL = '{S3_STAGE_URL}'
            STORAGE_INTEGRATION = {STORAGE_INTEGRATION}
            FILE_FORMAT = (TYPE = JSON)
            """,
        )

        execute(
            cursor,
            """
            CREATE TABLE IF NOT EXISTS
                PLAYERPULSE.RAW.GAME_ARCHIVES (
                    source_file STRING,
                    loaded_at TIMESTAMP_LTZ,
                    payload VARIANT
                )
            """,
        )

        # Full refresh keeps the raw load deterministic and idempotent
        # for this portfolio-sized dataset.
        execute(
            cursor,
            """
            TRUNCATE TABLE PLAYERPULSE.RAW.GAME_ARCHIVES
            """,
        )

        execute(
            cursor,
            """
            COPY INTO PLAYERPULSE.RAW.GAME_ARCHIVES (
                source_file,
                loaded_at,
                payload
            )
            FROM (
                SELECT
                    METADATA$FILENAME,
                    METADATA$START_SCAN_TIME,
                    t.$1
                FROM
                    @PLAYERPULSE.RAW.PLAYERPULSE_S3_STAGE t
            )
            PATTERN = '.*games[.]json'
            FORCE = TRUE
            ON_ERROR = 'ABORT_STATEMENT'
            """,
        )

        execute(
            cursor,
            """
            CREATE OR REPLACE TABLE PLAYERPULSE.RAW.GAMES AS
            SELECT
                archive.source_file,
                archive.loaded_at,
                game.value AS game_payload
            FROM PLAYERPULSE.RAW.GAME_ARCHIVES AS archive,
            LATERAL FLATTEN(
                INPUT => archive.payload:games
            ) AS game
            """,
        )

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_games,
                COUNT(
                    DISTINCT game_payload:"uuid"::STRING
                ) AS unique_games
            FROM PLAYERPULSE.RAW.GAMES
            """
        )

        total_games, unique_games = cursor.fetchone()

        print("Snowflake raw load completed")
        print(f"Total games: {total_games}")
        print(f"Unique games: {unique_games}")

        if total_games != unique_games:
            raise RuntimeError(
                "Duplicate game IDs detected in RAW.GAMES."
            )

    except (Error, RuntimeError) as error:
        print(
            f"Snowflake load failed: {error}",
            file=sys.stderr,
        )
        raise SystemExit(1) from error

    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    main()

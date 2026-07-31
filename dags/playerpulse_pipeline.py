from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG


with DAG(
    dag_id="playerpulse_pipeline",
    description=(
        "Ingest and transform public Chess.com player data."
    ),
    schedule=None,
    start_date=pendulum.datetime(2026, 7, 1, tz="UTC"),
    catchup=False,
    default_args={
        "owner": "ali",
        "retries": 2,
        "retry_delay": timedelta(minutes=1),
    },
    tags=["playerpulse", "chess", "data-engineering"],
) as dag:

    fetch_profile = BashOperator(
        task_id="fetch_player_profile",
        bash_command=(
            "python3 /opt/airflow/scripts/"
            "fetch_player_profile.py ajaza"
        ),
        cwd="/opt/airflow",
    )

    fetch_games = BashOperator(
        task_id="fetch_player_games",
        bash_command=(
            "python3 /opt/airflow/scripts/"
            "fetch_player_games.py ajaza --all"
        ),
        cwd="/opt/airflow",
    )

    transform_games = BashOperator(
        task_id="transform_all_games",
        bash_command=(
            "python3 /opt/airflow/scripts/"
            "transform_all_games.py ajaza"
        ),
        cwd="/opt/airflow",
    )
    upload_games_to_s3 = BashOperator(
        task_id="upload_games_to_s3",
        bash_command=(
            "python3 /opt/airflow/scripts/"
            "upload_all_to_s3.py ajaza "
            "--bucket "
            "playerpulse-ali-jazz-raw-2026-218484443553-ca-central-1-an"
        ),
        cwd="/opt/airflow",
    )
    fetch_profile >> fetch_games >> transform_games >> upload_games_to_s3

import pendulum

from airflow.sdk import dag, task


@dag(
    dag_id="playerpulse_smoke_test",
    schedule=None,
    start_date=pendulum.datetime(2026, 7, 30, tz="UTC"),
    catchup=False,
    tags=["playerpulse"],
)
def playerpulse_smoke_test():

    @task
    def verify_environment():
        print("PlayerPulse Airflow environment is working.")
        return "ready"

    verify_environment()


playerpulse_smoke_test()

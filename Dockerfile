FROM apache/airflow:3.3.0

ARG AIRFLOW_VERSION=3.3.0

RUN pip install --no-cache-dir \
    "apache-airflow==${AIRFLOW_VERSION}" \
    "dbt-snowflake==1.12.0"

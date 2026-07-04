"""
Airflow DAG — twitch_offline_pipeline

Orchestrates the BATCH (offline) layer end to end, on a daily schedule:

    upload raw  ->  Glue Spark sentiment  ->  Glue Crawler  ->  Redshift (dbt Silver+Gold)
                ->  snapshot  ->  refresh BI dashboard

Drop it into any Airflow 2.x or Amazon MWAA environment that has the
Amazon provider installed (`apache-airflow-providers-amazon`).

Env vars expected on the Airflow workers:
    PROJECT_DIR  -> path to this repo on the worker
    DATA_DIR     -> path to the raw chat_*.jsonl files
"""
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.amazon.aws.operators.glue import GlueJobOperator
from airflow.providers.amazon.aws.operators.glue_crawler import GlueCrawlerOperator

REGION = "ap-northeast-1"
BUCKET = f"twitch-data-{os.environ.get('AWS_ACCOUNT_ID', '000000000000')}"

default_args = {
    "owner": "data-eng",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="twitch_offline_pipeline",
    description="S3 -> Spark sentiment -> Glue Catalog -> Redshift (dbt star schema) -> BI snapshot",
    schedule="0 5 * * *",            # every day at 05:00
    start_date=datetime(2026, 6, 1),
    catchup=False,
    default_args=default_args,
    tags=["twitch", "batch", "redshift", "dbt"],
) as dag:

    # 1) land raw chat into the Bronze zone of the S3 data lake
    upload_bronze = BashOperator(
        task_id="upload_bronze",
        bash_command=(
            f"aws s3 cp $DATA_DIR s3://{BUCKET}/bronze/chat/ "
            f"--recursive --exclude '*' --include 'chat_*.jsonl' --region {REGION}"
        ),
    )

    # 2) distributed VADER sentiment scoring on Spark -> bronze/chat_scored/ (Parquet)
    spark_sentiment = GlueJobOperator(
        task_id="spark_sentiment",
        job_name="twitch-sentiment-spark",   # script: glue_jobs/spark_sentiment.py
        region_name=REGION,
    )

    # 3) catalog the scored Parquet so Redshift Spectrum can read it
    crawl_bronze = GlueCrawlerOperator(
        task_id="crawl_bronze",
        config={"Name": "twitch-bronze-crawler"},
        region_name=REGION,
    )

    # 4) build + test the Silver + Gold star schema with dbt
    build_warehouse = BashOperator(
        task_id="build_warehouse",
        bash_command="cd $PROJECT_DIR/dbt && dbt run --profiles-dir . && dbt test --profiles-dir .",
    )

    # 5) query Gold -> dashboard_snapshot.json
    build_snapshot = BashOperator(
        task_id="build_snapshot",
        bash_command="python $PROJECT_DIR/scripts/build_snapshot_redshift.py",
    )

    # 6) push the fresh snapshot into the serverless BI dashboard
    refresh_dashboard = BashOperator(
        task_id="refresh_dashboard",
        bash_command=(
            "cd $PROJECT_DIR/dashboards && "
            "zip -q /tmp/off.zip offline_dashboard_lambda.py "
            "$PROJECT_DIR/results/dashboard_snapshot.json && "
            f"aws lambda update-function-code --function-name twitch-offline-dashboard "
            f"--zip-file fileb:///tmp/off.zip --region {REGION}"
        ),
    )

    upload_bronze >> spark_sentiment >> crawl_bronze >> build_warehouse >> build_snapshot >> refresh_dashboard

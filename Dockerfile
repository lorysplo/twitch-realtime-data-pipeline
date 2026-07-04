# Container for the batch build/scoring scripts (dbt models + snapshot + local validation).
# Orchestration (Airflow) and BI (Superset) run in their own images — see dags/ and superset/.
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
      boto3>=1.34 \
      vaderSentiment>=3.3.2 \
      dbt-redshift>=1.7 \
      duckdb>=0.10

COPY . .

ENV AWS_DEFAULT_REGION=ap-northeast-1 \
    PYTHONUNBUFFERED=1

# default: build + test the Gold warehouse with dbt.
# override at run time, e.g.:  docker run --rm twitch-pipeline python scripts/build_snapshot_redshift.py
CMD ["sh", "-c", "cd dbt && dbt run --profiles-dir . && dbt test --profiles-dir ."]

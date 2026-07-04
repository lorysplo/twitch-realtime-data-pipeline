# Runbook

Operational notes for running, refreshing, troubleshooting, and tearing down the pipeline.

## Run

```bash
make install            # deps
# batch layer
make dbt-build          # build + test Silver + Gold (dbt)
make snapshot           # query Gold -> results/dashboard_snapshot.json
make deploy-dashboards  # push snapshot into the offline BI Lambda
# speed layer
make replay CH=chat_forsen.jsonl   # replay chat -> Kinesis (loops)
```

The batch flow also runs as an Airflow DAG — see `dags/twitch_offline_pipeline.py`.

## Refresh the dashboards
- **Offline:** re-run `make dbt-build && make snapshot && make deploy-dashboards`.
- **Live:** keep a `make replay` running; the dashboard auto-refreshes every 2s off DynamoDB.

## Common failures → fixes

| Symptom | Cause | Fix |
|---|---|---|
| Raid viewer counts all NULL | `event_info` inferred as a struct; sampling dropped `viewerCount` | store `event_info` as a JSON string + `json_extract_path_text` (already in the models) |
| Live dashboard shows all 0 | `boto3 table.scan()` returns only the first ~1 MB page | paginate with `LastEvaluatedKey` + TTL on writes (already in `dashboard_lambda.py`) |
| Lambda Function URL → 403 | new account needs both URL perms | add `lambda:InvokeFunctionUrl` **and** `lambda:InvokeFunction` (Principal `*`) |
| `relation bronze.chat_scored does not exist` | external schema / crawler not done | run `dbt/external_schema.sql`, then the Glue crawler |

## Cost control / teardown
- **Kinesis** bills per shard-hour — the only thing that bleeds when idle. Delete after a demo:
  ```bash
  aws kinesis delete-stream --stream-name twitch-chat-stream --enforce-consumer-deletion --region ap-northeast-1
  aws kinesis delete-stream --stream-name viewer-counts       --enforce-consumer-deletion --region ap-northeast-1
  ```
- **Redshift Serverless** doesn't bill compute when idle; delete to reach zero:
  ```bash
  aws redshift-serverless delete-workgroup --workgroup-name twitch-wg --region ap-northeast-1
  aws redshift-serverless delete-namespace --namespace-name twitch    --region ap-northeast-1
  ```
- **Lambda / DynamoDB (on-demand) / Glue / S3** are ~free when idle.
- Full teardown: `cd infra && terraform destroy -var="account_id=<acct>"`.

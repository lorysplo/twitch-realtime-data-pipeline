# infra/ — Infrastructure as Code (Terraform)

Codifies the AWS resources this project uses, so the whole stack can be recreated reproducibly.

| Resource | Purpose |
|---|---|
| `aws_kinesis_stream` ×2 | speed-layer ingest (`twitch-chat-stream`, `viewer-counts`) |
| `aws_dynamodb_table` | realtime metrics store (composite key + TTL) |
| `aws_s3_bucket` | Bronze data lake |
| `aws_glue_catalog_database` | Data Catalog (`twitch`) for Spectrum |
| `aws_redshiftserverless_namespace` / `_workgroup` | the warehouse (8 RPU) |

```bash
cd infra
terraform init
terraform plan  -var="account_id=<ACCOUNT_ID>"
terraform apply -var="account_id=<ACCOUNT_ID>"
```

> **Honesty note:** during development these were created via the AWS CLI/console; this Terraform is
> the codified version of the same infrastructure. IAM roles, the Lambda function code, the Glue job
> script, and the dbt models are deployed separately (see `scripts/`, `glue_jobs/`, `dbt/`, `dashboards/`).
> Secrets (the Redshift admin password) are supplied out-of-band, never committed.

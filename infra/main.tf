# Infrastructure as Code (Terraform) for the Twitch chat pipeline.
#
# HONESTY NOTE: during development these AWS resources were created via the CLI / console.
# This Terraform is the *codified, reproducible* version of that same infrastructure — apply it
# to stand the project up from scratch in a new account. Lambda function code and the Glue job
# script are deployed separately (see scripts/, glue_jobs/, dashboards/).

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

# ----------------------------------------------------------------------------
# Speed layer — Kinesis (2 streams) + DynamoDB
# ----------------------------------------------------------------------------
resource "aws_kinesis_stream" "chat" {
  name        = "twitch-chat-stream"
  shard_count = 1
  retention_period = 24
}

resource "aws_kinesis_stream" "viewers" {
  name        = "viewer-counts"
  shard_count = 1
  retention_period = 24
}

resource "aws_dynamodb_table" "metrics" {
  name         = "twitch-realtime-metrics"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "channel"
  range_key    = "window"

  attribute {
    name = "channel"
    type = "S"
  }
  attribute {
    name = "window"
    type = "N"
  }

  ttl {
    attribute_name = "expire_at"
    enabled        = true
  }
}

# ----------------------------------------------------------------------------
# Data lake — S3 (Bronze) + Glue Data Catalog
# ----------------------------------------------------------------------------
resource "aws_s3_bucket" "lake" {
  bucket = "twitch-data-${var.account_id}"
}

resource "aws_glue_catalog_database" "twitch" {
  name = "twitch"
}

# ----------------------------------------------------------------------------
# Warehouse — Redshift Serverless (namespace + workgroup)
# ----------------------------------------------------------------------------
resource "aws_redshiftserverless_namespace" "twitch" {
  namespace_name = "twitch"
  admin_username = "admin"
  # admin_user_password supplied out-of-band (do not commit secrets)
}

resource "aws_redshiftserverless_workgroup" "twitch" {
  namespace_name      = aws_redshiftserverless_namespace.twitch.namespace_name
  workgroup_name      = "twitch-wg"
  base_capacity       = 8
  publicly_accessible = true
}

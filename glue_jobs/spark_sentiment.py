#!/usr/bin/env python3
"""
spark_sentiment.py — "Step 4: score chat sentiment with Spark," as requested by the boss.
Reads the S3 Bronze chat_*.jsonl files, runs VADER sentiment scoring in a distributed
fashion, and writes chat_scored (Parquet) with a sentiment_score column.

Why Spark: scoring hundreds of thousands of chat messages one by one with VADER is
"heavy compute / Python" work that Spark handles in a distributed manner; dbt only does
SQL modeling. This is the standard industry division of labor (Spark for heavy compute +
dbt for modeling).

Usage (local):
  spark-submit --py-files sentiment.py spark_sentiment.py \
    --in  s3://twitch-data-<account-id>/bronze/chat/ \
    --out s3://twitch-data-<account-id>/bronze/chat_scored/

Usage (AWS Glue Spark Job):
  Upload the script to S3; job parameters:
    --extra-py-files            s3://.../sentiment.py
    --additional-python-modules vaderSentiment
    --in / --out                same as above
Key point: serialize the entire event_info column to a JSON string before writing it out
      (preserves all keys, so downstream Redshift can use json_extract_path_text to read a
      raid's viewerCount; this avoids having it inferred as a struct and losing keys).
"""
import argparse

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_json, udf
from pyspark.sql.types import DoubleType

import sentiment  # shares the same scoring logic as the realtime/local paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="input Bronze chat directory (S3)")
    ap.add_argument("--out", dest="out", required=True, help="output chat_scored directory (S3, Parquet)")
    args, _ = ap.parse_known_args()  # Glue injects extra parameters; use known_args for tolerance

    spark = SparkSession.builder.appName("twitch-chat-sentiment").getOrCreate()

    # Read the Bronze chat (Spark infers the schema from the full dataset by default, so all event_info keys are present)
    df = spark.read.json(args.inp)

    # VADER scoring: text + emotes -> compound score (-1 to +1)
    def _score(text, emotes):
        return float(sentiment.score(text or "", emotes or "")[0])
    score_udf = udf(_score, DoubleType())

    out = df.withColumn("sentiment_score", score_udf(col("text"), col("emotes")))

    # Serialize the entire (nested) event_info column to a JSON string column, preserving all keys
    if "event_info" in df.columns:
        out = out.withColumn("event_info", to_json(col("event_info")))

    out.write.mode("overwrite").parquet(args.out)
    spark.stop()
    print(f"[✓] Spark scoring complete -> {args.out}")


if __name__ == "__main__":
    main()

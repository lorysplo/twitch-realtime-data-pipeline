#!/usr/bin/env python3
"""
lambda_function.py — Cloud-side processing for the realtime path (AWS Lambda).
Triggered by Kinesis: decode a batch of chat messages → compute sentiment + count emotes → write this batch's metrics into DynamoDB.
Shares sentiment.py's scoring logic with the local realtime.py.

Packaging: zip this file + sentiment.py + the vaderSentiment library together; see step 4 of "Realtime Path - Deployment Steps.md".
"""
import base64
import collections
import json
import os
import time
from decimal import Decimal

import boto3

import sentiment  # shares the same scoring logic with the local realtime version

AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
TABLE_NAME = os.environ.get("METRICS_TABLE", "twitch-realtime-metrics")

ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
table = ddb.Table(TABLE_NAME)


def handler(event, context):
    records = event.get("Records", [])
    # A single Lambda handles both streams (topics) at once:
    #   - twitch-chat-stream: chat messages (have msg_type) → compute message volume/sentiment/emotes per channel
    #   - viewer-counts: viewer counts (have viewer_count, no msg_type) → take the latest count per channel
    stats = {}            # chat: channel -> {count, sent_sum, emotes}
    viewers = {}          # counts: channel -> (ts, viewer_count, game)

    for rec in records:
        data = base64.b64decode(rec["kinesis"]["data"]).decode("utf-8")
        try:
            r = json.loads(data)
        except ValueError:
            continue
        ch = r.get("channel") or "unknown"

        # viewer-count heartbeat (second topic): take the latest record per channel in this batch
        if "viewer_count" in r and not r.get("msg_type"):
            t = r.get("ts", 0)
            if ch not in viewers or t >= viewers[ch][0]:
                viewers[ch] = (t, int(r.get("viewer_count", 0)), r.get("game", ""))
            continue

        # chat (first topic)
        s = stats.setdefault(ch, {"count": 0, "sent_sum": 0.0, "emotes": collections.Counter()})
        comp, _ = sentiment.score(r.get("text", ""), r.get("emotes", ""))
        s["sent_sum"] += comp
        for nm in sentiment.extract_emotes(r.get("text", ""), r.get("emotes", "")):
            s["emotes"][nm] += 1
        s["count"] += 1

    now = int(time.time())
    total = 0

    expire_at = now + 1800   # TTL: auto-expires after 30 minutes so the table doesn't grow without bound (works with the table's TTL setting)

    # write chat metrics (keyed by channel + timestamp)
    for ch, s in stats.items():
        top = s["emotes"].most_common(1)
        table.update_item(
            Key={"channel": ch, "window": now},
            UpdateExpression=(
                "SET avg_sentiment = :avg_sentiment, top_emote = :top_emote, expire_at = :exp "
                "ADD #count :count, sent_sum :sent_sum"
            ),
            ExpressionAttributeNames={"#count": "count"},
            ExpressionAttributeValues={
                ":count": s["count"],
                ":sent_sum": Decimal(str(round(s["sent_sum"], 6))),
                ":avg_sentiment": Decimal(str(round(s["sent_sum"] / s["count"], 3))),
                ":top_emote": top[0][0] if top else "",
                ":exp": expire_at,
            },
        )
        total += s["count"]

    # write viewer counts (use "#viewers#channel" as a separate primary key, isolated from the chat metrics)
    for ch, (t, vc, game) in viewers.items():
        table.put_item(Item={
            "channel": "#viewers#" + ch,
            "window": now,
            "name": ch,
            "viewers": vc,
            "game": game,
            "expire_at": expire_at,
        })

    return {"ok": True, "n": total, "channels": list(stats), "viewers": list(viewers)}

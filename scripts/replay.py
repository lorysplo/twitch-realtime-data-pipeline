#!/usr/bin/env python3
"""
replay.py — Emit chat_raw.jsonl one record at a time using the original time gaps, simulating a realtime stream.
Usage:
    python replay.py chat_raw.jsonl                 # original speed, print to screen (debug)
    python replay.py chat_raw.jsonl --speed 5       # 5x speed
    python replay.py chat_raw.jsonl --loop          # loop the replay
    python replay.py chat_raw.jsonl --to-kinesis --stream twitch-chat-stream
speed: 1.0 original speed / 5.0 demo peak / 100 stress test to observe Spark micro-batch behavior
"""

import argparse
import errno
import json
import sys
import time


def iter_records(filepath):
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def make_kinesis_sender(stream_name, region, progress_every=100):
    import boto3
    client = boto3.client("kinesis", region_name=region)
    sent = 0

    def send(record):
        nonlocal sent
        client.put_record(
            StreamName=stream_name,
            Data=json.dumps(record, ensure_ascii=False).encode("utf-8"),
            PartitionKey=str(record.get("room_id", "0")),  # same channel goes to the same shard, preserving order
        )
        sent += 1
        if sent % progress_every == 0:
            print(f"[*] Sent {sent} records to Kinesis", file=sys.stderr, flush=True)
    return send


def replay(filepath, speed, loop, sink):
    rounds = 0
    while True:
        prev_ts = None
        count = 0
        for record in iter_records(filepath):
            if prev_ts is not None:
                gap = (record["ts"] - prev_ts) / speed
                if gap > 0:
                    time.sleep(gap)
            prev_ts = record["ts"]
            sink(record)
            count += 1
        rounds += 1
        print(f"\n[*] Finished one replay pass, {count} records total (round {rounds})", file=sys.stderr, flush=True)
        if not loop:
            break


def main():
    ap = argparse.ArgumentParser(description="Replay Twitch chat jsonl to simulate a realtime stream")
    ap.add_argument("file", help="input jsonl file")
    ap.add_argument("--speed", type=float, default=1.0, help="replay speed multiplier")
    ap.add_argument("--loop", action="store_true", help="loop the replay")
    ap.add_argument("--to-kinesis", action="store_true", help="send to Kinesis")
    ap.add_argument("--emit-json", action="store_true", help="output each record as a JSON line to stdout (feed to a realtime consumer)")
    ap.add_argument("--stream", default="twitch-chat-stream", help="Kinesis stream name")
    ap.add_argument("--region", default="ap-northeast-1", help="AWS region (Tokyo)")
    args = ap.parse_args()

    if args.speed <= 0:
        ap.error("--speed must be greater than 0")

    if args.to_kinesis:
        sink = make_kinesis_sender(args.stream, args.region)
        print(f"[*] Replay → Kinesis '{args.stream}' ({args.region}), speed={args.speed}", file=sys.stderr)
    elif args.emit_json:
        def sink(r):
            sys.stdout.write(json.dumps(r, ensure_ascii=False) + "\n")
            sys.stdout.flush()  # flush immediately so downstream receives it in realtime
        print(f"[*] Replay → stdout JSON, speed={args.speed}", file=sys.stderr)
    else:
        def sink(r):
            print(f'[{r["msg_type"]}] {r["display_name"]}: {r["text"]}')
        print(f"[*] Replay → screen, speed={args.speed} (debug)", file=sys.stderr)

    try:
        replay(args.file, args.speed, args.loop, sink)
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except OSError as exc:
            if exc.errno != errno.EPIPE:
                raise
        return


if __name__ == "__main__":
    main()

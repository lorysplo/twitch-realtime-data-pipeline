#!/usr/bin/env python3
"""
make_viewers_demo.py — Generate viewers_demo.jsonl, the replay file for the second stream (viewer counts) on the realtime dashboard.

What it does: pick the viewer-count heartbeats for the specified channels (forsen + lirik by default) out of the raw viewers_*.jsonl,
keep the real counts/games, and rewrite the timestamps into an even alternating cadence (one record every 12 seconds, alternating between the two channels),
so that replay.py plays back at a smooth pace instead of speeding up and slowing down.

Usage:
    python3 make_viewers_demo.py                 # defaults to forsen lirik
    python3 make_viewers_demo.py forsen lirik    # specify channels
    python3 make_viewers_demo.py jynxzi hasanabi # use different channels

Data source: automatically looks for viewers_*.jsonl under the current directory / ./data / ./_inbox/partner-*/data.
Output: viewers_demo.jsonl in the current directory.
Then: python3 replay.py viewers_demo.jsonl --to-kinesis --stream viewer-counts --region ap-northeast-1 --speed 5 --loop
"""
import glob
import json
import os
import sys

GAP = 12.0          # gap (seconds) between adjacent records, even
BASE_TS = 1781200000.0


def find_source_files():
    pats = [
        "viewers_*.jsonl",
        os.path.join("data", "viewers_*.jsonl"),
        os.path.join("_inbox", "partner-*", "data", "viewers_*.jsonl"),
    ]
    files = []
    for p in pats:
        files.extend(glob.glob(p))
    # exclude the output we generate ourselves
    return [f for f in files if os.path.basename(f) != "viewers_demo.jsonl"]


def main():
    channels = sys.argv[1:] or ["forsen", "lirik"]
    files = find_source_files()
    if not files:
        print("✗ No raw viewers_*.jsonl found. Put them in the current directory or under ./data/ and run again.")
        print("  (If you just want to run the demo, the project already ships a ready-made viewers_demo.jsonl you can use directly.)")
        sys.exit(1)

    rows = {ch: [] for ch in channels}
    for f in files:
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("channel") in rows:
                rows[r["channel"]].append(r)

    for ch in channels:
        rows[ch].sort(key=lambda r: r.get("ts", 0))
        if not rows[ch]:
            print(f"⚠ Channel {ch} has no viewer-count records in the raw data, skipping.")

    present = [ch for ch in channels if rows[ch]]
    if not present:
        print("✗ None of the specified channels have viewer-count records in the raw data. Try different channels.")
        sys.exit(1)

    out = []
    i = 0
    for k in range(max(len(rows[ch]) for ch in present)):
        for ch in present:
            if k < len(rows[ch]):
                rec = dict(rows[ch][k])
                rec["ts"] = round(BASE_TS + i * GAP, 3)   # rewrite to an even alternating timestamp
                out.append(rec)
                i += 1

    with open("viewers_demo.jsonl", "w", encoding="utf-8") as o:
        for rec in out:
            o.write(json.dumps(rec, ensure_ascii=False) + "\n")

    for ch in present:
        vs = [r["viewer_count"] for r in rows[ch]]
        print(f"  {ch}: {len(vs)} records, viewers {min(vs)}~{max(vs)}")
    print(f"[✓] Generated viewers_demo.jsonl with {len(out)} records ({'+'.join(present)} evenly alternating)")


if __name__ == "__main__":
    main()

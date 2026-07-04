#!/usr/bin/env python3
"""
build_snapshot_redshift.py — Query reports from the Redshift Gold tables and generate dashboard_snapshot.json (feeds the web dashboard).
QuickSight is too much hassle (subscription + network authorization), so use this free web dashboard instead: query Redshift once, build a snapshot, and push it into Lambda.
Uses the Redshift Data API (boto3 redshift-data) to query the Gold tables.
"""
import json
import os
import time
import boto3

WG, DB, REGION = "twitch-wg", "dev", "ap-northeast-1"
OUT = os.path.join(os.path.dirname(__file__), "dashboard_snapshot.json")
rd = boto3.client("redshift-data", region_name=REGION)


def q(sql):
    qid = rd.execute_statement(WorkgroupName=WG, Database=DB, Sql=sql)["Id"]
    while True:
        d = rd.describe_statement(Id=qid)
        if d["Status"] == "FINISHED":
            break
        if d["Status"] in ("FAILED", "ABORTED"):
            raise RuntimeError(d.get("Error", "")[:300])
        time.sleep(1.2)
    res = rd.get_statement_result(Id=qid)
    cols = [c["name"] for c in res["ColumnMetadata"]]
    rows = []
    for rec in res["Records"]:
        row = {}
        for c, cell in zip(cols, rec):
            if "isNull" in cell:
                row[c] = None
            elif "longValue" in cell:
                row[c] = cell["longValue"]
            elif "doubleValue" in cell:
                row[c] = cell["doubleValue"]
            else:
                row[c] = cell.get("stringValue", "")
        rows.append(row)
    return rows


snap = {}
snap["kpis"] = q("""
  SELECT (SELECT count(*) FROM public.fact_message) AS msgs,
         (SELECT count(*) FROM public.dim_user) AS users,
         (SELECT count(*) FROM public.dim_channel) AS channels,
         (SELECT count(*) FROM public.dim_date) AS days,
         (SELECT count(*) FROM public.fact_event WHERE event_type='raid') AS raids,
         (SELECT coalesce(sum(bits),0) FROM public.fact_message) AS bits
""")[0]
snap["by_channel"] = q("""
  SELECT c.channel_name AS channel, count(*) AS msgs, count(distinct f.user_key) AS dau,
         round(100.0*sum(case when f.is_sub then 1 else 0 end)/count(*),1) AS sub_pct,
         round(avg(f.sentiment_score),3) AS avg_sent
  FROM public.fact_message f JOIN public.dim_channel c ON f.channel_key=c.channel_key
  GROUP BY c.channel_name ORDER BY msgs DESC
""")
snap["daily"] = q("""
  SELECT cast(f.date_key as varchar) AS dt, c.channel_name AS channel,
         count(*) AS msgs, round(avg(f.sentiment_score),3) AS avg_sent
  FROM public.fact_message f JOIN public.dim_channel c ON f.channel_key=c.channel_key
  GROUP BY f.date_key, c.channel_name ORDER BY f.date_key
""")
snap["revenue"] = q("""
  SELECT c.channel_name AS channel,
         sum(case when e.event_type='sub' then 1 else 0 end) AS subs,
         sum(case when e.event_type='resub' then 1 else 0 end) AS resubs,
         sum(case when e.event_type in ('subgift','submysterygift') then 1 else 0 end) AS gifts
  FROM public.fact_event e JOIN public.dim_channel c ON e.channel_key=c.channel_key
  GROUP BY c.channel_name ORDER BY subs DESC, resubs DESC
""")
snap["raids"] = q("""
  SELECT c.channel_name AS channel, e.raid_viewers AS viewers
  FROM public.fact_event e JOIN public.dim_channel c ON e.channel_key=c.channel_key
  WHERE e.event_type='raid' ORDER BY e.raid_viewers DESC
""")
snap["viewers"] = q("""
  SELECT v.channel_name AS channel, max(v.viewer_count) AS peak,
         (SELECT game_name FROM public.fact_viewer v2 WHERE v2.channel_name=v.channel_name
          ORDER BY viewer_count DESC LIMIT 1) AS game
  FROM public.fact_viewer v GROUP BY v.channel_name ORDER BY peak DESC
""")
snap["generated_note"] = "Source: Redshift Serverless warehouse (Gold star-schema tables)"

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(snap, f, ensure_ascii=False, indent=2)
print(f"[✓] Snapshot generated (from Redshift) -> {OUT}")
print(f"    KPI: {snap['kpis']}")
print(f"    channels {len(snap['by_channel'])} · daily {len(snap['daily'])} rows · raids {len(snap['raids'])}")

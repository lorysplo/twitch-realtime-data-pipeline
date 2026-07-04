-- ============================================================================
-- Superset chart SQL — BI layer over the Redshift Gold star schema.
-- Each block = one Superset dataset / chart. These are the exact queries the
-- deployed dashboard uses (see scripts/build_snapshot_redshift.py).
-- Point a Superset "Database" at Redshift Serverless (db `dev`), then create a
-- dataset from each query and the matching chart.
-- ============================================================================

-- [1] KPI tiles: totals across the warehouse
SELECT (SELECT count(*) FROM public.fact_message)                       AS messages,
       (SELECT count(*) FROM public.dim_user)                           AS unique_users,
       (SELECT count(*) FROM public.dim_channel)                        AS channels,
       (SELECT count(*) FROM public.dim_date)                           AS days,
       (SELECT count(*) FROM public.fact_event WHERE event_type='raid') AS raids,
       (SELECT coalesce(sum(bits),0) FROM public.fact_message)          AS cheer_bits;

-- [2] By channel: messages, unique users (DAU), sub %, avg sentiment  (bar + line)
SELECT c.channel_name AS channel,
       count(*)                                                     AS messages,
       count(distinct f.user_key)                                  AS dau,
       round(100.0*sum(case when f.is_sub then 1 else 0 end)/count(*),1) AS sub_pct,
       round(avg(f.sentiment_score),3)                             AS avg_sentiment
FROM public.fact_message f
JOIN public.dim_channel c ON f.channel_key=c.channel_key
GROUP BY c.channel_name
ORDER BY messages DESC;

-- [3] Daily trend: messages + sentiment per day per channel  (stacked bars / lines)
SELECT cast(f.date_key as varchar) AS dt, c.channel_name AS channel,
       count(*)                    AS messages,
       round(avg(f.sentiment_score),3) AS avg_sentiment
FROM public.fact_message f
JOIN public.dim_channel c ON f.channel_key=c.channel_key
GROUP BY f.date_key, c.channel_name
ORDER BY f.date_key;

-- [4] Revenue events: subs / resubs / gifted per channel  (stacked bar)
SELECT c.channel_name AS channel,
       sum(case when e.event_type='sub'   then 1 else 0 end) AS subs,
       sum(case when e.event_type='resub' then 1 else 0 end) AS resubs,
       sum(case when e.event_type in ('subgift','submysterygift') then 1 else 0 end) AS gifted
FROM public.fact_event e
JOIN public.dim_channel c ON e.channel_key=c.channel_key
GROUP BY c.channel_name
ORDER BY subs DESC, resubs DESC;

-- [5] Raid attribution: incoming viewers per raid  (horizontal bar)
SELECT c.channel_name AS channel, e.raid_viewers AS incoming_viewers
FROM public.fact_event e
JOIN public.dim_channel c ON e.channel_key=c.channel_key
WHERE e.event_type='raid'
ORDER BY e.raid_viewers DESC;

-- [6] Peak concurrent viewers per channel (+ top game)  (horizontal bar)
SELECT v.channel_name AS channel,
       max(v.viewer_count) AS peak_viewers,
       (SELECT game_name FROM public.fact_viewer v2
        WHERE v2.channel_name=v.channel_name
        ORDER BY viewer_count DESC LIMIT 1) AS top_game
FROM public.fact_viewer v
GROUP BY v.channel_name
ORDER BY peak_viewers DESC;

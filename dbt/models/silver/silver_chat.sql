-- Silver: cleansing + anonymization + deduplication. Sentiment scores are already computed upstream by Glue Python (sentiment.py) and carried in sentiment_score.
-- event_info must be passed in from Bronze as a string (raw JSON); downstream fact_event reads values with json_extract_scalar.
-- Deduplication: the raw data has a small number of duplicates across files (~0.0% observed locally); deduplicating by business key is a proper responsibility of the Silver layer.
with dedup as (
    select *,
        row_number() over (
            partition by ts, user_id, text, msg_type order by channel
        ) as rn
    from {{ source('bronze', 'chat_scored') }}
    where text is not null
)
select
    ts,
    channel,
    room_id,
    msg_type,
    -- Anonymization: salted SHA256 of user_id, first 12 characters (same salt and algorithm as anonymize.py)
    substring(sha2('twitch-course-2026:' || cast(user_id as varchar), 256), 1, 12) as user_key,
    text,
    emotes,
    is_sub,
    is_mod,
    bits,
    event_info,
    sentiment_score,
    (timestamp 'epoch' + ts * interval '1 second')::date as dt
from dedup
where rn = 1

-- Fact: a chat message (grain = one message)
select
    ts,
    room_id as channel_key,
    user_key,
    dt as date_key,
    bits,
    is_sub,
    is_mod,
    length(text) as msg_len,
    (emotes <> '') as has_emote,
    sentiment_score
from {{ ref('silver_chat') }}
where msg_type in ('chat', 'cheer')

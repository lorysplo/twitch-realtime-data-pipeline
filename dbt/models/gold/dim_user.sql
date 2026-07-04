-- Dimension: user (anonymized). is_sub changes over time, so this simplifies to "ever subscribed"
select
    user_key,
    bool_or(is_sub) as ever_sub,
    min(dt) as first_seen
from {{ ref('silver_chat') }}
group by user_key

-- Dimension: channel
select distinct
    room_id as channel_key,
    channel as channel_name
from {{ ref('silver_chat') }}
where room_id > 0

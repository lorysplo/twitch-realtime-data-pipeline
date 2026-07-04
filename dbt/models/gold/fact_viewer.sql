-- Fact: a viewer-count heartbeat (grain = channel x minute, periodic snapshot fact)
select
    ts,
    channel as channel_name,
    dt as date_key,
    game as game_name,
    viewer_count
from {{ ref('silver_viewers') }}

-- Silver: viewer-count heartbeat, cleansing + adding a date column
select
    ts,
    channel,
    viewer_count,
    game,
    title,
    started_at,
    (timestamp 'epoch' + ts * interval '1 second')::date as dt
from {{ source('bronze', 'viewers') }}
where viewer_count is not null

-- Dimension: game category (from viewer-count data)
select distinct
    game as game_name
from {{ ref('silver_viewers') }}
where game <> ''

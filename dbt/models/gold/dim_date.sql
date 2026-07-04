-- Dimension: date
select distinct
    dt as date_key,
    extract(dow from dt) as dow,
    extract(year from dt) as yr,
    extract(month from dt) as mon
from {{ ref('silver_chat') }}

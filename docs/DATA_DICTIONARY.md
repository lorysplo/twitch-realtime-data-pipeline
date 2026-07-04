# Data Dictionary

Column-level reference for the warehouse. Built by dbt (`dbt/models/`). Layers: **Silver** (cleaned)
→ **Gold** (star schema). `ts` is epoch seconds; `dt`/`*_date`/`date_key` are dates.

## Silver

### `silver_chat` — cleaned, de-duplicated, anonymized chat
| Column | Type | Notes |
|---|---|---|
| `ts` | double | event time (epoch seconds) |
| `channel` | varchar | channel handle (e.g. `forsen`) |
| `room_id` | bigint | Twitch numeric channel id |
| `msg_type` | varchar | `chat` / `cheer` / `raid` / `sub` / `resub` / … |
| `user_key` | varchar(12) | **anonymized** user id = first 12 chars of `sha256('twitch-course-2026:' + user_id)` |
| `text` | varchar | message text |
| `emotes` | varchar | Twitch emote position string |
| `is_sub` / `is_mod` | boolean | flags on the message |
| `bits` | int | cheer bits on the message |
| `event_info` | varchar | raw event payload **stored as a JSON string** (keeps keys like `viewerCount`) |
| `sentiment_score` | double | VADER + emote score, −1…+1 |
| `dt` | date | derived from `ts` |

### `silver_viewers` — cleaned viewer-count heartbeats
| Column | Type | Notes |
|---|---|---|
| `ts` | double | sample time |
| `channel` | varchar | channel handle |
| `viewer_count` | int | concurrent viewers at `ts` |
| `game` | varchar | category being streamed |
| `title` | varchar | stream title |
| `started_at` | varchar | stream start timestamp |
| `dt` | date | derived from `ts` |

## Gold — dimensions

| Table | Key | Other columns |
|---|---|---|
| `dim_channel` | `channel_key` (= room_id) | `channel_name` |
| `dim_user` | `user_key` | `ever_sub` (bool — ever subscribed), `first_seen` (date) |
| `dim_date` | `date_key` (date) | `dow` (day of week), `yr`, `mon` |
| `dim_game` | `game_name` | — |

## Gold — facts

### `fact_message` — grain: **one chat / cheer message**
| Column | Notes |
|---|---|
| `ts` | event time |
| `channel_key` → `dim_channel` | FK |
| `user_key` → `dim_user` | FK |
| `date_key` → `dim_date` | FK |
| `bits` | cheer bits |
| `is_sub` / `is_mod` | flags |
| `msg_len` | message length |
| `has_emote` | message contained an emote |
| `sentiment_score` | −1…+1 |

### `fact_event` — grain: **one discrete event** (raid / sub / resub / …)
| Column | Notes |
|---|---|
| `ts`, `channel_key`, `user_key`, `date_key` | FKs as above |
| `event_type` | `raid` / `sub` / `resub` / `subgift` / … |
| `raid_viewers` | incoming viewers on a raid (`json_extract_path_text` of `event_info`) |

### `fact_viewer` — grain: **one viewer-count sample**
| Column | Notes |
|---|---|
| `ts` | sample time |
| `channel_name` | channel |
| `date_key` → `dim_date` | FK |
| `game_name` | category |
| `viewer_count` | concurrent viewers |

> Note: `fact_viewer` has **no `user_key`** — a viewer-count sample is not a single user's action.
> This is the clearest signal that the fact split is driven by what each measurement actually contains.

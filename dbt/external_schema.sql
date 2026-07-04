-- Redshift Spectrum external schema.
-- Lets Redshift query the Parquet that the Glue crawler cataloged in S3, without loading it.
-- The dbt sources (models/sources.yml) read from this `bronze` schema.

CREATE EXTERNAL SCHEMA IF NOT EXISTS bronze
FROM DATA CATALOG
DATABASE 'twitch'
IAM_ROLE 'arn:aws:iam::<ACCOUNT_ID>:role/twitch-redshift-role';

-- sanity check after the crawler has run:
-- SELECT count(*) FROM bronze.chat_scored;   -- ~287,728

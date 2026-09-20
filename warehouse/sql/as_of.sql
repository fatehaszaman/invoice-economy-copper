-- Shared by the research store and read-only audit CLI.
-- :cid = NULL means all channels, not only the aggregate/null channel.
WITH availability AS (
    SELECT rowid AS ingestion_order, *,
           CASE WHEN source_url LIKE '%comtradeapi.un.org/%'
                      OR quality_flags LIKE '%publication_time_unknown%'
                      OR quality_flags LIKE '%comtrade_free_tier%'
                THEN MAX(publication_ts, retrieval_ts)
                ELSE publication_ts END AS available_ts
      FROM observations
     WHERE canonical_series_id = :sid
       AND (:cid IS NULL OR channel_id = :cid)
), ranked AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY observation_ts, channel_id
        ORDER BY available_ts DESC, publication_ts DESC,
                 revision_number DESC, ingestion_order DESC
    ) AS rank
      FROM availability
     WHERE available_ts <= :asof
)
SELECT observation_ts, canonical_value, publication_ts,
       revision_number, unit, license_class, available_ts,
       retrieval_ts, quality_flags
  FROM ranked WHERE rank = 1
 ORDER BY observation_ts

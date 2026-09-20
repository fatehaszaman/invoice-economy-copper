-- Full acquisition history, not an as-of result or authenticated release history.
-- Preserve channels: comparing revisions across channels would be meaningless.
WITH ordered AS (
    SELECT canonical_series_id, channel_id, observation_ts, vintage_id,
           publication_ts, retrieval_ts, revision_number, canonical_value,
           LAG(canonical_value) OVER (
               PARTITION BY canonical_series_id, channel_id, observation_ts
               ORDER BY publication_ts, retrieval_ts, revision_number, rowid
           ) AS previous_value
      FROM observations
     WHERE canonical_series_id = :sid
)
SELECT *, canonical_value - previous_value AS revision_delta
  FROM ordered
 ORDER BY observation_ts, channel_id, publication_ts, retrieval_ts, revision_number

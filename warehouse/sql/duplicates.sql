-- SQLite's nullable composite primary key does not reject every duplicate.
-- GROUP BY groups NULL channels together, exposing bypasses of PITStore.append.
SELECT canonical_series_id, channel_id, observation_ts, vintage_id,
       COUNT(*) AS duplicate_count
  FROM observations
 GROUP BY canonical_series_id, channel_id, observation_ts, vintage_id
HAVING COUNT(*) > 1
 ORDER BY canonical_series_id, observation_ts, vintage_id

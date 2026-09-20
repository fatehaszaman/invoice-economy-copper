-- Acquisition inventory, NOT historical as-of coverage.
SELECT source, canonical_series_id, frequency, unit, license_class,
       COUNT(*) AS vintage_rows,
       COUNT(DISTINCT observation_ts) AS reference_dates,
       COUNT(DISTINCT payload_hash) AS payloads,
       SUM(CASE WHEN canonical_value IS NULL THEN 1 ELSE 0 END) AS null_values,
       MIN(observation_ts) AS first_reference_date,
       MAX(observation_ts) AS last_reference_date
  FROM observations
 GROUP BY source, canonical_series_id, frequency, unit, license_class
 ORDER BY source, canonical_series_id, frequency, unit, license_class

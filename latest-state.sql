WITH ranked AS (
  SELECT source, trade_id, version, status, notional_minor, currency,
         ROW_NUMBER() OVER (
           PARTITION BY source, trade_id
           ORDER BY version DESC
         ) AS position
  FROM canonical_events
  WHERE NOT EXISTS (
    SELECT 1 FROM quarantined_trades q
    WHERE q.source = canonical_events.source
      AND q.trade_id = canonical_events.trade_id
  )
)
SELECT source, trade_id, version, status, notional_minor, currency
FROM ranked WHERE position = 1
ORDER BY source, trade_id
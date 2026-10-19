"""Trade State Lab: synthetic, deterministic context preparation for AI.

Python 3.10+; standard library only. USD/EUR minor units have two decimals.
This is an educational model, not a regulatory-reporting implementation.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

LATEST_SQL = """WITH ranked AS (
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
ORDER BY source, trade_id"""

def validate(event):
    for name in ('source', 'trade_id'):
        if not isinstance(event.get(name), str) or not event[name].strip():
            raise ValueError(f'{name} must be a nonempty string')
    for name in ('version', 'arrival_seq'):
        if type(event.get(name)) is not int or event[name] < 1:
            raise ValueError(f'{name} must be a positive integer')
    if event.get('status') not in ('ACTIVE', 'CANCELLED'):
        raise ValueError('unsupported status')
    if type(event.get('notional_minor')) is not int or event['notional_minor'] < 0:
        raise ValueError('notional_minor must be a nonnegative integer')
    if event.get('currency') not in ('USD', 'EUR'):
        raise ValueError('this example supports only USD and EUR')

def reconstruct(events):
    """Resolve a whole input snapshot, retaining conflicts for inspection.

    Key policy: (source, trade_id, version) identifies one business event.
    Identical payloads for that key are replays; differing payloads cause
    conservative quarantine of the entire source/trade until reviewed.
    arrival_seq is ingestion metadata, not business precedence or a tie-break.
    """
    grouped = defaultdict(set)
    for event in events:
        validate(event)
        key = event['source'], event['trade_id'], event['version']
        grouped[key].add((event['status'], event['notional_minor'], event['currency']))
    conflicts = sorted(key for key, values in grouped.items() if len(values) > 1)
    quarantined = sorted({(key[0], key[1]) for key in conflicts})
    canonical = []
    for (source, trade_id, version), values in sorted(grouped.items()):
        if len(values) == 1:
            status, amount, currency = next(iter(values))
            canonical.append((source, trade_id, version, status, amount, currency))
    columns = ('source', 'trade_id', 'version', 'status', 'notional_minor', 'currency')
    with sqlite3.connect(':memory:') as connection:
        connection.execute('CREATE TABLE canonical_events(source TEXT, trade_id TEXT, version INTEGER, status TEXT, notional_minor INTEGER, currency TEXT, PRIMARY KEY(source,trade_id,version))')
        connection.execute('CREATE TABLE quarantined_trades(source TEXT, trade_id TEXT, PRIMARY KEY(source,trade_id))')
        connection.executemany('INSERT INTO canonical_events VALUES (?,?,?,?,?,?)', canonical)
        connection.executemany('INSERT INTO quarantined_trades VALUES (?,?)', quarantined)
        latest = [dict(zip(columns, row)) for row in connection.execute(LATEST_SQL)]
    return {
        'latest': latest,
        'active': [row for row in latest if row['status'] == 'ACTIVE'],
        'quarantined': [dict(source=source, trade_id=trade_id) for source, trade_id in quarantined],
        'conflicting_keys': [dict(source=k[0], trade_id=k[1], version=k[2]) for k in conflicts],
        'input_records': len(events),
        'distinct_event_keys': len(grouped),
        'replay_records': len(events) - sum(len(values) for values in grouped.values())
    }

def context_packet(state, source, trade_id):
    """Return deterministic evidence, not a generated model answer."""
    if {'source': source, 'trade_id': trade_id} in state['quarantined']:
        return {'source': source, 'trade_id': trade_id, 'serving_eligible': False,
                'reason': 'Conflicting business-version payloads require review.', 'evidence': None}
    event = next((e for e in state['latest'] if e['source'] == source and e['trade_id'] == trade_id), None)
    if event is None:
        return {'source': source, 'trade_id': trade_id, 'serving_eligible': False,
                'reason': 'No validated event exists in this snapshot.', 'evidence': None}
    return {'source': source, 'trade_id': trade_id, 'serving_eligible': True,
            'reason': 'Validated latest state; a cancellation must not be described as active.',
            'evidence': event.copy()}

def naive_active(events):
    """Deliberately faulty: filters cancellations before picking last arrival."""
    latest = {}
    for event in sorted(events, key=lambda e: e['arrival_seq']):
        if event['status'] == 'ACTIVE':
            latest[event['source'], event['trade_id']] = event
    return list(latest.values())

if __name__ == '__main__':
    fixtures = json.loads((Path(__file__).parent / 'fixtures.json').read_text())
    for case in fixtures:
        state = reconstruct(case['events'])
        print(case['title'])
        print(json.dumps(state, indent=2))
        print(json.dumps(context_packet(state, 'SIM', 'T1'), indent=2))

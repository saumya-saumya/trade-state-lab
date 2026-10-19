import copy
import itertools
import json
import unittest
from pathlib import Path
from trade_state import reconstruct, context_packet, naive_active

CASES = json.loads((Path(__file__).parent/'fixtures.json').read_text())

class TradeStateTests(unittest.TestCase):
    def case(self, name):
        return copy.deepcopy(next(c['events'] for c in CASES if c['id'] == name))

    def test_late_old_version_cannot_replace_newer_version(self):
        result = reconstruct(self.case('late-arrival'))
        self.assertEqual([(r['version'],r['notional_minor']) for r in result['active']],[(2,12000)])

    def test_naive_query_exposes_late_arrival_failure(self):
        self.assertEqual(naive_active(self.case('late-arrival'))[0]['notional_minor'],10000)

    def test_cancellation_removes_active_state(self):
        state = reconstruct(self.case('cancellation'))
        self.assertEqual(state['active'],[])
        self.assertEqual(state['latest'][0]['status'],'CANCELLED')

    def test_naive_filter_resurrects_cancelled_trade(self):
        self.assertEqual(len(naive_active(self.case('cancellation'))),1)

    def test_exact_replay_does_not_change_state(self):
        rows = self.case('replay')
        self.assertEqual(reconstruct(rows)['latest'],reconstruct(rows+rows)['latest'])
        self.assertEqual(reconstruct(rows)['active'],reconstruct(rows+rows)['active'])

    def test_replay_is_observable(self):
        self.assertEqual(reconstruct(self.case('replay'))['replay_records'],1)

    def test_input_order_does_not_change_business_state(self):
        for case in CASES:
            expected = reconstruct(case['events'])
            for order in itertools.permutations(case['events']):
                self.assertEqual(reconstruct(list(order)),expected)

    def test_conflict_quarantines_entire_trade(self):
        state = reconstruct(self.case('conflict'))
        self.assertEqual(state['active'],[])
        self.assertEqual(state['quarantined'],[{'source':'SIM','trade_id':'T1'}])

    def test_conflict_cannot_be_served_as_ai_evidence(self):
        packet = context_packet(reconstruct(self.case('conflict')),'SIM','T1')
        self.assertFalse(packet['serving_eligible'])
        self.assertIsNone(packet['evidence'])

    def test_missing_trade_has_no_invented_evidence(self):
        packet = context_packet(reconstruct([]),'SIM','MISSING')
        self.assertFalse(packet['serving_eligible'])
        self.assertIsNone(packet['evidence'])

    def test_cancellation_is_explicit_in_ai_packet(self):
        packet = context_packet(reconstruct(self.case('cancellation')),'SIM','T1')
        self.assertEqual(packet['evidence']['status'],'CANCELLED')

    def test_source_namespaces_do_not_collide(self):
        rows = self.case('late-arrival')[:2]
        other = copy.deepcopy(rows[0]);other['source']='OTHER';other['notional_minor']=30000
        self.assertEqual(len(reconstruct(rows+[other])['active']),2)

    def test_currencies_remain_separate(self):
        state = reconstruct(self.case('replay'))
        self.assertEqual([(r['currency'],r['notional_minor']) for r in state['active']],[('USD',10000),('EUR',5000)])

    def test_conflict_in_old_history_is_also_blocked_by_policy(self):
        rows = self.case('conflict')
        newer = copy.deepcopy(rows[0]);newer['version']=2;newer['arrival_seq']=3
        self.assertEqual(reconstruct(rows+[newer])['latest'],[])

    def test_invalid_version_is_rejected(self):
        for invalid in (0,-1,True,'2',2.5):
            rows=self.case('late-arrival');rows[0]['version']=invalid
            with self.assertRaises(ValueError):reconstruct(rows)

    def test_fractional_or_negative_minor_units_are_rejected(self):
        for invalid in (-1,1.5,True,'100'):
            rows=self.case('late-arrival');rows[0]['notional_minor']=invalid
            with self.assertRaises(ValueError):reconstruct(rows)

    def test_unsupported_status_and_currency_are_rejected(self):
        for field,value in (('status','UNKNOWN'),('currency','JPY')):
            rows=self.case('late-arrival');rows[0][field]=value
            with self.assertRaises(ValueError):reconstruct(rows)

    def test_empty_snapshot_is_valid_but_contains_no_evidence(self):
        state=reconstruct([])
        self.assertEqual(state['latest'],[])
        self.assertEqual(state['input_records'],0)

if __name__=='__main__':unittest.main()

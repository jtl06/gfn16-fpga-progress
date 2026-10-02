"""Scheduling-model invariants only; no RTL correctness/throughput claim."""
import unittest
from reference.candidate_overlap_model import schedule


class CandidateOverlapTests(unittest.TestCase):
    def test_one_context_is_serial(self):
        for banks in (1,2,4):
            r=schedule(7,31,5,11,1,banks,9)
            self.assertEqual(r['elapsed_cycles'],54*9)
            self.assertEqual(r['finite_run_cycle_speedup'],1)

    def test_engine_exclusion_and_candidate_dependencies(self):
        for contexts in (1,2,3,4):
            for banks in (1,2,3):
                r=schedule(7,31,5,11,contexts,banks,20)
                for field in ('stage','context'):
                    values={x[field] for x in r['trace']}
                    for value in values:
                        rows=sorted((x for x in r['trace'] if x[field]==value),key=lambda x:x['start'])
                        for first,second in zip(rows,rows[1:]):
                            self.assertLessEqual(first['end'],second['start'])
                self.assertGreaterEqual(r['average_cycles_per_square'],r['resource_interval_lower_bound'])

    def test_data_bank_not_reused_before_crt_finishes(self):
        r=schedule(7,31,5,11,4,2,30)
        leases={}
        for x in r['trace']:
            key=(x['context'],x['round'])
            if x['stage']=='convert':leases[key]=[x['bank'],x['start'],None]
            if x['stage']=='post':leases[key][2]=x['start']+5
        for bank in range(2):
            rows=sorted(x for x in leases.values() if x[0]==bank)
            for first,second in zip(rows,rows[1:]):self.assertLessEqual(first[2],second[1])

    def test_more_buffers_dont_magically_add_ntt_engines(self):
        r=schedule(7,31,5,11,4,2,100)
        self.assertEqual(r['resource_interval_lower_bound'],31)
        self.assertGreaterEqual(r['average_cycles_per_square'],31)
        self.assertLess(r['average_cycles_per_square'],32)

    def test_invalid_inputs(self):
        for value in (0,-1,True,1.5):
            with self.assertRaises(ValueError):schedule(value,31,5,11,2,2)

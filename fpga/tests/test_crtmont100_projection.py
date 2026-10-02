"""Existing-evidence projection and native text parser tests; no HDL run."""
import unittest
from unittest.mock import patch
from fpga.synthesis import crtmont100_projection as p
from fpga.synthesis import audit_crtmont100_offline as audit


def detail(expanded=False):
    ic=0 if expanded else 3.516
    return ('; From Node ; source ;\n; To Node ; target ;\n; Statistics ;\n'
        '; Property ; Value ; Count ; Total Delay ; % of Total ; Min ; Max ;\n'
        '; Data Delay ; 9.554 ; ; ; ; ; ;\n; Data ; ; ; ; ; ; ;\n'
        f'; IC ; ; 7 ; {ic} ; 37 ; 0 ; 1.628 ;\n'
        '; Cell ; ; 14 ; 5.770 ; 60 ; 0 ; 3.866 ;\n; uTco ; ; 1 ; .268 ; 3 ; .268 ; .268 ;\n'+
        ('; Routing Element ; ; 39 ; 3.516 ; 37 ; 0 ; .539 ;\n' if expanded else '')+
        '; Required Path ; ; ; ; ; ; ;\n; Clock ; ; ; ; ; ; ;\n; IC ; ; 3 ; 9 ; 90 ; 0 ; 9 ;\n')


class ProjectionTests(unittest.TestCase):
    def test_exact_integer_source_bound_formula(self):
        result=p.estimate();self.assertEqual(result['exponent_bits'],1911814)
        self.assertEqual(result['cached_chain_total_cycles'],41663+(1911814-1)*32920)
        self.assertEqual(result['clock_hz'],100000000)
        self.assertEqual((result['cold_cycles_sample_max'],result['warm_cycles_sample_max']),(41663,32920))
        self.assertEqual(len(result['source_sha256']),16)

    def test_required_clock_and_native_cycle_pins(self):
        for name in (p.AUDIT+'independent-review-v1.json',p.AUDIT+'receipt.json',p.NATIVE,p.NATIVE_REVIEW):
            bad=dict(p.PINS);bad[name]='0'*64
            with patch.object(p,'PINS',bad),self.assertRaisesRegex(ValueError,'input drift'):p.estimate()

    def test_no_t5_or_borrowed_clock_claim(self):
        result=p.estimate();self.assertIn('not_full_prp',result['status'])
        self.assertEqual((result['cold_sample_count'],result['warm_sample_count']),(1,4))
        self.assertEqual(result['samples'][0]['conversion'],4102)
        self.assertTrue(any('No unaudited T5' in value for value in result['limitations']))
        self.assertTrue(any('Do not borrow' in value for value in result['limitations']))

    def test_routing_expansion_counts_data_not_clock(self):
        path=dict(from_node='source',to_node='target',data_delay_ns=9.554)
        for expanded in (False,True):
            result=audit.detail_statistics(detail(expanded),path)
            self.assertEqual(result['data_interconnect_ns'],3.516)
            self.assertEqual(result['data_cell_ns'],5.770)
        with self.assertRaises(ValueError):audit.detail_statistics(detail(True).replace('3.516 ; 37','3.517 ; 37').replace('5.770','7.770'),path)
        with self.assertRaises(ValueError):audit.detail_statistics(detail(True).replace('source','wrong-source'),path)

    def test_existing_archive_full_replay_and_pinned_tamper(self):
        result=audit.verify();self.assertEqual(result['verified_report_artifacts'],172)
        self.assertEqual(result['refined_selected100']['RAM_to_CRT_selected_observations'],0)
        self.assertEqual(result['refined_selected100']['structural_groups'][0]['observations'],937)
        with patch.object(audit,'RECEIPT_SHA','0'*64),self.assertRaisesRegex(ValueError,'pinned'):audit.verify()


if __name__=='__main__':unittest.main()

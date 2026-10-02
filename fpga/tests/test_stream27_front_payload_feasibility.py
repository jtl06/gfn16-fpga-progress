"""Scalar/source checks only; deliberately establishes the no-drop-in fault seam."""
import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).resolve().parents[1]/'reference/stream27_front_payload_feasibility.py'
spec=importlib.util.spec_from_file_location('front_feasibility',PATH)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class FrontTests(unittest.TestCase):
    def test_all_prime_source_edges_numeric_rejected_and_hold(self):
        result=m.checks()
        self.assertEqual(result['events'],3072)
        self.assertGreater(result['valid_numeric_outputs'],26000)
        self.assertGreater(result['rejected_lane_tokens'],7000)
        self.assertGreater(result['model_eligible_normal_edges'],200)

    def test_digit_D3_rejected_origin_and_hold(self):
        for p in m.PRIMES:
            d=m.Digit(p,38);shared=m.Owner(38)
            corpus=[(True,0xffffffff,0x1234567),(True,0xfffffffe,0x2222222)]+[(False,0,0)]*6
            outputs=[]
            for valid,word,tag in corpus:
                outputs.append(d.step(valid,word,tag));occupied,owner=shared.step(valid,tag)
                self.assertEqual(outputs[-1][3],owner)
                self.assertEqual(bool(outputs[-1][0] or outputs[-1][1]),bool(occupied))
            self.assertEqual(outputs[3],(1,0,p-1,0x1234567))
            self.assertEqual(outputs[4],(0,1,p-1,0x2222222))
            self.assertEqual(outputs[-1],(0,0,p-1,0x2222222))

    def test_boundary_D5_frozen_snapshot_tail_after_quarantine(self):
        for p in m.PRIMES:
            b=m.Boundary(p)
            output=[]
            for edge in range(8):
                output.append(b.step(edge<3,-1 if edge==0 else -2147483648,
                    604832956 if edge==0 else 2,False,0x3456 if edge==0 else 0x777,
                    quarantine=edge>0))
            self.assertEqual(output[5],(1,0,p-1,0x3456))
            self.assertEqual(output[-1],(0,0,p-1,0x3456))

    def test_reset_flushes_dirty_payload_and_first_postreset(self):
        for latency in (3,5):
            s=m.Owner(38,latency);s.step(True,7)
            s.step(False,0,reset=True)
            for _ in range(latency+2):self.assertEqual(s.step(False,0),(0,0))
            out=[s.step(True,9)]+[s.step(False,0) for _ in range(latency)]
            self.assertEqual(out[-1],(1,9))

    def test_per_lane_valid_error_authority_must_not_be_shared(self):
        self.assertEqual(m.join([(1,0,1,5),(0,0,0,5)]),(False,True))
        self.assertEqual(m.join([(1,0,1,5),(0,1,0,5)]),(False,True))
        self.assertEqual(m.join([(0,1,0,5),(0,1,0,5)]),(False,True))

    def test_shared_tag_register_corruption_breaks_existing_fault_guard(self):
        for width in (27,38):
            c=m.corruption_counterexample(width)
            self.assertTrue(c['isolated_old_lane_tag_pending'])
            self.assertFalse(c['shared_tag_corruption_pending_without_independent_origin'])
            self.assertNotEqual(c['old_expected_owner'],c['actual_shared_corrupted_owner'])
        # A parity-only proposed witness does not close arbitrary word faults.
        self.assertEqual((5).bit_count()%2,(5^3).bit_count()%2)

    def test_frozen_timing58_storage2_source_seam(self):
        self.assertEqual(m.locked_sources()['bundle_sha256'],m.BUNDLE_PIN)
        c=m.storage_compatibility()
        self.assertEqual(c['unchanged_front_regions'],3)
        self.assertTrue(c['unchanged_geometry'])
        self.assertTrue(c['unchanged_leaf_bodies'])


if __name__=='__main__':unittest.main()

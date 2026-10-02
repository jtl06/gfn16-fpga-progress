"""Exact9.6 clock/profile/projection guards; no native or cloud execution."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from fpga.synthesis import crtmont96_projection as p
from fpga.synthesis import crtmont100_projection as frozen

ROOT=Path(__file__).resolve().parents[1]


class Exact96ProjectionTests(unittest.TestCase):
    def test_exact_period_rational_G4_cycles_and_archived_output(self):
        result=p.estimate()
        self.assertEqual(result['clock_period_ns_exact'],dict(numerator=48,denominator=5))
        self.assertEqual(result['clock_hz_exact'],dict(numerator=312500000,denominator=3))
        self.assertEqual(result['cached_chain_total_cycles'],41663+(1911814-1)*32920)
        self.assertEqual(result['projected_compute_seconds_exact'],
                         dict(numerator=188810776869,denominator=312500000))
        exact=Fraction(result['cached_chain_total_cycles']*48,5_000_000_000)
        self.assertEqual(result['projected_compute_seconds'],float(exact))
        self.assertEqual(result['duration_ratio_vs_audited100'],.96)
        self.assertEqual(result['warm_cycles_sample_max'],32920)
        self.assertEqual(len(result['source_sha256']),16)
        archive=json.loads((ROOT/p.BASE/'crtmont96-compute-projection-v1.json').read_text())
        self.assertEqual(result,archive)

    def test_frozen100_source_and_output_stay_unchanged(self):
        previous=frozen.estimate()
        self.assertEqual(previous['clock_hz'],100000000)
        self.assertEqual(previous['projected_compute_seconds'],629.36925623)
        for name in ('synthesis/crtmont100_projection.py','synthesis/audit_crtmont96_offline.py',
                     p.AUDIT+'receipt.json',p.AUDIT+'independent-review-v1.json'):
            changed=dict(p.PINS);changed[name]='0'*64
            with patch.object(p,'PINS',changed),self.assertRaisesRegex(ValueError,'input drift'):
                p.estimate()

    def test_semantic_gate_rejects_borrowed_unreviewed_negative_or_partial_clock(self):
        review_path=ROOT/p.AUDIT/'independent-review-v1.json'
        original=json.loads(review_path.read_text())
        changes=[]
        for key,value in (('measured_constraint_period_ns',9.5),('constraint_frequency_mhz',105.21)):
            r=copy.deepcopy(original);r['clock'][key]=value;changes.append(r)
        r=copy.deepcopy(original);r['status']='native_pending';changes.append(r)
        r=copy.deepcopy(original);r['source_sha256']['wrong.sv']='0'*64;changes.append(r)
        corner=next(iter(original['corners']))
        for kind in ('setup','hold','mpw'):
            r=copy.deepcopy(original);r['corners'][corner][kind]['slack_ns']=-.001;changes.append(r)
            r=copy.deepcopy(original);r['corners'][corner][kind]['failing_endpoints']=1;changes.append(r)
        r=copy.deepcopy(original);del r['corners'][corner];changes.append(r)
        read_text=Path.read_text
        for changed in changes:
            def reader(path,*args,**kwargs):
                return json.dumps(changed) if path==review_path else read_text(path,*args,**kwargs)
            with patch.object(Path,'read_text',reader),self.assertRaises(ValueError):
                p.estimate()

    def test_T5_cycles_cannot_use_G4_clock(self):
        prior=frozen.estimate()
        altered=dict(prior,warm_cycles_sample_max=28823)
        with patch('fpga.synthesis.crtmont100_projection.estimate',return_value=altered),\
             self.assertRaisesRegex(ValueError,'no T5 borrowing'):
            p.estimate()


if __name__=='__main__':
    unittest.main()

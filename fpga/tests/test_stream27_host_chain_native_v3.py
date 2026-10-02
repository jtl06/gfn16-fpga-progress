import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import stream27_host_chain_native_v2 as old
from fpga.reference import stream27_host_chain_native_v3 as current
from fpga.reference.stream27_host_chain_param_v1 import prepare as shared
from fpga.reference.stream27_host_chain_v1 import prepare as frozen


class NativeSourceDelta(unittest.TestCase):
    def test_diagnostic_only_preserves_every_rtl_asset_and_contract(self):
        with tempfile.TemporaryDirectory(prefix='s4-long-source-') as root:
            a=Path(root)/'old';b=Path(root)/'new';old.prepare(a,n=32);current.prepare(b,n=32)
            ma=json.loads((a/'manifest.json').read_text());mb=json.loads((b/'manifest.json').read_text())
            self.assertEqual(ma['steps'],mb['steps']);self.assertEqual(ma['build'],mb['build'])
            self.assertEqual(ma['build']['parameters'],dict(AW=5,P=16,CONTEXTS=1,EPOCH_SEED=65534))
            for name,pin in ma['sources'].items():
                if name!='rtl/tb/stream27_host_chain_v1.cpp':self.assertEqual(mb['sources'][name],pin,name)
            source=b/'inputs/fpga';cpp=(source/'rtl/tb/stream27_host_chain_v1.cpp').read_text()
            self.assertIn('d.operations_started==0 || d.completed_squares<=count',cpp)
            self.assertIn('d.warm_count=type==2?3:2',cpp)
            self.assertIn('d.operations_started==count&&d.completed_squares==count',cpp)
            self.assertIn('c.pops',cpp)
            self.assertEqual(json.loads((b/'preparation.json').read_text())['long_counts']['operations'],1212)

    def test_full_width_ordinal_role_is_not_arithmetic_prp(self):
        with tempfile.TemporaryDirectory(prefix='s4-long-source-') as root:
            out=Path(root)/'ordinal';r=current.prepare(out,n=32,ordinal=True)
            m=json.loads((out/'manifest.json').read_text())
            self.assertEqual(len(m['steps']),1);self.assertEqual(m['steps'][0]['argv'],['{exe}','--ordinal'])
            self.assertIn('65540',m['steps'][0]['expected_stdout']);self.assertIn('control witness',r['ordinal_scope'])

    def test_shared_p16_returns_exact_frozen_rtl(self):
        for n in (32,256):
            for paired in (False,True):
                self.assertEqual(shared(n,paired=paired)['generated_sha256'],frozen(n,paired=paired)['generated_sha256'])


if __name__=='__main__':unittest.main()

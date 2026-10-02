"""Exact finite source/contract checks; no native or HDL execution."""
import tempfile
from pathlib import Path
import unittest

from fpga.reference import stream27_canonical_image_native_v1 as native
from fpga.reference import stream27_canonical_image_prepare_v1 as prep


class NativePreparation(unittest.TestCase):
    def test_actual_sources_pinned(self):self.assertEqual(native.verify(),native.PINS)

    def test_minimal_compiled_closure_and_two_typed_steps(self):
        for aw in (5,8):
            for p in (8,16):
                m,files=prep.role(aw,p)
                self.assertEqual(m['build']['sv_sources'],[native.RAM,native.SV])
                self.assertEqual(m['build']['parameters'],dict(AW=aw,P=p))
                self.assertTrue(set(m['build']['sv_sources']+[m['build']['cpp_source']])<=files.keys())
                self.assertEqual(len(files),8)
                self.assertEqual([step['expected_returncode'] for step in m['steps']],[0,1])
                for step in m['steps']:self.assertEqual(step['validator']['assets'],{})
                self.assertIn('not per square',m['canonical_image']['ledger']['barrier_usage'])

    def test_exact_footer_counts(self):
        wanted={(5,8):(175,3618,109,4,21824),(5,16):(173,3586,108,4,21632),
                (8,8):(175,28930,109,4,174592),(8,16):(175,28930,109,4,174592)}
        for key,counts in wanted.items():self.assertEqual(tuple(native.contracts(*key)['counts'].values()),counts)

    def test_typed_outputs_and_counter_mutants(self):
        for aw,p in ((5,8),(5,16),(8,8),(8,16)):
            for negative in (False,True):
                c=native.contracts(aw,p)['negative' if negative else 'normal']
                config=dict(aw=aw,p=p,negative=negative)
                self.assertEqual(native.validate(c['stdout'],c['stderr'],c['returncode'],config,{})['status'],'PASS_expected_contracts')
                bad=c['stdout'].replace('cycles=','cycles=1') if not negative else c['stdout']+'PASS\n'
                with self.assertRaisesRegex(ValueError,'TYPED_OUTPUT'):native.validate(bad,c['stderr'],c['returncode'],config,{})
                with self.assertRaisesRegex(ValueError,'TYPED_OUTPUT'):native.validate(c['stdout'],c['stderr'],1-c['returncode'],config,{})

    def test_unsupported_full_size_and_fields_rejected(self):
        for aw,p in ((16,8),(4,8),(5,4),(5.0,8),(5,8.0)):
            with self.assertRaisesRegex(ValueError,'SMALL_GEOMETRY'):native.contracts(aw,p)

    def test_source_drift_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in native.PINS:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((native.ROOT/name).read_bytes())
            native.verify(root)
            target=root/native.SV;target.write_bytes(target.read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError,'SOURCE_DRIFT'):native.verify(root)


if __name__=='__main__':unittest.main()

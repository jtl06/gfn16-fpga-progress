"""Pure symbolic/source/config checks; never run HDL or vendor tools."""
import json
from pathlib import Path
import tempfile
import unittest

from fpga.reference import radix22_selector_experiment_v1 as probe


class SelectorExperiment(unittest.TestCase):
    def test_data_read_write_matches_frozen_physical_issue(self):
        for high in range(1,16,2):
            for number in (0,1,127,128,511):
                b=probe.local.frozen.paired_issue(65536,64,high,number)
                bank=probe.local.frozen.physical.bank_of(b.base,7)
                orientation=(((bank>>(high%7))&1)<<1)|((bank>>((high-1)%7))&1)
                read,write=probe.data_maps(2,high%7,orientation)
                expected=[probe.local.frozen.physical.bank_of(a,7) for a in b.addresses]
                self.assertEqual(read,expected)
                self.assertTrue(all(write[physical]==logical for logical,physical in enumerate(read)))
                single=probe.local.frozen.physical.issue(65536,64,high,number)
                orientation=(bank>>(high%7))&1
                # Single-stage base differs at fold boundaries: derive its own orientation.
                orientation=(single[0].u_bank>>(high%7))&1
                parent,_=probe.data_maps(0,high%7,orientation)
                self.assertEqual(parent,[a for r in single for a in (r.u_bank,r.v_bank)])

    def test_root_source_indices_and_no_direction_mux_local(self):
        for p in range(8):
            for x in range(32):
                for inverse in (False,True):
                    indices=probe.root_indices(1,p,x,inverse=inverse)
                    self.assertEqual(len(indices),96)
                    self.assertTrue(all(0<=i<282 for i in indices))
                    expected=probe.root_indices(2,p,x,inverse=inverse)
                    self.assertEqual(expected,probe.root_indices(2,p,0,inverse=not inverse))
                    self.assertTrue(all(0<=i<126 for i in expected))
        self.assertEqual(probe.root_indices(0,0,0,root_mask=0)[:64],[0]*64)

    def test_source_typed_contracts_and_replayable_role_closure(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve()/'roles'
            r=probe.prepare_roles(root)
            for mode,label in probe.MODES.items():
                m=json.loads((root/(label+'-manifest.json')).read_text())
                self.assertEqual(m['build']['parameters'],dict(MODE=mode))
                self.assertIn(f'-DN1_SELECTOR_MODE={mode}',m['build']['cflags'])
                self.assertEqual(m['steps'][1]['expected_returncode'],1)
                self.assertEqual(m['steps'][1]['expected_stderr'],'N1_SELECTOR_MISMATCH\n')
                for name,pin in m['sources'].items():self.assertEqual(probe.sha(root/'source/fpga'/name),pin)
            self.assertFalse(r['native_execution'])
            with self.assertRaisesRegex(ValueError,'fresh canonical'):probe.prepare_roles(root)

    def test_three_matched_component_controls(self):
        with tempfile.TemporaryDirectory() as d:
            controls=[]
            for mode in probe.MODES:
                root=Path(d).resolve()/str(mode)
                p=probe.prepare_project(root,mode,6)
                m=json.loads((root/'manifest.json').read_text())
                self.assertEqual(m['clock_period_ns'],10.0)
                self.assertEqual(m['compile_processors'],6)
                self.assertFalse(m['architectural_RTL_GO'])
                self.assertIn('ENABLE_INTERMEDIATE_SNAPSHOTS ON',(root/'probe.qsf').read_text())
                controls.append((root/'probe.qsf').read_text().replace('MODE '+str(mode),'MODE X'))
            self.assertEqual(controls[0],controls[1]);self.assertEqual(controls[1],controls[2])

    def test_invalid_mode_and_control_refusal(self):
        for bad in (-1,3,True):
            with self.assertRaisesRegex(ValueError,'typed selector'):probe.data_maps(bad,1,0)
        with self.assertRaisesRegex(ValueError,'typed root'):probe.root_indices(2,8,0)


if __name__=='__main__':unittest.main()

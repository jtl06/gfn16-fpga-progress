import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import root_lookahead_prepare_v1 as p
from fpga.reference import root_recurrence27_lookahead_v1 as s


class PreparationTests(unittest.TestCase):
    def test_lint_only_delta(self):
        original=(p.ROOT/p.FROZEN_LAUNCHER).read_text()
        expected=p.lint_launcher(original)
        self.assertEqual(expected,(p.ROOT/p.LAUNCHER).read_text())
        self.assertLess(expected.index("run('lint', lint)"),expected.index("run('build', command)"))
        self.assertEqual(expected.count("run('lint', lint)"),1)

    def test_closed_modules_and_pair(self):
        pins=p.pins();p.source_modules(p.ROOT,pins)
        top=(p.ROOT/'rtl/tb/root_lookahead_engine_pair_v1.sv').read_text()
        self.assertIn('(cycles !== baseline_cycles)',top)
        self.assertIn('(seed_setup_cycles !== baseline_seed_setup_cycles)',top)

    def test_manifest_roles_and_typed_fault(self):
        sources=p.pins()
        for host in ('aethia','gfn16-pilot-c4'):
            for role in ('control','mutant','aw5'):
                m=p.manifest(host,sources,role)
                self.assertTrue(m['admission']['lint_first'])
                self.assertFalse(m['admission']['promotion_allowed'])
                if role=='mutant':
                    self.assertEqual(m['steps'][0]['expected_returncode'],1)
                    self.assertEqual(m['steps'][0]['expected_stderr'],'ROOT_LOOKAHEAD_PAIR_MISMATCH\n')
                    self.assertEqual(m['steps'][0]['argv'],['{exe}','--bubble-witness'])

    def test_aw5_independent_vectors(self):
        _,profile=p.source_modules(p.ROOT,p.pins())
        rows=p.aw5_vectors(profile).splitlines()
        self.assertEqual(rows[0],'ROOTLOOKAW5 3084 3')
        self.assertEqual(len(rows[1].split()),3084)
        self.assertEqual(len(rows),20)
        self.assertTrue(all(len(row.split())==32 for row in rows[2:]))

    def test_physical_matched_projects(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);result=p.physical_projects(out,p.ROOT,s)
            self.assertEqual(len(result),4)
            for ns in (8,10):
                parent=out/'physical'/f'matched-rootfused-parent-{ns}ns'
                candidate=out/'physical'/f'candidate-{ns}ns'
                self.assertEqual((parent/'probe.sdc').read_bytes(),(candidate/'probe.sdc').read_bytes())
                self.assertEqual((parent/'run.tcl').read_bytes(),(candidate/'run.tcl').read_bytes())
                self.assertIn(f'-period {ns} ',(parent/'probe.sdc').read_text())
                m=json.loads((candidate/'manifest.json').read_text())
                self.assertFalse(m['promotion_allowed'])
                self.assertEqual(m['allowed_stages'],['syn','fit','sta'])
                self.assertEqual(m['compile_processors'],4)
                self.assertEqual(len(m['source_sha256']),7)


if __name__=='__main__':unittest.main()

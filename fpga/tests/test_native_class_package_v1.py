"""r38 integration guards, pure source/package tests only."""
import ast
import json
import unittest
from fpga.tools import native_class_package_v1 as p, native_class_v1 as c
from fpga.tests.test_native_shared_v1 import SharedNativeTests


class ClassPackageTests(SharedNativeTests):
    def test_exact_package_and_identity(self):
        for field, profile in [('gcp','gcp-c4d-static23-v1'), ('local','aethia-static02-v1')]:
            budget = self.root/'cloud-budget.json'
            budget.write_text(json.dumps(self.budget))
            if field == 'local':
                budget = self.root/'local.json'
                budget.write_text(json.dumps(dict(provider='local',host='aethia',cloud_cost_usd=0)))
            out=self.root/field
            p.prepare(self.manifest,self.source,profile,'class-'+field,'run',out,budget)
            ticket=json.loads((out/'ticket.json').read_text())
            manifest=json.loads((out/'manifest.json').read_text())
            for name,digest in ticket['tools'].items():
                path=name if '/' in name else 'tools/'+name
                self.assertEqual(p.hashlib.sha256((out/'capture/source/fpga'/path).read_bytes()).hexdigest(),digest)
            self.assertEqual(manifest['sources']['tools/native_class_v1.py'],p.EXECUTOR_SHA)
            self.assertIn('tools/native_static_package_v1.py',manifest['sources'])
            self.assertIn('results/throughput-20260929/azure-sim-f32-admission-v1/toolchain-terminal-v1.json',manifest['sources'])
            self.assertFalse(ticket['promotion_allowed'])

    def test_class_flags_and_failure_receipt_both_phases(self):
        raw=c.host.static_module().pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
        for name in c.SELECTIONS:
            text=c.adapted_source(raw,c.profile(name));ast.parse(text)
            self.assertEqual(text.count("'-Wno-fatal'"),2)
            self.assertIn("if name in ('lint', 'build'):",text)
            self.assertIn("report[name + '_admission'] = error.receipt",text)
            self.assertIn('fcntl.LOCK_EX | fcntl.LOCK_NB',text)
            self.assertIn('check_scratch_quota(scratch',text)
            self.assertIn('os.killpg(child.pid, signal.SIGKILL)',text)
            self.assertNotIn('admit_lint(',text)
        with self.assertRaises(ValueError):c.adapted_source(raw+b'\n',c.profile('gcp-c4d-static01-v1'))

    def test_defect_cannot_be_baselined(self):
        with self.assertRaises(c.classes.LintClassError) as error:
            c.classes.classify(0,b'',b'%Warning-WIDTH: x.sv:1: bad\n',{'lint_baseline':{'review':'PASS_fake'}},self.root)
        self.assertEqual(error.exception.receipt['fatal_class_counts'],{'WIDTH':1})


if __name__=='__main__':unittest.main()

"""Static host package binding tests; no native or remote execution."""
import ast
import json
from pathlib import Path
import tempfile
import unittest
from fpga.tools import native_static_package_v1 as s
from fpga.tests.test_native_shared_v1 import SharedNativeTests


class StaticPackageTests(SharedNativeTests):
    def test_static_aethia_three_pairs_package(self):
        budget=self.root/'local-budget.json';budget.write_text(json.dumps(dict(provider='local',host='aethia',cloud_cost_usd=0)))
        for suffix in ('02','46','810'):
            out=self.root/('static-'+suffix)
            report=s.prepare(self.manifest,self.source,'aethia-static'+suffix+'-v1','static-'+suffix,'lint',out,budget)
            m=json.loads((out/'manifest.json').read_text());t=json.loads((out/'ticket.json').read_text())
            self.assertEqual(m['host'],'aethia');self.assertEqual(t['budget']['provider'],'local')
            self.assertEqual(m['sources']['tools/native_static_v1.py'],s.STATIC_SHA)
            self.assertIn('tools/native_static_package_v1.py',m['sources'])
            self.assertIn('cloud/aethia-native-thread-profiles-v2.json',m['sources'])
            self.assertEqual(report['status'],'prepared_not_executed')
            for name,pin in t['tools'].items():
                self.assertEqual(s.sha(out/'capture/source/fpga'/s.source_name(name)),pin)

    def test_gcp_cannot_claim_local_budget_exemption(self):
        budget=self.root/'local-budget.json';budget.write_text(json.dumps(dict(provider='local',host='aethia',cloud_cost_usd=0)))
        with self.assertRaisesRegex(ValueError,'host-bound'):s.prepare(self.manifest,self.source,'gcp-c4d-static01-v1','bad-budget','lint',self.root/'bad',budget)
        self.assertFalse((self.root/'bad').exists())

    def test_profile_helpers_and_budget_are_only_deliberate_changes(self):
        raw=(s.HERE/'native_package_v1.py').read_bytes();text=s.adapted_source(raw);ast.parse(text)
        for preserved in ('queue.claim(registry','queue.archive_inventory','source pin','fresh job outputs'):
            if preserved=='source pin':continue
            self.assertIn(preserved,text)
        self.assertIn("load('native_static_v1.py')",text)
        self.assertIn("source/'tools/native_static_package_v1.py'",text)
        self.assertNotIn('subprocess',text)
        with self.assertRaises(ValueError):s.adapted_source(raw+b'\n')


if __name__=='__main__':unittest.main()

import json
import unittest
from fpga.tools import native_class_package_v2 as p
from fpga.tests.test_native_shared_v1 import SharedNativeTests


class BudgetBindingTests(SharedNativeTests):
    def test_azure_gcp_budget_rejected_before_output(self):
        out=self.root/'bad-azure'
        with self.assertRaisesRegex(ValueError,'host budget not admitted'):
            p.prepare(self.manifest,self.source,'azure-f32-static01-v1','no-cross-provider','run',out,self.budget_path)
        self.assertFalse(out.exists())

    def test_gcp_exact_package_self_and_parent(self):
        out=self.root/'good-gcp'
        p.prepare(self.manifest,self.source,'gcp-c4d-static23-v1','good-gcp','run',out,self.budget_path)
        m=json.loads((out/'manifest.json').read_text());t=json.loads((out/'ticket.json').read_text())
        self.assertIn('tools/native_class_package_v2.py',m['sources'])
        self.assertEqual(m['sources']['tools/native_class_package_v1.py'],p.PARENT_SHA)
        self.assertIn('native_class_package_v2.py',t['tools'])
        self.assertIn('native_class_package_v1.py',t['tools'])
        self.assertTrue(p.worker().__file__.endswith('native_class_package_v2.py'))

    def test_host_provider_matrix(self):
        for host in ('gfn16-azure-sim-f32','gfn16-azure-f16','unknown'):
            for provider in ('gcp','azure','local'):
                with self.assertRaises(ValueError):p.binding({'provider':provider},{'host':host})
        with self.assertRaises(ValueError):p.binding({'provider':'local'},{'host':'gfn16-pilot-c4d'})
        with self.assertRaises(ValueError):p.binding({'provider':'gcp'},{'host':'aethia'})


if __name__=='__main__':unittest.main()

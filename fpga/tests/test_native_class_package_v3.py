import copy
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from fpga.tests.test_native_shared_v1 import SharedNativeTests
from fpga.tools import native_class_package_v3 as p, native_class_v2 as c, native_package_v5 as stager


class AzurePackageTests(SharedNativeTests):
    def setUp(self):
        super().setUp()
        original=p.meter
        def fixed_meter():
            module=original();validate=module.validate_budget
            def fixed(value,host,max_seconds=3715,now=None,**kwargs):
                return validate(value,host,max_seconds,now=now or datetime(2026,10,1,7,53,tzinfo=timezone.utc),**kwargs)
            module.validate_budget=fixed
            return module
        guard=patch.object(p,'meter',side_effect=fixed_meter);guard.start();self.addCleanup(guard.stop)

    def azure_budget(self,profile):
        selected=c.profile(profile)
        meter=p.meter()
        return meter.make_budget(selected['host'],3715,
            'results/throughput-20260929/azure-host-hours-v2/provider-inputs-075211-v1.json',
            '55dccf9b3cba9d49a77d21651c1debd0cf4f04737e9b57524e413be8880bb2ef',
            p.source_identity(self.m),selected['profile_sha256'])

    def test_both_azure_packages_source_budget_closure(self):
        for profile in ('azure-f32-static01-v1','azure-f16-static45-v1'):
            value=self.azure_budget(profile);budget=self.root/(profile+'.json');budget.write_text(json.dumps(value))
            out=self.root/profile
            prepared=p.prepare(self.manifest,self.source,profile,'azure-test-'+profile,'run',out,budget)
            manifest=json.loads((out/'manifest.json').read_text());ticket=json.loads((out/'ticket.json').read_text())
            self.assertEqual(p.source_identity(manifest),value['source_sha256'])
            self.assertEqual(manifest['budget_source_members'],self.m['sources'])
            self.assertIn('tools/native_class_package_v3.py',manifest['sources'])
            self.assertIn('cloud/host_hours_azure_v2.py',manifest['sources'])
            staged=stager.worker().inspect_archive(out/'package.tar.gz',prepared['archive_sha256'],prepared['ticket_sha256'])
            self.assertEqual(staged[3]['host'],value['host'])
            for name,pin in ticket['tools'].items():
                relative=name if '/' in name else 'tools/'+name
                self.assertEqual(p.hashlib.sha256((out/'capture/source/fpga'/relative).read_bytes()).hexdigest(),pin)

    def test_cross_provider_and_source_profile_drift(self):
        profile=c.profile('azure-f32-static01-v1');value=self.azure_budget('azure-f32-static01-v1')
        with self.assertRaises(ValueError):p.binding(self.budget,profile,self.m)
        for field in ('source_sha256',):
            bad=copy.deepcopy(value);bad[field]='0'*64
            with self.assertRaises(ValueError):p.binding(bad,profile,self.m)
        bad=copy.deepcopy(value);bad['profile']['sha256']='0'*64
        with self.assertRaises(ValueError):p.binding(bad,profile,self.m)
        changed=copy.deepcopy(self.m);changed['build']['parameters']['AW']=16
        with self.assertRaises(ValueError):p.binding(value,profile,changed)

    def test_class_wrapper_retains_outer_f16_api(self):
        self.assertIn('execute_with_parent',c.execute.__code__.co_names)
        parent=c.parent('azure-f16-static45-v1')
        self.assertTrue(callable(parent.guard_protected));self.assertTrue(callable(parent.guard_toolchain))


if __name__=='__main__':unittest.main()

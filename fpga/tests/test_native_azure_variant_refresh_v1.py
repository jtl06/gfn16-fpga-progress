from datetime import datetime,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fpga.tools import native_azure_variant_refresh_v1 as r,native_class_package_v3 as p,native_profile_variants_v2 as v

ROOT=Path(__file__).resolve().parents[1]
PROVIDER=ROOT/'results/throughput-20260929/azure-host-hours-v2/provider-inputs-075211-v1.json'
PROVIDER_SHA='55dccf9b3cba9d49a77d21651c1debd0cf4f04737e9b57524e413be8880bb2ef'

class RefreshTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name).resolve()
        self.existing=ROOT/'artifacts/stream27-p16c-aw6-zero-square23-v1'
        old_loader=r.load
        patched=patch.object(r,'load',side_effect=lambda name,pin: p if name=='native_class_package_v3.py' else old_loader(name,pin));patched.start();self.addCleanup(patched.stop)
        original=p.meter
        def fixed_meter():
            module=original();validate=module.validate_budget
            module.validate_budget=lambda value,host,max_seconds=3715,now=None,**kw:validate(value,host,max_seconds,now=now or datetime(2026,10,1,7,53,tzinfo=timezone.utc),**kw)
            return module
        clock=patch.object(p,'meter',side_effect=fixed_meter);clock.start();self.addCleanup(clock.stop)
    def refresh(self,out=None,id='test-azure-refresh'):
        return r.repackage_variant(self.existing,'azure-f16-static45-v1',id,PROVIDER,PROVIDER_SHA,out or self.root/'new')
    def test_actual_gcp_role_rehost_preserves_function(self):
        result=self.refresh();self.assertEqual(result['status'],'prepared_refreshed_variant_not_executed')
        self.assertTrue(result['old_inputs_preserved']);self.assertTrue(result['logical_claim_required'])
        self.assertTrue((self.root/'new/packet/package.tar.gz').is_file())
        with self.assertRaises(ValueError):self.refresh()
    def test_same_native_id_and_bad_provider_refuse_before_output(self):
        ticket=json.loads((self.existing/'ticket.json').read_text())
        with self.assertRaises(ValueError):self.refresh(id=ticket['id'])
        with self.assertRaises(ValueError):r.repackage_variant(self.existing,'azure-f16-static45-v1','other',PROVIDER,'0'*64,self.root/'bad')
        self.assertFalse((self.root/'new').exists());self.assertFalse((self.root/'bad').exists())
    def test_fresh_budget_still_required_at_live_admission(self):
        result=self.refresh();budget=json.loads((self.root/'new/budget.json').read_text())
        with self.assertRaisesRegex(ValueError,'stale'):
            p.meter().validate_budget(budget,budget['host'],3715,now=datetime(2026,10,1,8,10,tzinfo=timezone.utc))
        manifest=json.loads((self.root/'new/packet/manifest.json').read_text())
        identity=v.functional_fingerprint(manifest,budget,self.root/'new/packet/capture/source/fpga')
        self.assertFalse(identity['fresh_budget_admission_conferred'])

if __name__=='__main__':unittest.main()

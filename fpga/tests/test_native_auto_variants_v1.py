from datetime import datetime,timezone
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fpga.tools import native_auto_variants_v1 as a,native_class_package_v4 as package

ROOT=Path(__file__).resolve().parents[1]

class AutoVariantTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name).resolve()
        self.template=ROOT/'artifacts/stream27-p16c-aw6-zero-square23-v1'
        self.ticket=dict(id='auto-test',owner='p16',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
            packages=[dict(archive=str(self.template/'package.tar.gz'),sha256=a.sha(self.template/'package.tar.gz'),
                ticket_sha256=a.sha(self.template/'ticket.json'),profile='gcp-c4d-static23-v1')])
        gcp=json.loads((ROOT/'queue/hosts/gcp-c4d-q1.json').read_text())
        azure=json.loads((ROOT/'queue/hosts/azure-f16-q2.json').read_text())
        # Live host enablement changes under dispatcher ownership; fixture
        # eligibility is explicit and does not mutate those host records.
        gcp['enabled']=True;azure['enabled']=True
        azure['lanes']=[dict(id='test-f16',profiles=['azure-f16-static1213-v1'],cpus=[12,13],ram_gib=8)]
        self.hosts=[gcp,azure]
        self.provider=dict(path=str(ROOT/'results/throughput-20260929/azure-host-hours-v3/provider-inputs-085825-v1.json'),
            sha256='ec9a88406f55554ca880e2e8a34ba7cb877384c7f4ea12784d415921e791de7c')
        # Only unit-test admission time is fixed; production uses real UTC.
        meter=package.base.meter
        def fixed_meter():
            module=meter();validate=module.validate_budget
            module.validate_budget=lambda value,host,max_seconds=3715,now=None,**kw:validate(value,host,max_seconds,now=now or datetime(2026,10,1,8,59,tzinfo=timezone.utc),**kw)
            return module
        guard=patch.object(package.base,'meter',side_effect=fixed_meter);guard.start();self.addCleanup(guard.stop)
        loader=a.load
        def load(name):
            if name=='tools/native_azure_variant_refresh_v2.py':
                wrapper=loader(name);inner=wrapper.module();old=inner.load
                inner.load=lambda name,pin: package if name=='native_class_package_v4.py' else old(name,pin)
                return inner
            return loader(name)
        guard=patch.object(a,'load',side_effect=load);guard.start();self.addCleanup(guard.stop)
    def test_automatically_emits_missing_gcp_and_f16_variants(self):
        before=copy.deepcopy(self.ticket)
        ticket,receipt=a.expand_variants(self.ticket,self.hosts,self.root/'expanded',self.provider)
        self.assertEqual(self.ticket,before)
        self.assertEqual({p['profile'] for p in ticket['packages']},{'gcp-c4d-static01-v1','gcp-c4d-static23-v1','azure-f16-static1213-v1'})
        self.assertEqual(receipt['notes'],[]);self.assertTrue(receipt['one_logical_claim_required'])
        self.assertEqual(ticket['packages'][-1]['runner'],'tools/native_class_package_v4.py')
    def test_disabled_host_and_missing_provider_never_block_existing(self):
        hosts=copy.deepcopy(self.hosts);hosts[0]['enabled']=False
        ticket,receipt=a.expand_variants(self.ticket,hosts,self.root/'missing')
        self.assertEqual(len(ticket['packages']),1);self.assertIn('provider',receipt['notes'][0]['reason'])
    def test_template_hash_drift_before_output(self):
        self.ticket['packages'][0]['sha256']='0'*64
        with self.assertRaises(ValueError):a.expand_variants(self.ticket,self.hosts,self.root/'bad',self.provider)
        self.assertFalse((self.root/'bad').exists())

if __name__=='__main__':unittest.main()

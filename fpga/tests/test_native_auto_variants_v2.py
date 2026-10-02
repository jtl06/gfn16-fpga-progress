"""Pure resized-host auto-variant fixtures; do not grant live host admission."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fpga.tools import native_auto_variants_v2 as wrapper, native_class_package_v5 as package

ROOT=Path(__file__).resolve().parents[1]


class ResizedAutoTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name).resolve()
        self.a=wrapper.module();template=ROOT/'artifacts/stream27-p16c-aw6-zero-square23-v1'
        self.ticket=dict(id='resized-auto-test',minimum_ram_gib=4,resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
            packages=[dict(archive=str(template/'package.tar.gz'),sha256=self.a.sha(template/'package.tar.gz'),
                ticket_sha256=self.a.sha(template/'ticket.json'),profile='gcp-c4d-static23-v1')])
        host=json.loads((ROOT/'queue/hosts/azure-f32-q2.json').read_text())
        # Synthetic eligible host fixture ONLY; live enablement stays dispatcher-owned.
        host.update(enabled=True)
        host['lanes']=[dict(id='fixture-resized',profiles=['azure-burst16-static01-v1'],cpus=[0,1],ram_gib=4)]
        self.hosts=[host]
        self.provider=dict(path=str(ROOT/'results/throughput-20260929/azure-sim-resize-r49-v1/provider-inputs-v2.json'),
            sha256='92634d6972ae482b6a9a403092ca08e4f3c42d84f36b6446fda1148db06b6e75')
        meter=package.base.meter
        def fixed_meter():
            module=meter();validate=module.validate_budget
            module.validate_budget=lambda value,host,max_seconds=3715,now=None,**kw:validate(value,host,max_seconds,
                now=now or datetime(2026,10,1,9,12,tzinfo=timezone.utc),**kw)
            return module
        guard=patch.object(package.base,'meter',side_effect=fixed_meter);guard.start();self.addCleanup(guard.stop)
        loader=self.a.load
        def load(name):
            if name=='tools/native_azure_variant_refresh_v3.py':
                inner=loader(name).module();old=inner.load
                inner.load=lambda name,pin:package if name=='native_class_package_v5.py' else old(name,pin)
                return inner
            return loader(name)
        guard=patch.object(self.a,'load',side_effect=load);guard.start();self.addCleanup(guard.stop)

    def test_source_preserving_resized_variant_and_metadata(self):
        before=copy.deepcopy(self.ticket)
        result,receipt=self.a.expand_variants(self.ticket,self.hosts,self.root/'expanded',self.provider)
        self.assertEqual(receipt['notes'],[])
        self.assertEqual(len(result['packages']),2);self.assertEqual(self.ticket,before)
        variant=result['packages'][-1]
        self.assertEqual(variant['profile'],'azure-burst16-static01-v1')
        self.assertEqual(variant['resources']['ram_gib'],4)
        self.assertEqual(variant['runner'],'tools/native_class_package_v5.py')
        self.assertTrue(variant['stager'].endswith('native_package_v7.py'))

    def test_no_silent_ram_reduction_or_unadmitted_host(self):
        self.ticket.pop('minimum_ram_gib')
        result,receipt=self.a.expand_variants(self.ticket,self.hosts,self.root/'too-small',self.provider)
        self.assertEqual(len(result['packages']),1)
        self.assertIn('minimum RAM',receipt['notes'][0]['reason'])
        self.hosts[0]['enabled']=False
        result,_=self.a.expand_variants(self.ticket,self.hosts,self.root/'disabled',self.provider)
        self.assertEqual(len(result['packages']),1)

    def test_provider_hash_mismatch_preserves_existing_variant(self):
        self.provider['sha256']='0'*64
        result,receipt=self.a.expand_variants(self.ticket,self.hosts,self.root/'bad-provider',self.provider)
        self.assertEqual(len(result['packages']),1)
        self.assertIn('provider capture pin',receipt['notes'][0]['reason'])


if __name__=='__main__':unittest.main()

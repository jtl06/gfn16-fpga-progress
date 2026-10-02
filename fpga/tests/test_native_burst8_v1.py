"""Same-hardware memory envelope and exact automatic role preservation."""
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fpga.tools import native_auto_variants_v3 as wrapper, native_class_package_burst8_v1 as package
from fpga.tools import native_class_burst8_v1 as policy,native_stage_burst8_v1 as stage

ROOT=Path(__file__).resolve().parents[1]


class BurstMemoryTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name).resolve()
        self.auto=wrapper.module();template=ROOT/'artifacts/stream27-p16c-aw6-zero-square23-v1'
        self.ticket=dict(id='burst-eight-test',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
            packages=[dict(archive=str(template/'package.tar.gz'),sha256=self.auto.sha(template/'package.tar.gz'),
                ticket_sha256=self.auto.sha(template/'ticket.json'),profile='gcp-c4d-static23-v1')])
        host=json.loads((ROOT/'queue/hosts/azure-f32-q2.json').read_text());host['enabled']=True
        host['lanes']=[dict(id='same-pair-fixture',profiles=['azure-burst16-static01-v1','azure-burst16-static8g01-v1'],cpus=[0,1],ram_gib=8)]
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
        loader=self.auto.load
        def load(name):
            if name=='tools/native_azure_variant_refresh_v4.py':
                refresh=loader(name)
                class Bound:
                    @staticmethod
                    def repackage_variant(existing,selected,*args,**kw):
                        inner=refresh.module(selected);old=inner.load
                        inner.load=lambda name,pin:package if name=='native_class_package_burst8_v1.py' else old(name,pin)
                        return inner.repackage_variant(existing,selected,*args,**kw)
                return Bound
            return loader(name)
        guard=patch.object(self.auto,'load',side_effect=load);guard.start();self.addCleanup(guard.stop)

    def test_auto_chooses_eight_without_lowering_minimum_or_changing_role(self):
        before=copy.deepcopy(self.ticket)
        result,receipt=self.auto.expand_variants(self.ticket,self.hosts,self.root/'variants',self.provider)
        self.assertEqual(receipt['notes'],[]);self.assertEqual(self.ticket,before)
        p=result['packages'][-1];self.assertEqual(p['profile'],'azure-burst16-static8g01-v1')
        self.assertEqual(p['resources']['ram_gib'],8)
        self.assertEqual(p['runner'],'tools/native_class_package_burst8_v1.py')
        self.assertEqual(len(p['stager_dependencies']),2)
        inspected=stage.worker().inspect_archive(Path(p['archive']),p['sha256'],p['ticket_sha256'])
        self.assertEqual(inspected[3]['memory_bytes'],8<<30)

    def test_hardware_rate_identity_separate_from_resource_envelope(self):
        for pair in ('01','23','45','67','89','1011','1213','1415'):
            p=policy.profile('azure-burst16-static8g'+pair+'-v1')
            self.assertEqual(p['memory_bytes'],8<<30);self.assertEqual(p['minimum_host_available_bytes'],8<<30)
            self.assertEqual(p['aggregate_native_memory_cap_bytes'],48<<30)
            self.assertLess((48+8)<<30,p['observed_total_memory_bytes'])
            self.assertEqual(p['profile_sha256'],'eef2a816c7fc6ae5e53919b24b2bb135a16808d7ef7ccb7341395b0c030b596d')
            self.assertEqual(p['memory_envelope_sha256'],'04fe25064f68301526492ebd232dba201fb15469e88c9f2cee0d3389215a9808')
            policy.parent(p['profile_id'])

    def test_larger_minimum_and_bad_provider_pin_fail_closed(self):
        self.ticket['resources']['ram_gib']=24
        result,_=self.auto.expand_variants(self.ticket,self.hosts,self.root/'too-large',self.provider)
        self.assertEqual(len(result['packages']),1)
        self.ticket['resources']['ram_gib']=8;self.provider['sha256']='0'*64
        result,receipt=self.auto.expand_variants(self.ticket,self.hosts,self.root/'bad-provider',self.provider)
        self.assertEqual(len(result['packages']),1);self.assertTrue(receipt['notes'])


if __name__=='__main__':unittest.main()

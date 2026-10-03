"""Literal application70 GMP source binding only; no candidate/math execution."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from fpga.tools import native_class_v2 as policy
from fpga.tools import native_class_package_v4 as package,native_package_v6 as stage
from fpga.tests import test_r15_f16_existing_native as fixtures

ROOT=Path(__file__).resolve().parents[1]
ROLES=ROOT/'results/throughput-20261003/r15-host-window-application-gmp-native-v1'


class ApplicationGmpTests(unittest.TestCase):
    def test_exact_application_schema_cannot_inherit_direct65_or_arbitrary_role(self):
        selected=policy.profile('azure-f16-static1213-v1')
        for index,mode in enumerate(('normal','faults')):
            role=json.loads((ROLES/mode/'manifest.json').read_bytes())
            self.assertEqual(package.source_identity(role),policy.GMP_APPLICATION_FIXTURES[index])
            self.assertEqual(role['metadata']['r15_native_gmp']['schema'],'r15-application70-gmp-link-v1')
            self.assertEqual(len(role['build']['sv_sources']),71)
            self.assertEqual(len(role['r15_application_host_window']['production_generated_sha256']),70)
            self.assertEqual(policy.gmp_ldflags(role,selected,Path(role['source_root'])),['-LDFLAGS','-lgmpxx -lgmp'])
            for change in ('schema','fixture','cpp','flags','probe'):
                bad=copy.deepcopy(role)
                if change=='schema':bad['metadata']['r15_native_gmp']['schema']='r15-direct65-gmp-link-v1'
                elif change=='fixture':bad['metadata']['r15_native_gmp']['fixture_sha256']=policy.GMP_FIXTURES[index]
                elif change=='cpp':bad['build']['cpp_source']='rtl/evil.cpp'
                elif change=='flags':bad['build']['ldflags']+=['-lother']
                else:bad['probe']['expected_json']['context_threads']=8
                with self.subTest(mode=mode,change=change),self.assertRaises(ValueError):package.source_identity(bad)
        direct=json.loads((ROOT/'results/throughput-20261003/r15-host-window-gmp-native-v1/normal/manifest.json').read_bytes())
        direct['metadata']['r15_native_gmp']['schema']='r15-application70-gmp-link-v1'
        with self.assertRaisesRegex(ValueError,'source-pinned'):package.source_identity(direct)

    def test_real_frozen_application_normal_fault_prepare_and_dual_stage(self):
        with tempfile.TemporaryDirectory(prefix='r15-app-gmp-source-proof-',dir=ROOT/'artifacts') as temporary:
            out=Path(temporary).resolve()
            for mode in ('normal','faults'):
                path=ROLES/mode/'manifest.json';before=path.read_bytes();role=json.loads(before)
                budget=fixtures.R15ExistingF16Tests.fixture_budget(self,out,role)
                budgetpath=out/(mode+'-budget.json');budgetpath.write_text(json.dumps(budget))
                for pair in ('1213','1415'):
                    selected='azure-f16-static'+pair+'-v1';packet=out/(mode+'-'+pair)
                    prepared=package.prepare(path,Path(role['source_root']),selected,
                        'metadata-app-gmp-'+mode+'-'+pair,'run',packet,budgetpath)
                    payload,ticket,manifest,placement=stage.worker().inspect_archive(packet/'package.tar.gz',
                        prepared['archive_sha256'],prepared['ticket_sha256'])
                    self.assertEqual(manifest['build'],role['build']);self.assertEqual(manifest['steps'],role['steps'])
                    self.assertEqual(manifest['metadata'],role['metadata']);self.assertEqual(manifest['budget_source_members'],role['sources'])
                    self.assertEqual(ticket['max_seconds'],3700);self.assertEqual(placement['static_lanes'],2)
                    self.assertEqual(placement['memory_bytes'],8<<30);self.assertEqual(placement['compile_workers'],2)
                    self.assertEqual(placement['model_threads'],1);self.assertEqual(placement['scratch_floor_bytes'],20<<30)
                    self.assertEqual(hashlib.sha256(payload['capture/source/fpga/'+policy.GMP_INVENTORY]).hexdigest(),policy.GMP_INVENTORY_SHA)
                self.assertEqual(path.read_bytes(),before)


if __name__=='__main__':unittest.main()

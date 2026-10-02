"""Actual fixed-wide short packets, immutable placement and identity checks."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from fpga.tools import native_threaded_wide_package_v1 as package
from fpga.tools import native_threaded_wide_stage_v1 as stage
from fpga.tools import native_threaded_wide_v1 as runtime
from fpga.tools import native_profile_variants_v9 as prior
from fpga.tools import native_profile_variants_v10 as variants

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'results/throughput-20260929/threaded-wide-package-v1'


def packet(count):
    p=DATA/f'packet{count}'
    return p,json.loads((p/'manifest.json').read_text()),json.loads((p/'ticket.json').read_text())


class WidePackageTests(unittest.TestCase):
    def test_actual_three_safe_archives_and_same_allocation(self):
        contracts=[];keys=[];fingerprints=[]
        for count in (2,4,8):
            p,m,t=packet(count);receipt=json.loads((p/'preparation.json').read_text())
            _,actual,manifest,_=stage.worker().inspect_archive(p/'package.tar.gz',receipt['archive_sha256'],receipt['ticket_sha256'])
            self.assertEqual(t,actual);self.assertEqual(m,manifest)
            self.assertEqual(t['max_seconds'],3700);self.assertEqual(t['budget']['max_seconds'],3715)
            self.assertEqual(t['fixed_execution'],m['fixed_execution']);self.assertEqual(t['placement'],m['fixed_execution']['placement'])
            self.assertEqual(m['build']['runtime_threads'],count)
            allocation=m['fixed_execution']['runtime_allocation']
            self.assertEqual(allocation,dict(cpus=list(range(8)),physical_cores=[[0,i] for i in range(8)],cpu_quota_percent=800,compile_workers=2,memory_bytes=8<<30))
            contracts.append(m['fixed_execution']);keys.append(t['build_key'])
            fingerprints.append(variants.functional_fingerprint(m,t['budget'],p/'capture/source/fpga')['sha256'])
        self.assertEqual(contracts[0],contracts[1]);self.assertEqual(contracts[0],contracts[2]);self.assertEqual(len(set(keys)),3);self.assertEqual(len(set(fingerprints)),3)

    def test_placement_cache_resource_model_tampering_rejected(self):
        p,m,t=packet(2)
        for kind in ('cpu','physical','quota','ram','cache','overlay','role-count','role-placement','runtime-pin'):
            altered=copy.deepcopy(m);fixed=altered['fixed_execution']
            if kind=='cpu':fixed['runtime_allocation']['cpus']=[0,1]
            elif kind=='physical':fixed['runtime_allocation']['physical_cores'][1]=[0,0]
            elif kind=='quota':fixed['runtime_allocation']['cpu_quota_percent']=200
            elif kind=='ram':fixed['runtime_allocation']['memory_bytes']=4<<30
            elif kind=='cache':fixed['observed_l3']['shared_cpu_list']='8-15'
            elif kind=='overlay':fixed['profile_sha256']='0'*64
            elif kind=='role-count':altered['wide_thread_pilot']['thread_count']=4
            elif kind=='role-placement':altered['wide_thread_pilot']['placement']['cpus']=[0,1]
            else:altered['sources']['tools/native_threaded_wide_v1.py']='0'*64
            with self.subTest(kind=kind),self.assertRaises(ValueError):variants.functional_fingerprint(altered,t['budget'],p/'capture/source/fpga')

    def test_old_p3_and_serial_identities_unchanged_but_wide_baseline_distinct(self):
        old=ROOT/'artifacts/soak-t5b-thread100-burst23-v1';m=json.loads((old/'manifest.json').read_text());t=json.loads((old/'ticket.json').read_text())
        self.assertEqual(variants.functional_fingerprint(m,t['budget'],old/'capture/source/fpga'),prior.functional_fingerprint(m,t['budget'],old/'capture/source/fpga'))
        p,m,t=packet(2);self.assertIn('fixed_execution',variants.functional_fingerprint(m,t['budget'],p/'capture/source/fpga')['identity'])

    def test_actual_unpacked_final_namespace_source_loader(self):
        p,m,t=packet(8)
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp).resolve();root=base/'capture/source/fpga';shutil.copytree(p/'capture/source/fpga',root)
            out=base/'output';out.mkdir();m.update(source_root=str(root),output_parent=str(out));path=base/'manifest.json';path.write_text(json.dumps(m));pin=hashlib.sha256(path.read_bytes()).hexdigest()
            value=runtime.parent(runtime.PROFILE_ID);value.PROFILES={m['host']:dict(runtime.profile(runtime.PROFILE_ID),base=str(base))};value.__file__=str(root/value.SELF)
            self.assertIs(value.load_manifest.__globals__,value.__dict__);value.LEASE_FDS=tuple(range(100,114));self.assertEqual(value.execute.__globals__['LEASE_FDS'],tuple(range(100,114)))
            with patch.object(value.socket,'gethostname',return_value=m['host']):self.assertEqual(value.load_manifest(path,pin)[0],m)
            with patch.object(value.socket,'gethostname',return_value='gfn16-pilot-c4d'):
                with self.assertRaises(ValueError):value.load_manifest(path,pin)

    def test_final_package_binding_rejects_wrong_role_before_any_side_effect(self):
        p,m,t=packet(2);profile=runtime.profile(runtime.PROFILE_ID)
        package.wide_binding(m,profile,True)
        for field in ('fixed_execution','wide_thread_pilot'):
            changed=copy.deepcopy(m);changed[field]={}
            with self.assertRaises(ValueError):package.wide_binding(changed,profile,True)


if __name__=='__main__':unittest.main()

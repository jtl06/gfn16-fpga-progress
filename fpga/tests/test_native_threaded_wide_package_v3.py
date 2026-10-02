"""Final live-guard captured runtime, package identity and real child binding."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from fpga.tools import native_threaded_wide_stage_v3 as stage
from fpga.tools import native_profile_variants_v12 as variants

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'results/throughput-20260929/threaded-wide-package-v3'


class CallableWidePackageTests(unittest.TestCase):
    def test_three_actual_packages_preserve_all_donor_and_fixed_contracts(self):
        fps=[]
        for count in (2,4,8):
            old=ROOT/'results/throughput-20260929/threaded-wide-package-v1'/f'packet{count}-v2';new=DATA/f'packet{count}';r=json.loads((new/'preparation.json').read_text())
            _,t,m,_=stage.worker().inspect_archive(new/'package.tar.gz',r['archive_sha256'],r['ticket_sha256'])
            prior=json.loads((old/'manifest.json').read_text())
            for key in ('build','probe','steps','fixed_execution','wide_thread_pilot','budget_source_members'):self.assertEqual(prior[key],m[key])
            self.assertEqual(t['placement'],m['fixed_execution']['placement'])
            self.assertEqual(t['max_seconds'],3700)
            fps.append(variants.functional_fingerprint(m,t['budget'],new/'capture/source/fpga')['sha256'])
        self.assertEqual(len(set(fps)),3)

    def test_actual_unpacked_final_runtime_import_loader_and_harmless_child(self):
        packet=DATA/'packet8'
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary).resolve();root=base/'capture/source/fpga';shutil.copytree(packet/'capture/source/fpga',root)
            path=root/'tools/native_threaded_wide_v3.py'
            spec=importlib.util.spec_from_file_location('_actual_captured_wide_runtime',path);runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)
            value=runtime.parent(runtime.PROFILE_ID);self.assertTrue(callable(value.MeasuredPopen))
            child=value.MeasuredPopen([sys.executable,'-B','-c','pass']);self.assertEqual(child.wait(timeout=10),0)
            self.assertIsNotNone(child.native_usage)
            out=base/'output';out.mkdir();m=json.loads((packet/'manifest.json').read_text());m.update(source_root=str(root),output_parent=str(out));manifest=base/'manifest.json';manifest.write_text(json.dumps(m))
            value.PROFILES={m['host']:dict(runtime.profile(runtime.PROFILE_ID),base=str(base))}
            value.LEASE_FDS=tuple(range(14));self.assertEqual(value.execute.__globals__['LEASE_FDS'],tuple(range(14)))
            with patch.object(value.socket,'gethostname',return_value=m['host']):self.assertEqual(value.load_manifest(manifest,hashlib.sha256(manifest.read_bytes()).hexdigest())[0],m)

    def test_previous_startup_only_family_not_stageable_as_live_successor(self):
        old=ROOT/'results/throughput-20260929/threaded-wide-package-v1/packet2-v2';r=json.loads((old/'preparation.json').read_text())
        with self.assertRaises(ValueError):stage.worker().inspect_archive(old/'package.tar.gz',r['archive_sha256'],r['ticket_sha256'])

    def test_fixed_placement_and_count_stay_mandatory(self):
        p=DATA/'packet2';m=json.loads((p/'manifest.json').read_text());t=json.loads((p/'ticket.json').read_text())
        for kind in ('placement','ram','model','pin'):
            changed=copy.deepcopy(m)
            if kind=='placement':changed['fixed_execution']['placement']['cpus']=[0,1]
            elif kind=='ram':changed['fixed_execution']['runtime_allocation']['memory_bytes']=4<<30
            elif kind=='model':changed['wide_thread_pilot']['thread_count']=8
            else:changed['sources']['tools/native_threaded_wide_v3.py']='0'*64
            with self.subTest(kind=kind),self.assertRaises(ValueError):variants.functional_fingerprint(changed,t['budget'],p/'capture/source/fpga')


if __name__=='__main__':unittest.main()

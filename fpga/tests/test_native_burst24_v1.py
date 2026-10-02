"""Memory-only host envelope and actual portable representative packet checks."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from fpga.tools import native_static_v4 as original
from fpga.tools import native_static_burst24_v1 as host
from fpga.tools import native_class_burst24_v1 as runtime
from fpga.tools import native_stage_burst24_v1 as stage
from fpga.tools import native_profile_variants_v8 as previous
from fpga.tools import native_profile_variants_v9 as variants

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'results/throughput-20260929/azure-burst24-anext-point-v1'


def load_packet(path):
    return dict(manifest=json.loads((path/'manifest.json').read_text()),budget=json.loads((path/'ticket.json').read_text())['budget'],source_root=path/'capture/source/fpga')


class Burst24Tests(unittest.TestCase):
    def test_same_eight_physical_pairs_no_tool_thread_time_or_budget_change(self):
        for pair in ('01','23','45','67','89','1011','1213','1415'):
            old=original.profile('azure-burst16-static'+pair+'-v1');new=host.profile('azure-burst16-static24g'+pair+'-v1')
            for key in ('cpus','topology','hashes','base','lock','physical_locks','pair_lock','profile_source','profile_sha256','burst_deadline_epoch','scratch_reservation_bytes'):
                self.assertEqual(old[key],new[key],key)
            self.assertEqual(new['memory_bytes'],24<<30)
            self.assertEqual(new['aggregate_native_memory_cap_bytes'],48<<30)
            self.assertEqual(new['minimum_host_available_bytes'],8<<30)
            self.assertEqual(new['cpu_quota_percent'],200)
            value=runtime.parent(new['profile_id']);self.assertIs(value.load_manifest.__globals__,value.__dict__)

    def test_exact_envelope_negatives(self):
        real=json.loads((ROOT/host.ENVELOPE).read_text());original_load=host.json.loads
        for key,change in [('memory',8<<30),('cpus',[0,2]),('aggregate',64<<30),('floor',0),('hardware','0'*64)]:
            bad=copy.deepcopy(real)
            if key=='memory':bad['profiles']['azure-burst16-static24g01-v1']['memory_bytes']=change
            elif key=='cpus':bad['profiles']['azure-burst16-static24g01-v1']['cpus']=change
            elif key=='aggregate':bad['aggregate_native_memory_cap_bytes']=change
            elif key=='floor':bad['minimum_host_available_bytes']=change
            else:bad['hardware_profile_sha256']=change
            def decode(text,*args,**kwargs):
                result=original_load(text,*args,**kwargs)
                return bad if result.get('schema')=='gfn16-burst-memory-envelope-v1' else result
            with self.subTest(key=key),patch.object(host.json,'loads',side_effect=decode),self.assertRaises(ValueError):host.profile('azure-burst16-static24g01-v1')

    def test_actual_staged_packages_and_gcp_functional_identity(self):
        old=load_packet(ROOT/'artifacts/anext-point-representative-aw16-gcp01-packet-v1')
        values=[old]
        for pair in ('01','45'):
            p=DATA/('packet'+pair);receipt=json.loads((p/'preparation.json').read_text())
            _,ticket,m,_=stage.worker().inspect_archive(p/'package.tar.gz',receipt['archive_sha256'],receipt['ticket_sha256'])
            self.assertEqual(ticket['max_seconds'],3700);self.assertEqual(ticket['budget']['max_seconds'],3715)
            for key in ('build','probe','steps','budget_source_members'):self.assertEqual(old['manifest'][key],m[key])
            values.append(load_packet(p))
        matched=variants.match_variants(values)
        self.assertEqual(matched['functional_sha256'],previous.functional_fingerprint(**old)['sha256'])
        for kind in ('compiled','validator','unrecognized-control'):
            bad=copy.deepcopy(values)
            m=bad[1]['manifest']
            key=m['build']['cpp_source'] if kind=='compiled' else m['steps'][0]['validator']['source'] if kind=='validator' else 'tools/native_class_burst24_v1.py'
            m['sources'][key]='0'*64
            with self.assertRaises(ValueError):variants.match_variants(bad)

    def test_actual_unpacked_source_loader(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp).resolve();root=base/'capture/source/fpga';shutil.copytree(DATA/'packet01/capture/source/fpga',root)
            out=base/'output';out.mkdir();m=json.loads((DATA/'packet01/manifest.json').read_text());m.update(source_root=str(root),output_parent=str(out))
            path=base/'manifest.json';path.write_text(json.dumps(m));pin=hashlib.sha256(path.read_bytes()).hexdigest()
            value=runtime.parent(m['cpu_profile']);value.PROFILES={m['host']:dict(runtime.profile(m['cpu_profile']),base=str(base))};value.__file__=str(root/value.SELF)
            with patch.object(value.socket,'gethostname',return_value=m['host']):self.assertEqual(value.load_manifest(path,pin)[0],m)
            with patch.object(value.socket,'gethostname',return_value='gfn16-pilot-c4d'):
                with self.assertRaises(ValueError):value.load_manifest(path,pin)


if __name__=='__main__':unittest.main()

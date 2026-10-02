"""Pure measured-duration and real generated namespace/source-gate checks.

No role/GMP import, reference generation, native/HDL/full-N execution.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fpga.tools import native_thread_config_v1 as config
from fpga.tools import native_threaded_duration_v1 as duration
from fpga.tools import native_threaded_long_class_v1 as runner

ROOT=Path(__file__).resolve().parents[1]
PILOT=ROOT/'artifacts/soak-t5b-thread100-burst23-v1'
NATIVE=ROOT/'queue/evidence/soak-t5b-thread100-q3-v1/attempt-0/collected/output/native'
LONG=ROOT/'results/throughput-20260929/soak-t5b-aw16-continuous-cross-burst16-manifest-v2'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def data():
    pilot=json.loads((PILOT/'manifest.json').read_text())
    report=json.loads((NATIVE/'report.json').read_text())
    gate_path=ROOT/'results/throughput-20260929/core27-t5b-soak-thread100-native-v1/native-gate.json'
    gate=json.loads(gate_path.read_text())
    values=dict(pilot_manifest=pilot,pilot_report=report,pilot_gate=gate,
                forecast=duration.forecast(pilot,report,gate))
    pins=dict(pilot_manifest=sha(PILOT/'manifest.json'),pilot_report=sha(NATIVE/'report.json'),
              pilot_gate=sha(gate_path),forecast=hashlib.sha256(json.dumps(values['forecast']).encode()).hexdigest())
    manifest=json.loads((LONG/'cross-runtime-manifest.json').read_text())
    manifest['build']=config.configure_build(manifest['build'],2)
    manifest['probe']['expected_json']=config.expected_probe(2)
    manifest['cpu_profile']=duration.PROFILE
    return manifest,values,pins


class ThreadedLongTests(unittest.TestCase):
    def test_actual_scalar_forecast_and_source_bound_shape(self):
        m,v,p=data();receipt=duration.assess(m,v,p,duration.HOST)
        self.assertEqual(receipt['shape'],duration.SHAPE)
        self.assertEqual(duration.ticks(100,2),3092161)
        self.assertEqual(duration.ticks(1000,11),29626294)
        self.assertLess(receipt['forecast']['overall_seconds_estimate'],4800)
        self.assertGreater(receipt['forecast']['continuous_command_seconds_estimate'],1800)
        self.assertFalse(receipt['native_1000_evidence'])
        self.assertEqual(len(receipt['forecast']['source_model_pins']),57)
        receipt['shape']['model_threads']=8
        self.assertEqual(duration.SHAPE['model_threads'],2)
        v['forecast']['pilot_pins']['pilot_report']='0'*64
        self.assertEqual(duration.PILOT_PINS['pilot_report'],p['pilot_report'])

    def test_forecast_raw_identity_finite_margin_and_type_changes_refused(self):
        for field,value in [('margin',1),('model_seconds_per_tick_upper_observed',float('nan')),
                            ('continuous_ticks',100),('promotion_allowed',0),
                            ('reference_replay_reserve_seconds',0),('continuous_command_seconds_estimate',100)]:
            m,v,p=data();v['forecast'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):duration.assess(m,v,p,duration.HOST)
        m,v,p=data();p['pilot_report']='0'*64
        with self.assertRaisesRegex(ValueError,'raw identities'):duration.assess(m,v,p,duration.HOST)

    def test_host_profile_compiled_source_corpus_probe_and_operation_changes_refused(self):
        for kind in ('host','profile','compiled','corpus','probe','threads','negative','chunk'):
            m,v,p=data()
            if kind=='host':m['host']='gfn16-pilot-c4d'
            elif kind=='profile':m['cpu_profile']='azure-burst16-static01-v1'
            elif kind=='compiled':m['sources'][m['build']['sv_sources'][0]]='0'*64
            elif kind=='corpus':m['sources']['soak/continuous.json']='0'*64
            elif kind=='probe':m['probe']['expected_json']['expected_threads']=True
            elif kind=='threads':m['build']['runtime_threads']=1
            elif kind=='negative':m['steps'][0]['validator']['config']['negative']='boundary'
            elif kind=='chunk':m['steps'][0]['argv'][-1]='{root}/soak/chunk-00.txt'
            with self.subTest(kind=kind),self.assertRaises(ValueError):duration.assess(m,v,p,duration.HOST)

    def test_pilot_actual_allocation_reference_cycle_changes_refused(self):
        for kind in ('allocation','limits','cycle','replay','probe'):
            m,v,p=data();r=v['pilot_report']
            if kind=='allocation':r['exact_build_identity']['identity']['runtime_allocation']['physical_cores']=[[0,2],[0,2]]
            elif kind=='limits':r['limits']['swap_max_bytes']=1
            elif kind=='cycle':r['validations']['soak-normal']['cycles']-=1
            elif kind=='replay':r['validations']['soak-normal']['independent_gmpy2_boundary_replay']=False
            elif kind=='probe':r['probe']['context_threads']=1
            with self.subTest(kind=kind),self.assertRaises(ValueError):duration.assess(m,v,p,duration.HOST)

    def test_generated_live_globals_file_profiles_and_fd_mutation(self):
        value=runner.parent(duration.PROFILE)
        for name in ('load_manifest','execute','check_sources','tools_for'):
            self.assertIs(getattr(value,name).__globals__,value.__dict__)
        self.assertEqual(set(value.PROFILES),{duration.HOST})
        self.assertEqual(value.SELF,runner.SELF)
        self.assertEqual(Path(value.__file__).name,'native_threaded_long_class_v1.py')
        value.LEASE_FDS=(101,102)
        self.assertEqual(value.execute.__globals__['LEASE_FDS'],(101,102))
        with self.assertRaises(ValueError):runner.profile('gcp-c4d-static23-v1')
        m,_,_=data();m['build']['runtime_threads']=1;m['build']['cflags'][-1]='-DGFN16_RUNTIME_THREADS=1'
        m['probe']['expected_json']=config.expected_probe(1)
        with self.assertRaisesRegex(ValueError,'must be two'):runner.validate_threaded(m)

    def test_real_unpacked_full_source_load_manifest_host_self_and_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary).resolve();root=base/'capture/source/fpga';output=base/'output'
            shutil.copytree(PILOT/'capture/source/fpga',root);output.mkdir()
            m=json.loads((PILOT/'manifest.json').read_text())
            for name in ('tools/native_threaded_duration_v1.py',runner.SELF):
                shutil.copyfile(ROOT/name,root/name);m['sources'][name]=sha(root/name)
            m.update(source_root=str(root),output_parent=str(output))
            path=base/'manifest.json';path.write_text(json.dumps(m));pin=sha(path)
            value=runner.parent(duration.PROFILE)
            selected=dict(runner.profile(duration.PROFILE),base=str(base))
            value.PROFILES={duration.HOST:selected};value.__file__=str(root/runner.SELF)
            with patch.object(value.socket,'gethostname',return_value=duration.HOST):
                accepted,_,_=value.load_manifest(path,pin)
                self.assertEqual(accepted,m)
            with patch.object(value.socket,'gethostname',return_value='wrong-host'):
                with self.assertRaisesRegex(ValueError,'explicit approved native host'):value.load_manifest(path,pin)
            value.__file__=str(root/'tools/native_threaded_class_v1.py')
            with patch.object(value.socket,'gethostname',return_value=duration.HOST):
                with self.assertRaisesRegex(ValueError,'launcher inside pinned snapshot'):value.load_manifest(path,pin)
            value.__file__=str(root/runner.SELF);(root/runner.SELF).write_text('source drift')
            with patch.object(value.socket,'gethostname',return_value=duration.HOST):
                with self.assertRaisesRegex(ValueError,'source pin/type drift'):value.load_manifest(path,pin)

    def test_only_exact_duration_anchors_change_proven_executor(self):
        raw=runner.base.source_policy().host.static_module().pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
        text=runner.adapted_source(raw,runner.profile(duration.PROFILE));ast.parse(text)
        self.assertIn("4500 if name == LONG_RECEIPT['model_step'] else 1800",text)
        self.assertIn("time.monotonic() - started < 4800",text)
        for preserved in ("pass_fds=LEASE_FDS + ((lock.fileno(),)",
            "fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)",
            "'--build', '-Wall', '-Wno-fatal', '-j', '2', '--threads', str(config['runtime_threads'])",
            'check_scratch_quota(scratch, used, inodes, profile)',
            'guard_protected(profile); guard(); begin =',
            'exact_build_identity=identity.build_identity(manifest, profile)',
            'native_child_usage=child.resource_receipt()'):
            self.assertIn(preserved,text)
        self.assertNotIn('ResourcePool',text);self.assertNotIn('CompileSlots',text)
        for name,pin in runner.dependencies().items():self.assertEqual(sha(ROOT/name),pin)

    def test_actual_closed_evidence_validation_drift_shape_and_path(self):
        m,values,_=data()
        originals=dict(pilot_manifest=PILOT/'manifest.json',pilot_report=NATIVE/'report.json',
            pilot_gate=ROOT/'results/throughput-20260929/core27-t5b-soak-thread100-native-v1/native-gate.json')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();folder=root/'duration';folder.mkdir();evidence={}
            for key in duration.EVIDENCE:
                name='duration/'+key+'.json';target=root/name
                if key=='forecast':target.write_text(json.dumps(values[key],indent=2)+'\n')
                else:shutil.copyfile(originals[key],target)
                pin=sha(target);m['sources'][name]=pin;evidence[key]=dict(path=name,sha256=pin)
            m['runtime_duration']=dict(shape=copy.deepcopy(duration.SHAPE),contract_sha256=duration.contract(m),evidence=evidence)
            self.assertEqual(duration.validate(m,root,duration.HOST)['shape'],duration.SHAPE)
            bad=copy.deepcopy(m);bad['runtime_duration']['shape']['outer_seconds']=5000.0
            with self.assertRaisesRegex(ValueError,'typed closed shape'):duration.validate(bad,root,duration.HOST)
            bad=copy.deepcopy(m);bad['runtime_duration']['evidence']['forecast']['path']='../forecast.json'
            with self.assertRaisesRegex(ValueError,'relative evidence'):duration.validate(bad,root,duration.HOST)
            (folder/'forecast.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'source-closed duration evidence'):duration.validate(m,root,duration.HOST)


if __name__=='__main__':unittest.main()

"""Read-only actual C2 metadata; no candidate import, GMP or model execution."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from fpga.tools import native_long_class_v2 as runtime

ROOT=Path(__file__).resolve().parents[1]
ROLE=ROOT/'artifacts/s4-p16-c2-explicit-continuous1000-role-v1'
PILOT=ROOT/'artifacts/s4-p16-c2-explicit-own100-threadpilot-v1/packet-815'
NATIVE=ROOT/'queue/evidence/s4-p16-c2-explicit-own100-threadpilot-q2-v1'


class C2LongTests(unittest.TestCase):
    def fixture(self):
        paths=dict(forecast=ROLE/'forecast.json',pilot_manifest=PILOT/'manifest.json',
            pilot_report=NATIVE/'attempt-0/collected/output/native/report.json',
            pilot_gate=NATIVE/'gate-receipt.json')
        return (json.loads((ROLE/'manifest.json').read_text()),
            {k:json.loads(p.read_text()) for k,p in paths.items()},
            {k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()})

    def test_real_raw_role_assessment_uses_own_eight_thread_policy(self):
        m,v,p=self.fixture()
        self.assertNotIn('cpu_profile',m)
        got=runtime.duration_for(8).assess(m,v,p,'gfn16-azure-sim-f32')
        self.assertEqual(got['shape']['model_threads'],8)
        self.assertEqual(got['model_step'],runtime.C2_STEP)
        self.assertAlmostEqual(got['model_seconds_estimate'],2479.583882300012)
        self.assertAlmostEqual(got['overall_seconds_estimate'],3433.0724904160197)
        self.assertFalse(got['promotion_allowed'])
        for count in (1,4):
            with self.subTest(count=count),self.assertRaises(ValueError):
                runtime.duration_for(count).assess(m,v,p,'gfn16-azure-sim-f32')

    def test_exact_scalar_header_delta_and_no_candidate_import(self):
        before=(PILOT/'capture/source/fpga'/runtime.C2_HEADER).read_bytes()
        after=(ROLE/'source/fpga'/runtime.C2_HEADER).read_bytes()
        original=runtime.importlib.util.spec_from_file_location
        def framework_only(name,path,*args,**kwargs):
            self.assertNotEqual(Path(path).name,Path(runtime.C2_HELPER).name)
            return original(name,path,*args,**kwargs)
        with patch.object(runtime.importlib.util,'spec_from_file_location',side_effect=framework_only):
            scalar=runtime.c2_scalar_functions()
            self.assertEqual(scalar['header'](before),after)
            self.assertEqual(scalar['config']()['doubles'],1022)
            self.assertEqual([r[:100] for r in scalar['bits']()],scalar['bits'](100))
            m,v,p=self.fixture()
            runtime.duration_for(8).assess(m,v,p,'gfn16-azure-sim-f32')
        self.assertNotIn(runtime.C2_HELPER,runtime.PINS)
        for key,pin in runtime.C2_HEADER_DELTA.items():
            if key.endswith('sha256'):
                self.assertEqual(hashlib.sha256(before if key.startswith('pilot') else after).hexdigest(),pin)

    def test_c2_wrong_source_header_runtime_measurement_and_shape_reject(self):
        base,values,pins=self.fixture()
        changes={
            'host':lambda m,v,p:v['pilot_report'].update(host='gfn16-pilot-c4d'),
            'source':lambda m,v,p:m['sources'].update({runtime.C2_CPP:'0'*64}),
            'header':lambda m,v,p:m['sources'].update({runtime.C2_HEADER:'0'*64}),
            'old_header':lambda m,v,p:v['pilot_manifest']['sources'].update({runtime.C2_HEADER:'0'*64}),
            'helper':lambda m,v,p:m['sources'].update({runtime.C2_HELPER:'0'*64}),
            'proof':lambda m,v,p:v['forecast'].update(generator_sha256='0'*64),
            'pins':lambda m,v,p:p.update(pilot_manifest='0'*64),
            'typed':lambda m,v,p:v['pilot_gate']['steps'][0].update(typed_validator_sha256='0'*64),
            'threads':lambda m,v,p:m['probe']['expected_json'].update(model_threads=1),
            'profile':lambda m,v,p:m.update(cpu_profile='azure-burst16-thread-wide07-v1'),
            'quota':lambda m,v,p:m['fixed_execution']['runtime_allocation'].update(cpu_quota_percent=200),
            'physical':lambda m,v,p:m['fixed_execution']['runtime_allocation']['physical_cores'].__setitem__(1,[0,8]),
            'memory':lambda m,v,p:m['fixed_execution']['runtime_allocation'].update(memory_bytes=4<<30),
            'swap':lambda m,v,p:v['pilot_report']['limits'].update(swap_max_bytes=1),
            'validator':lambda m,v,p:m['steps'][0]['validator'].update(source=runtime.C2_PILOT_VALIDATOR),
            'count':lambda m,v,p:m['steps'][0]['validator']['config'].update(count=100),
            'double':lambda m,v,p:m['steps'][0]['validator']['config'].update(doubles=1021),
            'argv':lambda m,v,p:m['steps'][0].update(argv=['{exe}','1000']),
            'extra_step':lambda m,v,p:m['steps'].append(copy.deepcopy(m['steps'][0])),
            'parameters':lambda m,v,p:m['build']['parameters'].update(CONTEXTS=1),
            'bool_parameter':lambda m,v,p:m['build']['parameters'].update(COLD_LAUNCH_FENCE=True),
            'reset':lambda m,v,p:m['r84']['continuous'].update(initial_resets=2),
            'load':lambda m,v,p:m['r84']['continuous'].update(initial_load_words=65536),
            'reload':lambda m,v,p:m['r84']['continuous'].update(no_reload_or_checkpoint_barrier=False),
            'outcome':lambda m,v,p:v['pilot_gate'].update(status='FAIL'),
            'forecast':lambda m,v,p:v['forecast']['forecast'].update(overall_seconds_estimate=1),
            'infinite':lambda m,v,p:v['pilot_report'].update(seconds=float('inf')),
            'nan':lambda m,v,p:v['pilot_report']['steps'][-1].update(seconds=float('nan')),
            'promotion':lambda m,v,p:v['pilot_gate'].update(promotion_allowed=True),
        }
        for name,mutate in changes.items():
            m,v,p=copy.deepcopy((base,values,pins));mutate(m,v,p)
            with self.subTest(change=name),self.assertRaises((ValueError,KeyError)):
                runtime.duration_for(8).assess(m,v,p,'gfn16-azure-sim-f32')

    def test_even_coherently_changed_pilot_boundary_calendar_rejects(self):
        base,values,pins=self.fixture()
        for name in ('count_per_context','doubles','initial_resets','reads','joint_cycles','overlap_edges','launches','setup_edges','warm_edges','done_edges'):
            m,v,p=copy.deepcopy((base,values,pins))
            for native in (v['pilot_gate']['steps'][0]['validation'],
                           v['pilot_report']['validations'][runtime.C2_PILOT_STEP],
                           v['forecast']['pilot_native_validation']):
                value=native['measurements'][name]
                if isinstance(value,list):
                    if isinstance(value[0],list):value[0][0]+=1
                    else:value[0]+=1
                else:native['measurements'][name]+=1
            with self.subTest(field=name),self.assertRaises(ValueError):
                runtime.duration_for(8).assess(m,v,p,'gfn16-azure-sim-f32')


class TimingC2LongTests(unittest.TestCase):
    def fixture(self):
        base=ROOT/'results/throughput-20260929/trackS-c2-timing-v1'
        native=ROOT/'queue/evidence/s4-p16-c2-timing-own100-threadpilot-q1-v1'
        paths=dict(forecast=base/'continuous1000-role-v1/forecast.json',
            pilot_manifest=base/'own100-threadpilot-v1/packet-815/manifest.json',
            pilot_report=native/'attempt-0/collected/output/native/report.json',pilot_gate=native/'gate-receipt.json')
        return (json.loads((base/'continuous1000-role-v1/manifest.json').read_text()),
            {k:json.loads(p.read_text()) for k,p in paths.items()},
            {k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()})

    def test_actual_timing_pilot_forecast_and_independent_full_calendar(self):
        m,v,p=self.fixture()
        got=runtime.duration_for(8).assess(m,v,p,'gfn16-azure-sim-f32')
        self.assertAlmostEqual(got['model_seconds_estimate'],2582.033923052568)
        self.assertAlmostEqual(got['overall_seconds_estimate'],3513.2323871910685)
        self.assertEqual(got['model_step'],'normal-full-c2-timing-continuous1000-percontext')
        family=runtime.c2_source_family(v['forecast'])
        self.assertEqual(family['source_family'],'timing58')
        self.assertEqual(len(m['build']['sv_sources']),59)
        self.assertEqual(family['interval'],8460)
        for model,count in ((m,1000),(v['pilot_manifest'],100)):
            calendar=runtime.c2_timing_calendar(model['context_timing']['calendar']['geometry'],count)
            self.assertEqual(calendar,model['context_timing']['own_long']['own_calendar'])
            self.assertEqual(calendar['lease_peak'],3)
            self.assertEqual(calendar['correction'][2]['margin'],30)
        for count in (1,4):
            with self.subTest(count=count),self.assertRaises(ValueError):
                runtime.duration_for(count).assess(m,v,p,'gfn16-azure-sim-f32')

    def test_exact_header_extension_four_scalar_asts_not_candidate_import(self):
        m,v,p=self.fixture();family=runtime.c2_source_family(v['forecast'])
        base=ROOT/'results/throughput-20260929/trackS-c2-timing-v1'
        before=(base/'own100-threadpilot-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        after=(base/'continuous1000-role-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        original=runtime.importlib.util.spec_from_file_location
        def framework_only(name,path,*args,**kwargs):
            self.assertNotIn(Path(path).name,(Path(runtime.C2_TIMING_HELPER).name,Path(runtime.C2_TIMING_VALIDATOR).name))
            return original(name,path,*args,**kwargs)
        with patch.object(runtime.importlib.util,'spec_from_file_location',side_effect=framework_only):
            scalar=runtime.c2_scalar_functions(family)
            self.assertEqual(scalar['header'](before),after)
            self.assertEqual(scalar['config'](),m['steps'][0]['validator']['config'])
            runtime.duration_for(8).assess(m,v,p,'gfn16-azure-sim-f32')
        self.assertNotIn(runtime.C2_TIMING_HELPER,runtime.PINS)
        self.assertNotIn(runtime.C2_TIMING_VALIDATOR,runtime.PINS)

    def test_source_runtime_cohort_and_calendar_mutations_reject(self):
        m,v,p=self.fixture()
        changes=[('m',('sources',runtime.C2_CPP),'0'*64),
            ('m',('sources',runtime.C2_TIMING_HELPER),'0'*64),
            ('m',('sources',runtime.C2_TIMING_VALIDATOR),'0'*64),
            ('m',('sources',runtime.C2_HEADER),runtime.C2_HEADER_DELTA['full_sha256']),
            ('m',('build','parameters','CONTEXTS'),1),
            ('m',('probe','expected_json','model_threads'),4),
            ('m',('steps',0,'validator','config','interval'),8459),
            ('m',('steps',0,'validator','config','count'),100),
            ('m',('steps',0,'validator','config','doubles'),1021),
            ('m',('steps',0,'validator','source'),runtime.C2_HELPER),
            ('m',('steps',0,'argv'),['{exe}','1000']),
            ('m',('fixed_execution','runtime_allocation','cpu_quota_percent'),200),
            ('m',('fixed_execution','runtime_allocation','memory_bytes'),4<<30),
            ('m',('r84','continuous','initial_resets'),2),
            ('m',('r84','continuous','no_reload_or_checkpoint_barrier'),False),
            ('m',('context_timing','calendar','geometry','warm_interval'),8459),
            ('m',('context_timing','own_long','count_per_context'),100),
            ('m',('context_timing','own_long','old_pilot_forecast_used'),True),
            ('m',('context_timing','own_long','own_calendar','frames'),200),
            ('m',('context_timing','own_long','own_calendar','lease_peak'),4),
            ('m',('context_timing','own_long','own_calendar','correction',2,'margin'),31),
            ('m',('context_timing','own_long','own_calendar','lease_allocation',2,3),0),
            ('v',('forecast','generator'),runtime.C2_HELPER),
            ('v',('forecast','allowed_compiled_delta','full_sha256'),'0'*64),
            ('v',('forecast','forecast','overall_seconds_estimate'),1),
            ('v',('pilot_report','seconds'),float('inf')),
            ('v',('pilot_gate','status'),'FAIL'),
            ('v',('pilot_gate','steps',0,'typed_validator_sha256'),runtime.C2_PILOT_TYPED_PIN),
            ('p',('pilot_manifest',),runtime.C2_EVIDENCE_PINS['pilot_manifest'])]
        for label,path,value in changes:
            a,b,c=copy.deepcopy((m,v,p));target={'m':a,'v':b,'p':c}[label]
            for key in path[:-1]:target=target[key]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.duration_for(8).assess(a,b,c,'gfn16-azure-sim-f32')

    def test_coherent_wrong_actual_source_calendar_rejects(self):
        m,v,p=self.fixture();step='normal-full-c2-timing-own100-percontext-threadpilot'
        for name in ('interval','joint_cycles','overlap_edges','warm_edges','done_edges','launches'):
            a,b,c=copy.deepcopy((m,v,p))
            for native in (b['pilot_gate']['steps'][0]['validation'],b['pilot_report']['validations'][step],
                           b['forecast']['pilot_native_validation']):
                value=native['measurements'][name]
                if isinstance(value,list):
                    if isinstance(value[0],list):value[0][0]+=1
                    else:value[0]+=1
                else:native['measurements'][name]+=1
            with self.subTest(field=name),self.assertRaises(ValueError):
                runtime.duration_for(8).assess(a,b,c,'gfn16-azure-sim-f32')

    def test_source_own_compiler_peak_allows_four_not_eight(self):
        m,v,p=self.fixture()
        m['runtime_duration']=dict(evidence=dict(pilot_report=dict(sha256=p['pilot_report'])))
        four=runtime.compilation_bound(m,v['pilot_report'],4)
        self.assertEqual(four['compiler_peak_rss_bytes'],1416852*1024)
        self.assertLess(four['estimated_peak_bytes'],8<<30)
        for count in (5,8,True):
            with self.subTest(count=count),self.assertRaises(ValueError):
                runtime.compilation_bound(m,v['pilot_report'],count)


class SerialAllocationTests(unittest.TestCase):
    """Existing serial resource seam only; this is not a new source admission."""
    def fixture(self):
        base=ROOT/'results/throughput-20260929/trackS-c2-timing-storage2-v1/own100-serial-v1'
        pilot=json.loads((base/'packet-01/manifest.json').read_text())
        report=json.loads((ROOT/'queue/evidence/s4-p16-c2-timing-storage2-own100-serial-q1-v1/attempt-0/collected/output/native/report.json').read_text())
        self.assertEqual(hashlib.sha256((base/'packet-01/manifest.json').read_bytes()).hexdigest(),report['manifest_sha256'])
        # Allocator consumes raw or placed roles; source-family admission is
        # separate and still demands its own immutable helper/pilot/forecast.
        return {'build':copy.deepcopy(pilot['build'])},pilot,report

    def test_actual_gcp_serial_pair_not_azure_wide(self):
        m,p,r=self.fixture()
        runtime.c2_allocation(m,p,r,1)
        m['cpu_profile']='gcp-c4d-static23-v1'
        runtime.c2_allocation(m,p,r,1)
        self.assertEqual(r['model_threads'],1)
        for count in (4,8):
            with self.subTest(count=count),self.assertRaises((ValueError,KeyError)):
                runtime.c2_allocation(m,p,r,count)

    def test_serial_resource_and_inherited_wide_metadata_refusals(self):
        base,pilot,report=self.fixture()
        changes=[('m',('fixed_execution',),{}),('m',('wide_thread_pilot',),{}),
            ('m',('compile_allocation',),{}),('m',('cpu_profile',),'azure-burst16-thread-wide815-v1'),
            ('m',('cpu_profile',),'gcp-c4d-static24g01-v1'),
            ('r',('host',),'gfn16-azure-sim-f32'),('r',('compile_workers',),4),
            ('r',('limits','physical_cores'),[[0,0],[0,0]]),('r',('limits','affinity'),[0,4]),
            ('r',('limits','cpu_max'),['800000','100000']),('r',('limits','memory_max_bytes'),4<<30),
            ('r',('limits','swap_max_bytes'),1)]
        for label,path,value in changes:
            m,p,r=copy.deepcopy((base,pilot,report));target={'m':m,'p':p,'r':r}[label]
            for key in path[:-1]:target=target[key]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.c2_allocation(m,p,r,1)

    def test_original8459_calendar_is_not_timing8460(self):
        m=json.loads((ROOT/'artifacts/s4-p16-c2-explicit-own100-threadpilot-v1/manifest-815.json').read_text())
        geometry=m['r84']['geometry']
        for count in (100,1000):
            proof=runtime.c2_frame_calendar(geometry,count,8459)
            self.assertEqual(proof['frames'],2*count)
            self.assertEqual(proof['per_context_interval'],8459)
            self.assertEqual(proof['launch_gaps'],[4229,4230])
            self.assertEqual(proof['lease_peak'],3)
            self.assertEqual(proof['correction'][2]['margin'],31)
        with self.assertRaises(ValueError):runtime.c2_frame_calendar(geometry,1000,8460)
        for key in ('warm_interval','carry_done','first_digit','term_seed_first','correction_cache_latency','last_sink'):
            bad=copy.deepcopy(geometry);bad[key]+=1
            with self.subTest(key=key),self.assertRaises(ValueError):runtime.c2_frame_calendar(bad,1000,8459)


if __name__=='__main__':unittest.main()

"""Read-only actual C2 metadata; no candidate import, GMP or model execution."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
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


class OriginalStorageC2LongTests(unittest.TestCase):
    def fixture(self):
        base=ROOT/'results/throughput-20260929/trackS-c2-storage2-ownlong-v1'
        native=ROOT/'queue/evidence/s4-p16-c2-storage2-own100-serial-q1-v1'
        paths=dict(forecast=base/'continuous1000-role-v1/forecast.json',
            pilot_manifest=base/'own100-serial-v1/packet-01/manifest.json',
            pilot_report=native/'attempt-0/collected/output/native/report.json',pilot_gate=native/'gate-receipt.json')
        return (json.loads((base/'continuous1000-role-v1/manifest.json').read_text()),
            {k:json.loads(p.read_text()) for k,p in paths.items()},
            {k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()})

    def test_actual_own_original_serial_forecast_and_complete_calendar(self):
        m,v,p=self.fixture()
        got=runtime.assess(m,v,p,'gfn16-pilot-c4d')
        self.assertAlmostEqual(got['model_seconds_estimate'],5205.015155497531)
        self.assertAlmostEqual(got['overall_seconds_estimate'],6149.698724071262)
        self.assertEqual(got['shape']['model_threads'],1)
        self.assertEqual(got['model_step'],'normal-full-c2-storage2-continuous1000-percontext')
        self.assertFalse(got['promotion_allowed'])
        self.assertNotIn('fixed_execution',m)
        for model,count in ((m,1000),(v['pilot_manifest'],100)):
            self.assertEqual(runtime.c2_frame_calendar(model['storage2']['geometry'],count,8459),
                             model['storage2']['own_long']['own_calendar'])
        for count in (4,8):
            with self.subTest(count=count),self.assertRaises(ValueError):
                runtime.duration_for(count).assess(m,v,p,'gfn16-pilot-c4d')

    def test_actual_header_delta_and_no_private_candidate_import(self):
        m,v,p=self.fixture();family=runtime.c2_source_family(v['forecast'])
        base=ROOT/'results/throughput-20260929/trackS-c2-storage2-ownlong-v1'
        before=(base/'own100-serial-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        after=(base/'continuous1000-role-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        original=runtime.importlib.util.spec_from_file_location
        def framework_only(name,path,*args,**kwargs):
            self.assertNotIn(Path(path).name,(Path(runtime.C2_STORAGE_HELPER).name,Path(runtime.C2_STORAGE_VALIDATOR).name))
            return original(name,path,*args,**kwargs)
        with patch.object(runtime.importlib.util,'spec_from_file_location',side_effect=framework_only):
            scalar=runtime.c2_scalar_functions(family)
            self.assertEqual(scalar['header'](before),after)
            self.assertEqual(scalar['config'](),m['steps'][0]['validator']['config'])
            runtime.assess(m,v,p,'gfn16-pilot-c4d')
        self.assertNotIn(runtime.C2_STORAGE_HELPER,runtime.PINS)

    def test_original_source_calendar_thread_and_forecast_negatives(self):
        m,v,p=self.fixture()
        changes=[('m',('build','runtime_threads'),8),('m',('build','runtime_threads'),True),
            ('m',('probe','expected_json','model_threads'),8),
            ('m',('build','cflags'),m['build']['cflags']+['-DGFN16_RUNTIME_THREADS=8']),
            ('m',('sources',runtime.C2_STORAGE_HELPER),'0'*64),
            ('m',('sources',runtime.C2_STORAGE_VALIDATOR),'0'*64),
            ('m',('storage2','geometry','warm_interval'),8460),
            ('m',('storage2','own_long','prior_forecast_used'),True),
            ('m',('storage2','own_long','own_calendar','frames'),200),
            ('m',('storage2','own_long','own_calendar','launch_gaps'),[4230,4230]),
            ('m',('storage2','production_generated_sha256','genefer_sdp_ram32.sv'),'0'*64),
            ('m',('r84','continuous','model_threads'),8),
            ('m',('r84','continuous','no_reload_or_checkpoint_barrier'),False),
            ('v',('forecast','generator'),runtime.C2_TIMING_HELPER),
            ('v',('forecast','forecast','overall_seconds_estimate'),1),
            ('v',('pilot_gate','steps',0,'typed_validator_sha256'),'0'*64),
            ('v',('pilot_report','limits','cpu_max'),['800000','100000']),
            ('v',('pilot_report','host'),'gfn16-azure-sim-f32'),
            ('p',('pilot_report',),runtime.C2_EVIDENCE_PINS['pilot_report'])]
        for label,path,value in changes:
            a,b,c=copy.deepcopy((m,v,p));target={'m':a,'v':b,'p':c}[label]
            for key in path[:-1]:target=target[key]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.assess(a,b,c,'gfn16-pilot-c4d')

    def test_actual_bind_dual_serial_safe_stage_and_equal_functional_identity(self):
        from fpga.tools import native_long_package_v3 as package,native_long_stage_v3 as stage
        from fpga.tools import native_profile_variants_v14 as checker
        from fpga.tools.candidate_ladder import budget_from_hourly
        base=ROOT/'results/throughput-20260929/trackS-c2-storage2-ownlong-v1'
        native=ROOT/'queue/evidence/s4-p16-c2-storage2-own100-serial-q1-v1'
        evidence=dict(forecast=base/'continuous1000-role-v1/forecast.json',
            pilot_manifest=base/'own100-serial-v1/packet-01/manifest.json',
            pilot_report=native/'attempt-0/collected/output/native/report.json',pilot_gate=native/'gate-receipt.json')
        original=(base/'continuous1000-role-v1/manifest.json').read_bytes()
        with tempfile.TemporaryDirectory(prefix='original-storage2-long-metadata-') as temp:
            out=Path(temp).resolve();bound=out/'bound'
            result=package.bind_role(base/'continuous1000-role-v1/manifest.json',base/'continuous1000-role-v1/source/fpga',
                evidence,bound,host='gfn16-pilot-c4d')
            self.assertEqual(result['admission']['shape']['model_threads'],1)
            budget=out/'budget.json';budget.write_text(json.dumps(budget_from_hourly()))
            fingerprints=[]
            for profile,cpus in (('gcp-c4d-static01-v1',[0,1]),('gcp-c4d-static23-v1',[2,3])):
                dest=out/profile
                prepared=package.prepare(bound/'manifest.json',bound/'source/fpga',profile,
                    'metadata-only-original-'+profile,'run',dest,budget)
                _,ticket,m,placed=stage.worker().inspect_archive(dest/'package.tar.gz',
                    prepared['archive_sha256'],prepared['ticket_sha256'])
                # Future long-only family tests must not publish a changed
                # live ordinary-intake checker before atomic adoption.
                family=(package.EXECUTOR_SHA,stage.PACKAGE_SHA)
                with patch.object(checker,'LONG_FAMILIES',checker.LONG_FAMILIES|{family}),\
                     patch.dict(checker.LONG_PHASES,{family:runtime.PHASE_PIN}):
                    fingerprints.append(checker.functional_fingerprint(m,ticket['budget'],dest/'capture/source/fpga')['sha256'])
                self.assertEqual(placed['cpus'],cpus)
                self.assertEqual(placed['memory_bytes'],8<<30)
                self.assertEqual(ticket['runtime_duration']['model_threads'],1)
                self.assertEqual(ticket['max_seconds'],10800)
                self.assertEqual(len(m['build']['sv_sources']),54)
                self.assertNotIn('fixed_execution',m)
                runtime.duration.validate(m,dest/'capture/source/fpga','gfn16-pilot-c4d')
            self.assertEqual(fingerprints[0],fingerprints[1])
        self.assertEqual((base/'continuous1000-role-v1/manifest.json').read_bytes(),original)


class ComboStorageC2LongTests(unittest.TestCase):
    """Actual source/receipt metadata only; no candidate arithmetic import."""
    def fixture(self):
        base=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-ownlong-v1'
        native=ROOT/'queue/evidence/s4-p16-c2-combo-own100-serial-q1-v1'
        paths=dict(forecast=base/'continuous1000-measured-v1/forecast.json',
            pilot_manifest=native/'attempt-0/collected/output/native/approved-manifest.json',
            pilot_report=native/'attempt-0/collected/output/native/report.json',pilot_gate=native/'gate-receipt.json')
        return (json.loads((base/'continuous1000-measured-v1/manifest.json').read_text()),
            {k:json.loads(p.read_text()) for k,p in paths.items()},
            {k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()})

    def test_actual_combo_own_pilot_source_calendar_and_duration(self):
        m,v,p=self.fixture()
        got=runtime.assess(m,v,p,'gfn16-pilot-c4d')
        self.assertEqual(got['model_step'],'normal-full-c2-combo-continuous1000-percontext')
        self.assertEqual(got['shape']['model_threads'],1)
        self.assertFalse(got['promotion_allowed'])
        self.assertAlmostEqual(got['model_seconds_estimate'],v['forecast']['forecast']['continuous_command_seconds_estimate'])
        self.assertAlmostEqual(got['overall_seconds_estimate'],v['forecast']['forecast']['overall_seconds_estimate'])
        for model,count in ((m,1000),(v['pilot_manifest'],100)):
            self.assertEqual(runtime.c2_frame_calendar(model['context_storage_combo']['geometry'],count,8459),
                             model['context_storage_combo']['own_long']['own_calendar'])

    def test_exact_combo_header_scalar_source_and_no_candidate_import(self):
        m,v,p=self.fixture();family=runtime.c2_source_family(v['forecast'])
        base=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-ownlong-v1'
        before=(base/'own100-serial-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        after=(base/'continuous1000-source-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        original=runtime.importlib.util.spec_from_file_location
        def framework_only(name,path,*args,**kwargs):
            self.assertNotIn(Path(path).name,(Path(runtime.C2_COMBO_HELPER).name,Path(runtime.C2_COMBO_VALIDATOR).name))
            return original(name,path,*args,**kwargs)
        with patch.object(runtime.importlib.util,'spec_from_file_location',side_effect=framework_only):
            self.assertEqual(runtime.c2_scalar_functions(family)['header'](before),after)
            runtime.assess(m,v,p,'gfn16-pilot-c4d')
        self.assertNotIn(runtime.C2_COMBO_HELPER,runtime.PINS)

    def test_combo_source_family_and_receipt_substitution_refuse(self):
        m,v,p=self.fixture()
        changes=[('m',('context_storage_combo','geometry','warm_interval'),8460),
            ('m',('context_storage_combo','own_long','prior_forecast_used'),True),
            ('m',('context_storage_combo','own_long','own_calendar','frames'),200),
            ('m',('sources',runtime.C2_COMBO_HELPER),'0'*64),
            ('m',('sources',runtime.C2_COMBO_VALIDATOR),'0'*64),
            ('m',('build','runtime_threads'),8),
            ('v',('forecast','generator'),runtime.C2_STORAGE_HELPER),
            ('v',('pilot_gate','steps',0,'typed_validator_sha256'),
                runtime.C2_FAMILIES[runtime.C2_STORAGE_HELPER]['typed_pin']),
            ('p',('pilot_manifest',),runtime.C2_FAMILIES[runtime.C2_STORAGE_HELPER]['evidence_pins']['pilot_manifest'])]
        for label,path,value in changes:
            a,b,c=copy.deepcopy((m,v,p));target={'m':a,'v':b,'p':c}[label]
            for key in path[:-1]:target=target[key]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.assess(a,b,c,'gfn16-pilot-c4d')


class R2BoundaryC2LongTests(unittest.TestCase):
    """Actual R2 source/own-pilot metadata; no numerical/oracle rerun."""
    def fixture(self):
        base=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-boundary-ownlong-v1'
        native=ROOT/'queue/evidence/s4-p16-c2-combo-r2-own100-serial-q1-v1'
        paths=dict(forecast=base/'continuous1000-measured-v1/forecast.json',
            pilot_manifest=native/'attempt-0/collected/output/native/approved-manifest.json',
            pilot_report=native/'attempt-0/collected/output/native/report.json',pilot_gate=native/'gate-receipt.json')
        return (json.loads((base/'continuous1000-measured-v1/manifest.json').read_text()),
            {k:json.loads(p.read_text()) for k,p in paths.items()},
            {k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()})

    def test_actual_r2_source_calendar_and_own_measured_admission_shape(self):
        m,v,p=self.fixture();got=runtime.assess(m,v,p,'gfn16-pilot-c4d')
        self.assertEqual(got['shape']['model_threads'],1)
        self.assertEqual(got['model_step'],'normal-full-c2-combo-r2-continuous1000-percontext')
        self.assertFalse(got['promotion_allowed'])
        self.assertEqual(len(m['build']['sv_sources']),55)
        for model,count in ((m,1000),(v['pilot_manifest'],100)):
            group=model['context_storage_combo_boundary']
            self.assertEqual(runtime.c2_frame_calendar(group['geometry'],count,8459,boundary_inputreg=1),
                             group['own_long']['own_calendar'])

    def test_exact_r2_header_only_delta_and_four_scalar_asts(self):
        m,v,p=self.fixture();family=runtime.c2_source_family(v['forecast'])
        base=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-boundary-ownlong-v1'
        before=(base/'own100-serial-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        after=(base/'continuous1000-source-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        self.assertEqual(runtime.c2_scalar_functions(family)['header'](before),after)
        self.assertNotIn(runtime.C2_R2_HELPER,runtime.PINS)
        self.assertNotIn(runtime.C2_R2_VALIDATOR,runtime.PINS)

    def test_parent_source_pilot_and_seed_cache_substitution_refuse(self):
        m,v,p=self.fixture()
        changes=[('m',('build','parameters','BOUNDARY_INPUTREG'),0),
            ('m',('build','parameters','BOUNDARY_INPUTREG'),True),
            ('m',('context_storage_combo_boundary','geometry','correction_cache_latency'),77),
            ('m',('context_storage_combo_boundary','geometry','term_seed_first'),70),
            ('m',('context_storage_combo_boundary','geometry','boundary_frontend_added'),1),
            ('m',('context_storage_combo_boundary','own_long','prior_forecast_used'),True),
            ('m',('sources',runtime.C2_R2_HELPER),'0'*64),
            ('m',('sources',runtime.C2_R2_VALIDATOR),'0'*64),
            ('v',('forecast','generator'),runtime.C2_COMBO_HELPER),
            ('v',('pilot_gate','steps',0,'typed_validator_sha256'),
                runtime.C2_FAMILIES[runtime.C2_COMBO_HELPER]['typed_pin']),
            ('v',('pilot_report','sources',runtime.C2_CPP),'0'*64),
            ('p',('pilot_manifest',),runtime.C2_FAMILIES[runtime.C2_COMBO_HELPER]['evidence_pins']['pilot_manifest'])]
        for label,path,value in changes:
            a,b,c=copy.deepcopy((m,v,p));target={'m':a,'v':b,'p':c}[label]
            for key in path[:-1]:target=target[key]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.assess(a,b,c,'gfn16-pilot-c4d')


class R3QuarantineC2LongTests(unittest.TestCase):
    """Own immutable R3 pilot/forecast; no candidate arithmetic execution."""
    BASE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-quarantine-ownlong-v1'
    NATIVE=ROOT/'queue/evidence/s4-p16-c2-combo-r3-own100-serial-q1-v1'

    def paths(self):
        return dict(forecast=self.BASE/'continuous1000-measured-v1/forecast.json',
            pilot_manifest=self.NATIVE/'attempt-0/collected/output/native/approved-manifest.json',
            pilot_report=self.NATIVE/'attempt-0/collected/output/native/report.json',
            pilot_gate=self.NATIVE/'gate-receipt.json')

    def fixture(self):
        paths=self.paths()
        return (json.loads((self.BASE/'continuous1000-measured-v1/manifest.json').read_text()),
            {k:json.loads(p.read_text()) for k,p in paths.items()},
            {k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()})

    def test_actual_quarantine_source_calendar_and_own_duration(self):
        m,v,p=self.fixture();got=runtime.assess(m,v,p,'gfn16-pilot-c4d')
        self.assertEqual(got['model_step'],'normal-full-c2-combo-r3-continuous1000-percontext')
        self.assertEqual(got['shape']['model_threads'],1)
        self.assertFalse(got['promotion_allowed'])
        self.assertEqual(len(m['build']['sv_sources']),56)
        self.assertAlmostEqual(got['model_seconds_estimate'],4453.79968981495)
        self.assertAlmostEqual(got['overall_seconds_estimate'],5480.826726891464)
        for model,count in ((m,1000),(v['pilot_manifest'],100)):
            group=model['context_storage_combo_quarantine']
            self.assertEqual(runtime.c2_frame_calendar(group['geometry'],count,8459,boundary_inputreg=1),
                             group['own_long']['own_calendar'])

    def test_exact_own_header_and_only_four_scalar_asts(self):
        m,v,p=self.fixture();family=runtime.c2_source_family(v['forecast'])
        before=(self.BASE/'own100-serial-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        after=(self.BASE/'continuous1000-source-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        original=runtime.importlib.util.spec_from_file_location
        def framework_only(name,path,*args,**kwargs):
            self.assertNotIn(Path(path).name,(Path(runtime.C2_R3_HELPER).name,Path(runtime.C2_R3_VALIDATOR).name))
            return original(name,path,*args,**kwargs)
        with patch.object(runtime.importlib.util,'spec_from_file_location',side_effect=framework_only):
            self.assertEqual(runtime.c2_scalar_functions(family)['header'](before),after)
            runtime.assess(m,v,p,'gfn16-pilot-c4d')
        self.assertNotIn(runtime.C2_R3_HELPER,runtime.PINS)
        self.assertNotIn(runtime.C2_R3_VALIDATOR,runtime.PINS)

    def test_predecessor_pilot_and_quarantine_calendar_substitution_refuse(self):
        m,v,p=self.fixture();key='context_storage_combo_quarantine'
        changes=[('m',('build','parameters','QUARANTINE_REPLICAS'),0),
            ('m',('build','parameters','QUARANTINE_REPLICAS'),True),
            ('m',(key,'geometry','correction_cache_latency'),77),
            ('m',(key,'geometry','term_seed_first'),70),
            ('m',(key,'geometry','boundary_frontend_added'),1),
            ('m',(key,'own_long','prior_forecast_used'),True),
            ('m',(key,'own_long','own_calendar','frames'),200),
            ('m',('sources',runtime.C2_R3_HELPER),'0'*64),
            ('m',('sources',runtime.C2_R3_VALIDATOR),'0'*64),
            ('m',('build','runtime_threads'),8),
            ('v',('forecast','generator'),runtime.C2_R2_HELPER),
            ('v',('pilot_gate','steps',0,'typed_validator_sha256'),
                runtime.C2_FAMILIES[runtime.C2_R2_HELPER]['typed_pin']),
            ('v',('pilot_report','sources',runtime.C2_CPP),'0'*64),
            ('p',('pilot_manifest',),runtime.C2_FAMILIES[runtime.C2_R2_HELPER]['evidence_pins']['pilot_manifest'])]
        for label,path,value in changes:
            a,b,c=copy.deepcopy((m,v,p));target={'m':a,'v':b,'p':c}[label]
            for name in path[:-1]:target=target[name]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.assess(a,b,c,'gfn16-pilot-c4d')

    def test_actual_bound_dual_gcp_safe_stage_equal_identity(self):
        from fpga.tools import native_long_package_v3 as package,native_long_stage_v3 as stage
        from fpga.tools import native_profile_variants_v14 as checker
        from fpga.tools.candidate_ladder import budget_from_hourly
        original=(self.BASE/'continuous1000-measured-v1/manifest.json').read_bytes()
        with tempfile.TemporaryDirectory(prefix='r3-long-metadata-') as temporary:
            out=Path(temporary).resolve();bound=out/'bound'
            result=package.bind_role(self.BASE/'continuous1000-measured-v1/manifest.json',
                self.BASE/'continuous1000-measured-v1/source/fpga',self.paths(),bound,host='gfn16-pilot-c4d')
            self.assertEqual(result['admission']['shape']['model_threads'],1)
            budget=out/'budget.json';budget.write_text(json.dumps(budget_from_hourly()))
            fingerprints=[]
            for profile,cpus in (('gcp-c4d-static01-v1',[0,1]),('gcp-c4d-static23-v1',[2,3])):
                dest=out/profile
                prepared=package.prepare(bound/'manifest.json',bound/'source/fpga',profile,
                    'metadata-r3-'+profile,'run',dest,budget)
                _,ticket,manifest,placed=stage.worker().inspect_archive(dest/'package.tar.gz',
                    prepared['archive_sha256'],prepared['ticket_sha256'])
                family=(package.EXECUTOR_SHA,stage.PACKAGE_SHA)
                with patch.object(checker,'LONG_FAMILIES',checker.LONG_FAMILIES|{family}), \
                     patch.dict(checker.LONG_PHASES,{family:runtime.PHASE_PIN}):
                    fingerprints.append(checker.functional_fingerprint(manifest,ticket['budget'],dest/'capture/source/fpga')['sha256'])
                self.assertEqual(placed['cpus'],cpus)
                self.assertEqual(placed['memory_bytes'],8<<30)
                self.assertEqual(len(manifest['build']['sv_sources']),56)
                self.assertEqual(ticket['max_seconds'],10800)
                self.assertNotIn('fixed_execution',manifest)
                runtime.duration.validate(manifest,dest/'capture/source/fpga','gfn16-pilot-c4d')
            self.assertEqual(fingerprints[0],fingerprints[1])
        self.assertEqual((self.BASE/'continuous1000-measured-v1/manifest.json').read_bytes(),original)


class R4ReadlocalC2LongTests(unittest.TestCase):
    """Own read-local source/evidence only; no predecessor forecast replay."""
    BASE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-readlocal-ownlong-v1'
    NATIVE=ROOT/'queue/evidence/s4-p16-c2-combo-r4-own100-serial-q1-v1'

    def paths(self):
        return dict(forecast=self.BASE/'continuous1000-bound-v1/forecast.json',
            pilot_manifest=self.NATIVE/'attempt-0/collected/output/native/approved-manifest.json',
            pilot_report=self.NATIVE/'attempt-0/collected/output/native/report.json',
            pilot_gate=self.NATIVE/'gate-receipt.json')

    def fixture(self):
        paths=self.paths()
        return (json.loads((self.BASE/'continuous1000-bound-v1/manifest.json').read_text()),
            {k:json.loads(p.read_text()) for k,p in paths.items()},
            {k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()})

    def test_actual_readlocal_source_calendar_and_own_duration(self):
        m,v,p=self.fixture();got=runtime.assess(m,v,p,'gfn16-pilot-c4d')
        self.assertEqual(got['model_step'],'normal-full-c2-combo-r4-continuous1000-percontext')
        self.assertEqual(got['shape']['model_threads'],1)
        self.assertFalse(got['promotion_allowed'])
        self.assertEqual(len(m['build']['sv_sources']),56)
        self.assertAlmostEqual(got['model_seconds_estimate'],4609.000053209784)
        self.assertAlmostEqual(got['overall_seconds_estimate'],5526.481784773328)
        for model,count in ((m,1000),(v['pilot_manifest'],100)):
            group=model['context_storage_combo_readlocal']
            self.assertEqual(runtime.c2_frame_calendar(group['geometry'],count,8459,boundary_inputreg=1),
                             group['own_long']['own_calendar'])

    def test_header_only_delta_and_no_candidate_module_import(self):
        m,v,p=self.fixture();family=runtime.c2_source_family(v['forecast'])
        before=(self.BASE/'own100-serial-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        after=(self.BASE/'continuous1000-bound-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        original=runtime.importlib.util.spec_from_file_location
        def framework_only(name,path,*args,**kwargs):
            self.assertNotIn(Path(path).name,(Path(runtime.C2_R4_HELPER).name,Path(runtime.C2_R4_VALIDATOR).name))
            return original(name,path,*args,**kwargs)
        with patch.object(runtime.importlib.util,'spec_from_file_location',side_effect=framework_only):
            self.assertEqual(runtime.c2_scalar_functions(family)['header'](before),after)
            runtime.assess(m,v,p,'gfn16-pilot-c4d')
        self.assertNotIn(runtime.C2_R4_HELPER,runtime.PINS)
        self.assertNotIn(runtime.C2_R4_VALIDATOR,runtime.PINS)

    def test_predecessor_evidence_and_literal_readlocal_substitution_refuse(self):
        m,v,p=self.fixture();key='context_storage_combo_readlocal'
        changes=[('m',('build','parameters','CANONICAL_READ_LOCAL'),0),
            ('m',('build','parameters','CANONICAL_READ_LOCAL'),True),
            ('m',('build','parameters','QUARANTINE_REPLICAS'),0),
            ('m',(key,'geometry','correction_cache_latency'),77),
            ('m',(key,'geometry','boundary_frontend_added'),1),
            ('m',(key,'own_long','prior_forecast_used'),True),
            ('m',(key,'own_long','own_calendar','frames'),200),
            ('m',('sources',runtime.C2_R4_HELPER),'0'*64),
            ('m',('sources',runtime.C2_R4_VALIDATOR),'0'*64),
            ('m',('build','runtime_threads'),8),
            ('v',('forecast','generator'),runtime.C2_R3_HELPER),
            ('v',('pilot_gate','steps',0,'typed_validator_sha256'),
                runtime.C2_FAMILIES[runtime.C2_R3_HELPER]['typed_pin']),
            ('v',('pilot_report','sources',runtime.C2_CPP),'0'*64),
            ('p',('pilot_manifest',),runtime.C2_FAMILIES[runtime.C2_R3_HELPER]['evidence_pins']['pilot_manifest'])]
        for label,path,value in changes:
            a,b,c=copy.deepcopy((m,v,p));target={'m':a,'v':b,'p':c}[label]
            for name in path[:-1]:target=target[name]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.assess(a,b,c,'gfn16-pilot-c4d')

    def test_actual_bound_dual_gcp_stage_and_equal_functional_identity(self):
        from fpga.tools import native_long_package_v3 as package,native_long_stage_v3 as stage
        from fpga.tools import native_profile_variants_v14 as checker
        from fpga.tools.candidate_ladder import budget_from_hourly
        original=(self.BASE/'continuous1000-bound-v1/manifest.json').read_bytes()
        with tempfile.TemporaryDirectory(prefix='r4-long-metadata-') as temporary:
            out=Path(temporary).resolve();bound=out/'bound'
            result=package.bind_role(self.BASE/'continuous1000-bound-v1/manifest.json',
                self.BASE/'continuous1000-bound-v1/source/fpga',self.paths(),bound,host='gfn16-pilot-c4d')
            self.assertEqual(result['admission']['shape']['model_threads'],1)
            budget=out/'budget.json';budget.write_text(json.dumps(budget_from_hourly()))
            fingerprints=[]
            for profile,cpus in (('gcp-c4d-static01-v1',[0,1]),('gcp-c4d-static23-v1',[2,3])):
                dest=out/profile
                prepared=package.prepare(bound/'manifest.json',bound/'source/fpga',profile,
                    'metadata-r4-'+profile,'run',dest,budget)
                _,ticket,manifest,placed=stage.worker().inspect_archive(dest/'package.tar.gz',
                    prepared['archive_sha256'],prepared['ticket_sha256'])
                family=(package.EXECUTOR_SHA,stage.PACKAGE_SHA)
                with patch.object(checker,'LONG_FAMILIES',checker.LONG_FAMILIES|{family}), \
                     patch.dict(checker.LONG_PHASES,{family:runtime.PHASE_PIN}):
                    fingerprints.append(checker.functional_fingerprint(manifest,ticket['budget'],dest/'capture/source/fpga')['sha256'])
                self.assertEqual(placed['cpus'],cpus)
                self.assertEqual(placed['memory_bytes'],8<<30)
                self.assertEqual(len(manifest['build']['sv_sources']),56)
                self.assertEqual(ticket['max_seconds'],10800)
                self.assertNotIn('fixed_execution',manifest)
                runtime.duration.validate(manifest,dest/'capture/source/fpga','gfn16-pilot-c4d')
            self.assertEqual(fingerprints[0],fingerprints[1])
        self.assertEqual((self.BASE/'continuous1000-bound-v1/manifest.json').read_bytes(),original)


class R6OneshotC2LongTests(unittest.TestCase):
    """Own accepted-one-shot source; never qualify the recurring old trigger."""
    BASE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-oneshot-ownlong-v1'
    NATIVE=ROOT/'queue/evidence/s4-p16-c2-combo-r6-own100-serial-q1-v1'
    HELPER='reference/stream27_context_storage_combo_oneshot_continuous.py'
    VALIDATOR='reference/stream27_context_storage_combo_oneshot_long_native.py'
    HELPER_PIN='4e1a08cbb907769b399a76e8391f9c9085324628f2121aaeb796542d639ce6c0'
    VALIDATOR_PIN='1f062db5c3128f964c9608d8aba56a78a1159ebfe98d0f51c7e432737c495d48'
    FULL_DIR='continuous1000-source-v1'
    CONTEXT_KEY='context_storage_combo_oneshot'
    SOURCE_FAMILY='storage2-combo-oneshot55'
    STEP='normal-full-c2-combo-r6-continuous1000-percontext'
    COMMAND_ESTIMATE=4473.310481727123
    OVERALL_ESTIMATE=5391.070489509073
    PARAMETERS=dict(runtime.C2_PARAMETERS,BOUNDARY_INPUTREG=1,QUARANTINE_REPLICAS=1,
        CANONICAL_READ_LOCAL=1,CANONICAL_LOAD_LOCAL=1,COLD_SECOND_ONESHOT=1)
    CPP=runtime.C2_CPP
    SV_COUNT=56

    def source_models(self):
        return [json.loads((self.BASE/name/'manifest.json').read_text())
                for name in ('own100-serial-v1',self.FULL_DIR)]

    def paths(self):
        return dict(forecast=self.BASE/'continuous1000-measured-v1/forecast.json',
            pilot_manifest=self.NATIVE/'attempt-0/collected/output/native/approved-manifest.json',
            pilot_report=self.NATIVE/'attempt-0/collected/output/native/report.json',
            pilot_gate=self.NATIVE/'gate-receipt.json')

    def fixture(self):
        paths=self.paths()
        return (json.loads((self.BASE/'continuous1000-measured-v1/manifest.json').read_text()),
            {k:json.loads(p.read_text()) for k,p in paths.items()},
            {k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()})

    def test_actual_oneshot_source_pilot_and_own_measured_forecast(self):
        m,v,p=self.fixture();got=runtime.assess(m,v,p,'gfn16-pilot-c4d')
        self.assertEqual(got['model_step'],self.STEP)
        self.assertEqual(got['shape']['model_threads'],1)
        self.assertFalse(got['promotion_allowed'])
        self.assertAlmostEqual(got['model_seconds_estimate'],self.COMMAND_ESTIMATE)
        self.assertAlmostEqual(got['overall_seconds_estimate'],self.OVERALL_ESTIMATE)
        self.assertEqual(runtime.c2_source_family(v['forecast'])['source_family'],self.SOURCE_FAMILY)
        original=runtime.importlib.util.spec_from_file_location
        def framework_only(name,path,*args,**kwargs):
            self.assertNotIn(Path(path).name,(Path(self.HELPER).name,Path(self.VALIDATOR).name))
            return original(name,path,*args,**kwargs)
        with patch.object(runtime.importlib.util,'spec_from_file_location',side_effect=framework_only):
            runtime.assess(m,v,p,'gfn16-pilot-c4d')

    def test_old_trigger_source_evidence_and_false_oneshot_reject(self):
        m,v,p=self.fixture();key=self.CONTEXT_KEY
        changes=[('m',('build','parameters','COLD_SECOND_ONESHOT'),0),
            ('m',('build','parameters','COLD_SECOND_ONESHOT'),True),
            ('m',('build','parameters','CANONICAL_LOAD_LOCAL'),0),
            ('m',('build','parameters','CANONICAL_READ_LOCAL'),0),
            ('m',(key,'geometry','correction_cache_latency'),77),
            ('m',(key,'geometry','boundary_frontend_added'),1),
            ('m',(key,'own_long','prior_forecast_used'),True),
            ('m',(key,'own_long','own_calendar','frames'),200),
            ('m',('sources',self.HELPER),'0'*64),
            ('m',('sources',self.VALIDATOR),'0'*64),
            ('m',('build','runtime_threads'),8),
            ('v',('forecast','generator'),runtime.C2_R4_HELPER),
            ('v',('pilot_gate','steps',0,'typed_validator_sha256'),
                runtime.C2_FAMILIES[runtime.C2_R4_HELPER]['typed_pin']),
            ('v',('pilot_report','sources',self.CPP),'0'*64),
            ('v',('pilot_gate','steps',0,'validation','measurements','joint_cycles'),2234665),
            ('p',('pilot_manifest',),runtime.C2_FAMILIES[runtime.C2_R4_HELPER]['evidence_pins']['pilot_manifest'])]
        for label,path,value in changes:
            a,b,c=copy.deepcopy((m,v,p));target={'m':a,'v':b,'p':c}[label]
            for name in path[:-1]:target=target[name]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.assess(a,b,c,'gfn16-pilot-c4d')
        self.assertNotIn('reference/stream27_context_storage_combo_loadlocal_continuous.py',runtime.C2_FAMILIES)

    def test_actual_bind_dual_gcp_safe_stage_and_equal_identity(self):
        from fpga.tools import native_long_package_v3 as package,native_long_stage_v3 as stage
        from fpga.tools import native_profile_variants_v14 as checker
        from fpga.tools.candidate_ladder import budget_from_hourly
        original=(self.BASE/'continuous1000-measured-v1/manifest.json').read_bytes()
        with tempfile.TemporaryDirectory(prefix='r6-long-metadata-') as temporary:
            out=Path(temporary).resolve();bound=out/'bound'
            result=package.bind_role(self.BASE/'continuous1000-measured-v1/manifest.json',
                self.BASE/'continuous1000-measured-v1/source/fpga',self.paths(),bound,host='gfn16-pilot-c4d')
            self.assertEqual(result['admission']['shape']['model_threads'],1)
            budget=out/'budget.json';budget.write_text(json.dumps(budget_from_hourly()))
            fingerprints=[]
            for profile,cpus in (('gcp-c4d-static01-v1',[0,1]),('gcp-c4d-static23-v1',[2,3])):
                dest=out/profile
                prepared=package.prepare(bound/'manifest.json',bound/'source/fpga',profile,
                    'metadata-r6-'+profile,'run',dest,budget)
                _,ticket,manifest,placed=stage.worker().inspect_archive(dest/'package.tar.gz',
                    prepared['archive_sha256'],prepared['ticket_sha256'])
                family=(package.EXECUTOR_SHA,stage.PACKAGE_SHA)
                with patch.object(checker,'LONG_FAMILIES',checker.LONG_FAMILIES|{family}), \
                     patch.dict(checker.LONG_PHASES,{family:runtime.PHASE_PIN}):
                    fingerprints.append(checker.functional_fingerprint(manifest,ticket['budget'],dest/'capture/source/fpga')['sha256'])
                self.assertEqual(placed['cpus'],cpus)
                self.assertEqual(placed['memory_bytes'],8<<30)
                self.assertEqual(len(manifest['build']['sv_sources']),self.SV_COUNT)
                self.assertEqual(ticket['max_seconds'],10800)
                self.assertNotIn('fixed_execution',manifest)
                runtime.duration.validate(manifest,dest/'capture/source/fpga','gfn16-pilot-c4d')
                self.assertEqual(manifest['sources'][self.HELPER],self.HELPER_PIN)
                self.assertEqual(manifest['sources'][self.VALIDATOR],self.VALIDATOR_PIN)
            self.assertEqual(fingerprints[0],fingerprints[1])
        self.assertEqual((self.BASE/'continuous1000-measured-v1/manifest.json').read_bytes(),original)

    def test_previous_captured_r4_packages_still_have_equal_fingerprints(self):
        from fpga.tools import native_profile_variants_v14 as checker
        base=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-readlocal-ownlong-v1/continuous1000-long-packet-v1'
        fingerprints=[]
        for name in ('packet-01','packet-23'):
            directory=base/name
            manifest=json.loads((directory/'manifest.json').read_text())
            ticket=json.loads((directory/'ticket.json').read_text())
            family=tuple(manifest['sources'][rel] for rel in
                ('tools/native_long_class_v2.py','tools/native_long_package_v3.py'))
            self.assertEqual(family,checker.PRE_R6_C2_LONG)
            self.assertIn(family,checker.LONG_FAMILIES)
            self.assertEqual(checker.LONG_PHASES[family],runtime.PHASE_PIN)
            fingerprints.append(checker.functional_fingerprint(manifest,ticket['budget'],
                directory/'capture/source/fpga')['sha256'])
        self.assertEqual(fingerprints[0],fingerprints[1])

    def test_captured_source_header_scalar_asts_and_no_module_import(self):
        pilot,full=self.source_models()
        family=dict(helper=self.HELPER,helper_pin=self.HELPER_PIN,threads=1)
        original=runtime.importlib.util.spec_from_file_location
        def framework_only(name,path,*args,**kwargs):
            self.assertNotIn(Path(path).name,(Path(self.HELPER).name,Path(self.VALIDATOR).name))
            return original(name,path,*args,**kwargs)
        before=(self.BASE/'own100-serial-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        after=(self.BASE/self.FULL_DIR/'source/fpga'/runtime.C2_HEADER).read_bytes()
        with patch.object(runtime.importlib.util,'spec_from_file_location',side_effect=framework_only):
            scalar=runtime.c2_scalar_functions(family)
            self.assertEqual(scalar['header'](before),after)
            self.assertEqual(scalar['config'](),full['steps'][0]['validator']['config'])
        self.assertNotIn(self.HELPER,runtime.PINS)
        self.assertNotIn(self.VALIDATOR,runtime.PINS)
        compiled=set(full['build']['sv_sources'])|{self.CPP,
            'rtl/tb/native_runtime_context_v1.h','rtl/tb/stream27_host_chain_full_reference_v1.h',
            'rtl/tb/stream27_shared_reference_ntt_v1.h'}
        self.assertTrue(all(pilot['sources'][name]==full['sources'][name] for name in compiled))
        for name,model in (('own100-serial-v1',pilot),(self.FULL_DIR,full)):
            source=self.BASE/name/'source/fpga'
            self.assertTrue(all(hashlib.sha256((source/rel).read_bytes()).hexdigest()==pin
                                for rel,pin in model['sources'].items()))
            self.assertEqual(model['sources'][self.VALIDATOR],self.VALIDATOR_PIN)
        self.assertEqual(full['sources'][self.HELPER],self.HELPER_PIN)

    def test_literal_oneshot_flags_and_independent_source_calendar(self):
        pilot,full=self.source_models()
        expected=self.PARAMETERS
        for model,count in ((pilot,100),(full,1000)):
            self.assertEqual(model['build']['parameters'],expected)
            self.assertTrue(all(type(value) is int for value in model['build']['parameters'].values()))
            self.assertEqual(model['build']['runtime_threads'],1)
            self.assertEqual(len(model['build']['sv_sources']),56)
            group=model[self.CONTEXT_KEY]
            self.assertEqual(len(group['production_generated_sha256']),55)
            self.assertEqual(runtime.c2_frame_calendar(group['geometry'],count,8459,boundary_inputreg=1),
                             group['own_long']['own_calendar'])
            self.assertFalse(group['own_long']['prior_forecast_used'])
            self.assertEqual(group['own_long']['initial_resets'],1)
            self.assertEqual(group['own_long']['initial_load_words'],131072)
            self.assertEqual(group['own_long']['descriptors'],2*(count-1))


class R7FaultlocalC2LongTests(R6OneshotC2LongTests):
    """Repeat the same strict checks on R7's own source, pilot and forecast."""
    BASE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-faultlocal-ownlong-v1'
    NATIVE=ROOT/'queue/evidence/s4-p16-c2-combo-r7-own100-serial-q1-v1'
    HELPER='reference/stream27_context_storage_combo_faultlocal_continuous.py'
    VALIDATOR='reference/stream27_context_storage_combo_faultlocal_long_native.py'
    HELPER_PIN='3515ce1045a322a6f429f307e6f6ca286fdd332bcce0f5d126a67e762eac97e2'
    VALIDATOR_PIN='3199615c75830616fda22a086657fa5398ca8a90776f51109de658bc16ba4162'
    FULL_DIR='continuous1000-measured-v1'
    CONTEXT_KEY='context_storage_combo_faultlocal'
    SOURCE_FAMILY='storage2-combo-faultlocal55'
    STEP='normal-full-c2-combo-r7-continuous1000-percontext'
    COMMAND_ESTIMATE=4317.635033477309
    OVERALL_ESTIMATE=5240.443927887096
    PARAMETERS=dict(R6OneshotC2LongTests.PARAMETERS,COMM_OWNER_COMPARE_LOCAL=1)

    def test_r6_substitution_and_false_local_compare_reject(self):
        m,v,p=self.fixture()
        changes=[('m',('build','parameters','COMM_OWNER_COMPARE_LOCAL'),0),
            ('m',('build','parameters','COMM_OWNER_COMPARE_LOCAL'),True),
            ('m',('build','parameters','COLD_SECOND_ONESHOT'),0),
            ('v',('forecast','generator'),runtime.C2_R6_HELPER),
            ('v',('forecast','generator_sha256'),runtime.C2_FAMILIES[runtime.C2_R6_HELPER]['helper_pin']),
            ('v',('pilot_gate','steps',0,'typed_validator_sha256'),runtime.C2_FAMILIES[runtime.C2_R6_HELPER]['typed_pin']),
            ('p',('pilot_report',),runtime.C2_FAMILIES[runtime.C2_R6_HELPER]['evidence_pins']['pilot_report'])]
        for label,path,value in changes:
            a,b,c=copy.deepcopy((m,v,p));target={'m':a,'v':b,'p':c}[label]
            for name in path[:-1]:target=target[name]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.assess(a,b,c,'gfn16-pilot-c4d')

    def test_captured_r6_dual_packages_remain_accepted(self):
        from fpga.tools import native_profile_variants_v14 as checker
        base=R6OneshotC2LongTests.BASE/'continuous1000-packet-v1'
        fingerprints=[]
        for name in ('packet-01','packet-23'):
            directory=base/name
            manifest=json.loads((directory/'manifest.json').read_text())
            ticket=json.loads((directory/'ticket.json').read_text())
            family=tuple(manifest['sources'][rel] for rel in
                ('tools/native_long_class_v2.py','tools/native_long_package_v3.py'))
            self.assertIn(family,checker.LONG_FAMILIES)
            self.assertEqual(checker.LONG_PHASES[family],runtime.PHASE_PIN)
            fingerprints.append(checker.functional_fingerprint(manifest,ticket['budget'],
                directory/'capture/source/fpga')['sha256'])
        self.assertEqual(fingerprints[0],fingerprints[1])


class R9RegisteredErrorC2LongTests(R6OneshotC2LongTests):
    """Own CPP/publication-fence calendar and pilot, never PUB0 inheritance."""
    BASE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-registerederror-ownlong-v1'
    NATIVE=ROOT/'queue/evidence/s4-p16-c2-combo-r9-own100-serial-q1-v1'
    HELPER='reference/stream27_context_storage_combo_registerederror_continuous.py'
    VALIDATOR='reference/stream27_context_storage_combo_registerederror_long_native.py'
    HELPER_PIN='d537b22f007232a26d18f1e1a5412a35c4e290441f1741a8439897d099ed310a'
    VALIDATOR_PIN='474a65104c92d6cfe7fcb980dbcaa23b93ce4a925bcf35d76d287e5ed3ae4628'
    FULL_DIR='continuous1000-measured-v1'
    CONTEXT_KEY='context_registered_error'
    SOURCE_FAMILY='storage2-combo-registerederror55'
    STEP='normal-full-c2-combo-r9-continuous1000-percontext'
    COMMAND_ESTIMATE=4204.281430352457
    OVERALL_ESTIMATE=5124.462425584461
    PARAMETERS=dict(R7FaultlocalC2LongTests.PARAMETERS,CANONICAL_C0_DIRECT=1,ERROR_AGGREGATION_REGISTERED=1)
    CPP=runtime.C2_R9_CPP

    def test_exact_cpp_only_copy_cost_delta_and_explicit_context(self):
        before=(R7FaultlocalC2LongTests.BASE/'own100-serial-v1/source/fpga'/runtime.C2_CPP).read_bytes()
        after=(self.BASE/'own100-serial-v1/source/fpga'/self.CPP).read_bytes()
        marker=b'==N+3,"R84_REAL_CANONICAL_COPY_COST"'
        self.assertEqual(before.count(marker),1)
        self.assertEqual(before.replace(marker,b'==N+4,"R84_REAL_CANONICAL_COPY_COST"'),after)
        self.assertEqual(hashlib.sha256(after).hexdigest(),runtime.C2_FAMILIES[self.HELPER]['cpp_pin'])
        self.assertRegex(after.decode(),r'VerilatedContext context;gfn16_runtime::configure\(context,argc,argv\);DUT d\{&context\};')
        self.assertEqual(after.count(b'DUT d{&context}'),1)

    def test_source_specific_publication_fence_both_jobs_not_warm_time(self):
        m,v,p=self.fixture();warm=v['pilot_gate']['steps'][0]['validation']['measurements']['warm_edges']
        old,oldjoint=runtime.c2_publication_edges(warm)
        done,joint=runtime.c2_publication_edges(warm,1)
        self.assertEqual(done,[old[0]+1,old[1]+2])
        self.assertEqual((done,joint),([1509668,2169132],2234668))
        self.assertEqual(joint,oldjoint+2)
        launches=[[first+k*8459 for k in range(1000)] for first in (204,4433)]
        longwarm=[row[-1]+12558 for row in launches]
        self.assertEqual(runtime.c2_publication_edges(longwarm,1),([9122768,9782232],9847768))
        for selector in (True,-1,2):
            with self.subTest(selector=selector),self.assertRaises(ValueError):
                runtime.c2_publication_edges(warm,selector)

    def test_wrong_cpp_pub0_context_or_r7_receipts_refuse(self):
        m,v,p=self.fixture();key=self.CONTEXT_KEY
        changes=[('m',('build','cpp_source'),runtime.C2_CPP),
            ('m',('sources',self.CPP),runtime.C2_CPP_PIN),
            ('m',('build','parameters','ERROR_AGGREGATION_REGISTERED'),0),
            ('m',('build','parameters','CANONICAL_C0_DIRECT'),True),
            ('m',('steps',0,'validator','config','publication_fence_edges'),0),
            ('m',(key,'runtime_context_explicitly_configured_before_every_model'),False),
            ('m',(key,'own_long','runtime_context_explicit_before_every_model'),False),
            ('m',(key,'own_long','publication_fence_edges_per_job'),0),
            ('m',(key,'own_long','copy_cost_edges'),65539),
            ('m',(key,'own_long','normal_cpp_donor_pin'),'0'*64),
            ('v',('forecast','generator'),runtime.C2_R7_HELPER),
            ('v',('pilot_gate','steps',0,'typed_validator_sha256'),runtime.C2_FAMILIES[runtime.C2_R7_HELPER]['typed_pin']),
            ('p',('pilot_report',),runtime.C2_FAMILIES[runtime.C2_R7_HELPER]['evidence_pins']['pilot_report'])]
        for label,path,value in changes:
            a,b,c=copy.deepcopy((m,v,p));target={'m':a,'v':b,'p':c}[label]
            for name in path[:-1]:target=target[name]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.assess(a,b,c,'gfn16-pilot-c4d')

    def test_captured_r7_packages_keep_cpp_and_pub0_identity(self):
        from fpga.tools import native_profile_variants_v14 as checker
        base=R7FaultlocalC2LongTests.BASE/'continuous1000-packet-v1'
        fingerprints=[]
        for name in ('packet-01','packet-23'):
            directory=base/name
            manifest=json.loads((directory/'manifest.json').read_text())
            ticket=json.loads((directory/'ticket.json').read_text())
            family=tuple(manifest['sources'][rel] for rel in
                ('tools/native_long_class_v2.py','tools/native_long_package_v3.py'))
            self.assertIn(family,checker.LONG_FAMILIES)
            self.assertEqual(checker.LONG_PHASES[family],runtime.PHASE_PIN)
            self.assertEqual(manifest['build']['cpp_source'],runtime.C2_CPP)
            self.assertNotIn('publication_fence_edges',manifest['steps'][0]['validator']['config'])
            fingerprints.append(checker.functional_fingerprint(manifest,ticket['budget'],
                directory/'capture/source/fpga')['sha256'])
        self.assertEqual(fingerprints[0],fingerprints[1])


class R10TimingLeanC2LongTests(R9RegisteredErrorC2LongTests):
    """Own inverse-only I8460 source calendar/serial pilot, not a composed rate."""
    BASE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-timing10-ownlong-v1'
    NATIVE=ROOT/'queue/evidence/s4-p16-c2-combo-r10-own100-serial-q1-v1'
    HELPER='reference/stream27_context_storage_combo_timing10_continuous.py'
    VALIDATOR='reference/stream27_context_storage_combo_timing10_long_native.py'
    HELPER_PIN='ba414fd196133e1543b5c5392a4c89af095ad40364bfad9763d22fd435188bca'
    VALIDATOR_PIN='d07064ecff5f93b1dc1887a3edb5462b740f01a5bd93a8cd503dea4ed14b253c'
    FULL_DIR='continuous1000-measured-v1'
    CONTEXT_KEY='context_timing10'
    SOURCE_FAMILY='storage2-combo-timing10-58'
    STEP='normal-full-c2-combo-r10-continuous1000-percontext'
    COMMAND_ESTIMATE=4440.349083275069
    OVERALL_ESTIMATE=5380.5961513328075
    PARAMETERS=runtime.C2_FAMILIES[runtime.C2_R10_HELPER]['parameters']
    CPP=runtime.C2_R10_CPP
    SV_COUNT=59

    def test_literal_oneshot_flags_and_independent_source_calendar(self):
        for model,count in zip(self.source_models(),(100,1000)):
            self.assertEqual(model['build']['parameters'],self.PARAMETERS)
            self.assertEqual(len(model['build']['sv_sources']),59)
            group=model[self.CONTEXT_KEY];g=group['geometry']
            self.assertEqual(len(group['production_generated_sha256']),58)
            self.assertEqual((g['warm_interval'],g['first_digit'],g['carry_done'],g['sink_accept'],g['last_sink']),
                             (8460,8459,12558,8417,12512))
            self.assertEqual((g['correction_cache_latency'],g['term_seed_first'],g['term_seed_last']),
                             (78,71,74))
            self.assertEqual(runtime.c2_frame_calendar(g,count,8460,1,1),group['own_long']['own_calendar'])
            for key in ('lean_production','host_GL_assumed_unimplemented'):
                self.assertIs(group[key],True);self.assertIs(group['own_long'][key],True)
            self.assertIs(group['protected_fault_rollback_claim'],False)
            self.assertFalse(group['own_long']['prior_forecast_used'])

    def test_source_specific_publication_fence_both_jobs_not_warm_time(self):
        m,v,p=self.fixture();warm=v['pilot_gate']['steps'][0]['validation']['measurements']['warm_edges']
        self.assertEqual(warm,[850303,854533])
        old,oldjoint=runtime.c2_publication_edges(warm)
        done,joint=runtime.c2_publication_edges(warm,1)
        self.assertEqual((done,joint),([1509768,2169232],2234768))
        self.assertEqual((done[0]-old[0],done[1]-old[1],joint-oldjoint),(1,2,2))
        launches=[[first+k*8460 for k in range(1000)] for first in (204,4434)]
        longwarm=[row[-1]+12559 for row in launches]
        self.assertEqual(runtime.c2_publication_edges(longwarm,1),([9123768,9783232],9848768))
        got=runtime.assess(m,v,p,'gfn16-pilot-c4d')
        self.assertEqual(got['build_label'],runtime.C2_LEAN_LABEL)
        self.assertFalse(got['host_gl_implemented']);self.assertFalse(got['rollback_implemented'])

    def test_exact_captured_inverse_geometry_ast_preserves_cache_and_seed(self):
        source=self.BASE/self.FULL_DIR/'source/fpga'
        raw=(source/runtime.C2_R10_INVERSE_SOURCE).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),runtime.C2_R10_INVERSE_PIN)
        nodes=[n for n in runtime.ast.parse(raw).body if isinstance(n,runtime.ast.FunctionDef) and n.name=='inverse_geometry']
        self.assertEqual(len(nodes),1)
        namespace=dict(field=runtime.types.SimpleNamespace(need=runtime.duration.need))
        exec(compile(runtime.ast.Module(body=nodes,type_ignores=[]),'[source-only inverse calendar]','exec'),namespace)
        before=json.loads((R9RegisteredErrorC2LongTests.BASE/'continuous1000-measured-v1/manifest.json').read_text())['context_registered_error']['geometry']
        full=self.source_models()[1];g=full[self.CONTEXT_KEY]['geometry']
        derived=namespace['inverse_geometry'](before)
        self.assertEqual(derived,g)
        self.assertEqual((derived['pointwise_accept'],derived['correction_cache_latency'],derived['term_seed_first'],derived['term_seed_last']),
                         (4207,78,71,74))
        self.assertEqual(derived['next_cache_capture'],12636)
        self.assertEqual(derived['cache_margin'],30)

    def test_cache79_naive_composition_source_substitution_and_protected_scope_refuse(self):
        m,v,p=self.fixture();key=self.CONTEXT_KEY
        changes=[('m',(key,'geometry','correction_cache_latency'),79),
            ('m',(key,'geometry','term_seed_first'),72),
            ('m',(key,'geometry','final_gs_inputreg'),0),
            ('m',(key,'source_sha256','reference/stream27_timing_flags.py'),'0'*64),
            ('m',('sources',runtime.C2_R10_INVERSE_SOURCE),'0'*64),
            ('m',('sources',runtime.C2_R10_BIND_SOURCE),'0'*64),
            ('m',('build','parameters','FINAL_GS_INPUTREG'),0),
            ('m',('steps',0,'validator','config','lean_production'),False),
            ('m',(key,'host_GL_assumed_unimplemented'),False),
            ('m',(key,'own_long','protected_fault_rollback_claim'),True),
            ('v',('forecast','generator'),runtime.C2_R9_HELPER),
            ('p',('pilot_report',),runtime.C2_FAMILIES[runtime.C2_R9_HELPER]['evidence_pins']['pilot_report'])]
        for label,path,value in changes:
            a,b,c=copy.deepcopy((m,v,p));target={'m':a,'v':b,'p':c}[label]
            for name in path[:-1]:target=target[name]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.assess(a,b,c,'gfn16-pilot-c4d')
        g=m[key]['geometry']
        for selector in (True,-1,2):
            with self.subTest(selector=selector),self.assertRaises(ValueError):
                runtime.c2_frame_calendar(g,100,8460,1,selector)
        with self.assertRaises(ValueError):runtime.c2_frame_calendar(g,100,8460,1,0)

    def test_captured_lean_packet_stays_source_exact(self):
        from fpga.tools import native_profile_variants_v14 as checker
        base=ROOT/'results/throughput-20260929/trackS-c2-lean-r7-ownlong-v1/long-package-v1'
        fingerprints=[]
        for name in ('packet-01','packet-23'):
            directory=base/name;m=json.loads((directory/'manifest.json').read_text());t=json.loads((directory/'ticket.json').read_text())
            family=tuple(m['sources'][rel] for rel in ('tools/native_long_class_v2.py','tools/native_long_package_v3.py'))
            self.assertEqual(family,('3838f3fbefdc22c911e1a48d4f22211cde30aefc67cd607d15e15c32dc18c57d','7a05779457515e943c22743fedb512d96144d3d0559f83ce96bc722d98bf1c73'))
            self.assertIn(family,checker.LONG_FAMILIES)
            fingerprints.append(checker.functional_fingerprint(m,t['budget'],directory/'capture/source/fpga')['sha256'])
        self.assertEqual(fingerprints[0],fingerprints[1])


class R11TransportLeanC2LongTests(R10TimingLeanC2LongTests):
    """Own registered transport/field retirement/watchdog source and pilot."""
    BASE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-transport11-ownlong-v1'
    NATIVE=ROOT/'queue/evidence/s4-p16-c2-combo-r11-own100-serial-q1-v1'
    HELPER='reference/stream27_context_storage_combo_transport11_continuous.py'
    VALIDATOR='reference/stream27_context_storage_combo_transport11_long_native.py'
    HELPER_PIN='e5cf7553c6a90e3600369cfd5e58478a506fc513f24407dd6ce732c60f4169e7'
    VALIDATOR_PIN='e4554733c3224d264efef399317eb459f092f62767c480fd9a3533c517e0de69'
    CONTEXT_KEY='context_transport11'
    SOURCE_FAMILY='storage2-combo-transport11-58'
    STEP='normal-full-c2-combo-r11-continuous1000-percontext'
    COMMAND_ESTIMATE=4387.597855322529
    OVERALL_ESTIMATE=5315.112824885808
    PARAMETERS=runtime.C2_FAMILIES[runtime.C2_R11_HELPER]['parameters']
    CPP=runtime.C2_R11_CPP

    def test_literal_oneshot_flags_and_independent_source_calendar(self):
        for model,count in zip(self.source_models(),(100,1000)):
            self.assertEqual(model['build']['parameters'],self.PARAMETERS)
            self.assertEqual(len(model['build']['sv_sources']),59)
            group=model[self.CONTEXT_KEY];g=group['geometry']
            self.assertEqual(len(group['production_generated_sha256']),58)
            self.assertEqual((g['warm_interval'],g['first_digit'],g['carry_done'],g['sink_accept'],g['last_sink']),
                             (8463,8462,12561,8419,12514))
            self.assertEqual((g['correction_cache_latency'],g['term_seed_first'],g['term_seed_last']),
                             (78,71,74))
            self.assertEqual((g['crt_accept'],g['carry_busy_edges'],g['crt_delivery_after_field_sink_edges']),
                             (8420,4143,1))
            self.assertEqual(runtime.c2_frame_calendar(g,count,8463,1,1,1),group['own_long']['own_calendar'])
            self.assertIs(group['progress_watchdog_repaired_source_only_no_prior_PRP_inheritance'],True)
            for key in ('lean_production','host_GL_assumed_unimplemented'):
                self.assertIs(group[key],True);self.assertIs(group['own_long'][key],True)
            self.assertIs(group['protected_fault_rollback_claim'],False)
            self.assertFalse(group['own_long']['prior_forecast_used'])

    def test_source_specific_publication_fence_both_jobs_not_warm_time(self):
        m,v,p=self.fixture();warm=v['pilot_gate']['steps'][0]['validation']['measurements']['warm_edges']
        self.assertEqual(warm,[850603,854834])
        old,oldjoint=runtime.c2_publication_edges(warm)
        done,joint=runtime.c2_publication_edges(warm,1)
        self.assertEqual((done,joint),([1510068,2169532],2235068))
        self.assertEqual((done[0]-old[0],done[1]-old[1],joint-oldjoint),(1,2,2))
        launches=[[first+k*8463 for k in range(1000)] for first in (204,4435)]
        longwarm=[row[-1]+12562 for row in launches]
        self.assertEqual(runtime.c2_publication_edges(longwarm,1),([9126768,9786232],9851768))
        got=runtime.assess(m,v,p,'gfn16-pilot-c4d')
        self.assertEqual(got['build_label'],runtime.C2_LEAN_LABEL)
        self.assertFalse(got['host_gl_implemented']);self.assertFalse(got['rollback_implemented'])

    def test_exact_captured_inverse_geometry_ast_preserves_cache_and_seed(self):
        source=self.BASE/self.FULL_DIR/'source/fpga'
        name='reference/stream27_context_transport11_model.py'
        raw=(source/'lineage'/name).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),runtime.C2_R11_SOURCE_PINS[name])
        nodes=[n for n in runtime.ast.parse(raw).body if isinstance(n,runtime.ast.FunctionDef) and n.name=='geometry']
        self.assertEqual(len(nodes),1)
        namespace={}
        exec(compile(runtime.ast.Module(body=nodes,type_ignores=[]),'[source-only transport geometry]','exec'),namespace)
        before=json.loads((R10TimingLeanC2LongTests.BASE/'continuous1000-measured-v1/manifest.json').read_text())['context_timing10']['geometry']
        full=self.source_models()[1];g=full[self.CONTEXT_KEY]['geometry']
        derived=namespace['geometry'](before,crt_transport_reg=1,inverse_ingress_reg=1,term_join_transport_reg=1,ntt_compare_reg=0)
        self.assertEqual(derived,g)
        self.assertEqual((derived['pointwise_accept'],derived['correction_cache_latency'],derived['term_seed_first'],derived['term_seed_last']),
                         (4207,78,71,74))
        self.assertEqual(derived['next_cache_capture'],12639)
        self.assertEqual(derived['cache_margin'],30)
        self.assertEqual(derived['crt_accept'],derived['sink_accept']+1)

    def test_cache79_naive_composition_source_substitution_and_protected_scope_refuse(self):
        m,v,p=self.fixture();key=self.CONTEXT_KEY
        changes=[('m',(key,'geometry','warm_interval'),8460),
            ('m',(key,'geometry','crt_accept'),8419),
            ('m',(key,'geometry','carry_busy_edges'),4142),
            ('m',(key,'geometry','correction_cache_latency'),79),
            ('m',(key,'geometry','crt_delivery_after_field_sink_edges'),0),
            ('m',(key,'progress_watchdog_repaired_source_only_no_prior_PRP_inheritance'),False),
            ('m',('build','parameters','LEAN_PROGRESS_WATCHDOG'),0),
            ('m',('build','parameters','CRT_TRANSPORT_REG'),0),
            ('m',('build','parameters','TERM_JOIN_TRANSPORT_REG'),True),
            ('m',(key,'own_long','protected_fault_rollback_claim'),True),
            ('v',('forecast','generator'),runtime.C2_R10_HELPER),
            ('p',('pilot_report',),runtime.C2_FAMILIES[runtime.C2_R10_HELPER]['evidence_pins']['pilot_report'])]
        for name in runtime.C2_R11_SOURCE_PINS:
            changes.append(('m',('sources','lineage/'+name),'0'*64))
            changes.append(('m',(key,'source_sha256',name),'0'*64))
        for label,path,value in changes:
            a,b,c=copy.deepcopy((m,v,p));target={'m':a,'v':b,'p':c}[label]
            for name in path[:-1]:target=target[name]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.assess(a,b,c,'gfn16-pilot-c4d')
        g=m[key]['geometry']
        for selector in (True,-1,2):
            with self.subTest(selector=selector),self.assertRaises(ValueError):
                runtime.c2_frame_calendar(g,100,8463,1,1,selector)
        with self.assertRaises(ValueError):runtime.c2_frame_calendar(g,100,8463,1,1,0)

    def test_captured_r10_packet_identity_and_failures_not_relabelled(self):
        from fpga.tools import native_profile_variants_v14 as checker
        base=R10TimingLeanC2LongTests.BASE/'continuous1000-packet-v1'
        fingerprints=[]
        for name in ('packet-01','packet-23'):
            directory=base/name;m=json.loads((directory/'manifest.json').read_text());t=json.loads((directory/'ticket.json').read_text())
            family=tuple(m['sources'][rel] for rel in ('tools/native_long_class_v2.py','tools/native_long_package_v3.py'))
            self.assertEqual(family,('e5bc5825dd9ea8dbc777f9870538c30d262ebeeb555ca55cd54c198dd8a332dc','7880002e6fca59bcaf5b758e392d39db57db29b387e226d30ce8cce9a8e06a93'))
            self.assertIn(family,checker.LONG_FAMILIES)
            fingerprints.append(checker.functional_fingerprint(m,t['budget'],directory/'capture/source/fpga')['sha256'])
        self.assertEqual(fingerprints[0],fingerprints[1])


class R12SourcePreparationTests(unittest.TestCase):
    """Frozen source contract before measured admission; no pilot invented."""
    BASE=ROOT/'results/throughput-20260929/trackS-c2-feedback12-ownlong-v1'
    FREEZE=ROOT/'results/throughput-20260929/trackS-c2-feedback12-source-v1/freeze.json'

    def models(self):
        return [json.loads((self.BASE/name/'manifest.json').read_text())
                for name in ('own100-serial-v1','continuous1000-source-v1')]

    def test_source_template_header_config_separate_from_actual_measured_binding(self):
        pilot,full=self.models();family=runtime.C2_R12_SOURCE_TEMPLATE
        scalar=runtime.c2_scalar_functions(family)
        before=(self.BASE/'own100-serial-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        after=(self.BASE/'continuous1000-source-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        self.assertEqual(scalar['header'](before),after)
        self.assertEqual(scalar['config'](),full['steps'][0]['validator']['config'])
        self.assertEqual(full['build']['parameters'],family['parameters'])
        self.assertEqual(pilot['build'],full['build'])
        for model in (pilot,full):
            self.assertEqual(model['sources'][family['validator']],family['validator_pin'])
            self.assertEqual(model['sources'][family['cpp']],family['cpp_pin'])
            self.assertEqual(len(model['build']['sv_sources']),59)
        self.assertNotIn('evidence_pins',family)
        self.assertNotIn('typed_pin',family)
        self.assertIn(runtime.C2_R12_HELPER,runtime.C2_FAMILIES)
        with self.assertRaises(ValueError):
            runtime.c2_source_family(dict(generator=family['helper'],generator_sha256='0'*64))
        self.assertNotIn(runtime.C2_R12_HELPER,runtime.PINS)
        self.assertNotIn(runtime.C2_R12_VALIDATOR,runtime.PINS)

    def test_own_200_and_2000_frame_calendar_counts_real_feedback_and_correction(self):
        for model,count in zip(self.models(),(100,1000)):
            group=model['context_feedback12'];g=group['geometry']
            actual=runtime.c2_frame_calendar(g,count,8464,1,1,1,1)
            self.assertEqual(actual,group['own_long']['own_calendar'])
            self.assertEqual(actual['frames'],2*count)
            self.assertEqual(actual['launch_gaps'],[4232,4232])
            self.assertEqual(actual['feedback_peak_rows'],[1,1])
            self.assertEqual(actual['feedback_old_fifo_rows'],0)
            self.assertEqual(actual['explicit_feedback_register_rows'],1)
            self.assertEqual((g['first_digit'],g['carry_done'],g['pointwise_accept'],g['sink_accept']),
                             (8462,12561,4207,8419))
            self.assertEqual((g['next_correction_accept'],g['next_cache_capture'],g['cold_correction_input_edges_added']),
                             (12562,12640,0))

    def test_exact_source_model_geometry_preserves_cold_and_pairs_warm_registers(self):
        pilot,full=self.models();source=self.BASE/'continuous1000-source-v1/source/fpga'
        for name,pin in runtime.C2_R12_SOURCE_PINS.items():
            self.assertEqual(full['sources']['lineage/'+name],pin)
            self.assertEqual(pilot['sources']['lineage/'+name],pin)
            self.assertEqual(full['context_feedback12']['source_sha256'][name],pin)
            self.assertEqual(hashlib.sha256((source/'lineage'/name).read_bytes()).hexdigest(),pin)
        raw=(source/'lineage/reference/stream27_context_feedback12_model.py').read_bytes()
        nodes=[n for n in runtime.ast.parse(raw).body if isinstance(n,runtime.ast.FunctionDef) and n.name=='geometry']
        self.assertEqual(len(nodes),1);namespace={}
        exec(compile(runtime.ast.Module(body=nodes,type_ignores=[]),'[source-only paired ingress geometry]','exec'),namespace)
        before=json.loads((R11TransportLeanC2LongTests.BASE/'continuous1000-measured-v1/manifest.json').read_text())['context_transport11']['geometry']
        derived=namespace['geometry'](before,feedback_ingress_reg=1,auto_correction_ingress_reg=1,c0_admission_direct=1)
        self.assertEqual(derived,full['context_feedback12']['geometry'])
        for key in ('first_digit','carry_done','pointwise_accept','sink_accept','correction_cache_latency','term_seed_first','term_seed_last'):
            self.assertEqual(derived[key],before[key])

    def test_own_publication_algebra_and_exact_freeze_source_join(self):
        raw=self.FREEZE.read_bytes();freeze=json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'f5fbe66f2493aa5a0248a64aa82acf7208f7a344d6c8ca9ca07f73fca4a6f71a')
        self.assertEqual(freeze['binder_sha256'],runtime.C2_R12_SOURCE_PINS['reference/stream27_context_feedback12_bind.py'])
        self.assertEqual(freeze['model_sha256'],runtime.C2_R12_SOURCE_PINS['reference/stream27_context_feedback12_model.py'])
        self.assertTrue(freeze['cold_one_shot_and_acceptance_literal'])
        self.assertTrue(freeze['queued_descriptor_rechecked_at_actual_accept'])
        self.assertTrue(freeze['raw_origin_command_collision_sticky_checks'])
        self.assertFalse(freeze['native_qualified'])
        for count,done,joint in ((100,[1510167,2169631],2235167),(1000,[9127767,9787231],9852767)):
            warm=[first+(count-1)*8464+12562 for first in (204,4436)]
            self.assertEqual(runtime.c2_publication_edges(warm,1),(done,joint))
            self.assertEqual(freeze['full']['count'+str(count)+'_publication'],done)
            self.assertEqual(freeze['full']['count'+str(count)+'_joint'],joint)

    def test_frozen_ingress_and_retained_watchdog_lineage_without_execution_credit(self):
        pilot,full=self.models();context=full['context_feedback12']
        runtime.c2_feedback12_source_guard(full,pilot,context)
        for name in dict(runtime.C2_R11_SOURCE_PINS,**runtime.C2_R12_SOURCE_PINS):
            for target in ('full','pilot','context'):
                a,b,c=copy.deepcopy((full,pilot,context))
                if target=='context':c['source_sha256'][name]='0'*64
                else:{'full':a,'pilot':b}[target]['sources']['lineage/'+name]='0'*64
                with self.subTest(name=name,target=target),self.assertRaises(ValueError):
                    runtime.c2_feedback12_source_guard(a,b,c)
        for key in ('R11_watchdog_source_retained_no_prior_execution_inheritance','donor_results_not_inherited'):
            bad=copy.deepcopy(context);bad[key]=False
            with self.subTest(key=key),self.assertRaises(ValueError):
                runtime.c2_feedback12_source_guard(full,pilot,bad)

    def test_old_r11_or_uncounted_feedback_and_retimed_cold_reject(self):
        g=self.models()[1]['context_feedback12']['geometry']
        for key,value in (('warm_interval',8463),('feedback_delay',0),('feedback_fifo_rows',0),
            ('explicit_feedback_register_rows',0),('existing_feedback_delay',1),
            ('automatic_correction_input_edges_added',0),('cold_correction_input_edges_added',1),
            ('c0_admission_direct',0),('next_correction_accept',12561),('next_cache_capture',12639)):
            bad=copy.deepcopy(g);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                runtime.c2_frame_calendar(bad,100,8464,1,1,1,1)
        for selector in (True,-1,2):
            with self.subTest(selector=selector),self.assertRaises(ValueError):
                runtime.c2_frame_calendar(g,100,8464,1,1,1,selector)
        with self.assertRaises(ValueError):runtime.c2_frame_calendar(g,100,8464,1,1,1,0)


class R12FeedbackLeanC2LongTests(R11TransportLeanC2LongTests):
    """Own measured R12 pilot; counted feedback and paired correction tuple."""
    BASE=ROOT/'results/throughput-20260929/trackS-c2-feedback12-ownlong-v1'
    NATIVE=ROOT/'queue/evidence/s4-p16-c2-combo-r12-own100-serial-q1-v1'
    HELPER=runtime.C2_R12_HELPER
    VALIDATOR=runtime.C2_R12_VALIDATOR
    HELPER_PIN='bb858a6e8e07b8f06c92c9a0e958fc4d570439b9423a08a5de1b88a8901b6b78'
    VALIDATOR_PIN='f06a4129f267cdd5e72ca5df33387484722dc0cad81059c55add4fc61bfb8def'
    CONTEXT_KEY='context_feedback12'
    SOURCE_FAMILY='storage2-feedback12-58'
    STEP='normal-full-c2-combo-r12-continuous1000-percontext'
    COMMAND_ESTIMATE=4532.03321154484
    OVERALL_ESTIMATE=5458.589260682369
    PARAMETERS=runtime.C2_FAMILIES[runtime.C2_R12_HELPER]['parameters']
    CPP=runtime.C2_R12_CPP

    def test_literal_oneshot_flags_and_independent_source_calendar(self):
        for model,count in zip(self.source_models(),(100,1000)):
            self.assertEqual(model['build']['parameters'],self.PARAMETERS)
            self.assertEqual(len(model['build']['sv_sources']),59)
            group=model[self.CONTEXT_KEY];g=group['geometry']
            self.assertEqual(len(group['production_generated_sha256']),58)
            self.assertEqual((g['warm_interval'],g['first_digit'],g['carry_done'],g['sink_accept']),
                             (8464,8462,12561,8419))
            self.assertEqual((g['correction_cache_latency'],g['term_seed_first'],g['term_seed_last']),
                             (78,71,74))
            self.assertEqual((g['feedback_fifo_rows'],g['existing_feedback_delay'],
                              g['explicit_feedback_register_rows'],g['cold_correction_input_edges_added']),
                             (1,0,1,0))
            self.assertEqual(runtime.c2_frame_calendar(g,count,8464,1,1,1,1),group['own_long']['own_calendar'])
            self.assertIs(group['R11_watchdog_source_retained_no_prior_execution_inheritance'],True)
            self.assertIs(group['donor_results_not_inherited'],True)
            self.assertFalse(group['own_long']['prior_forecast_used'])

    def test_source_specific_publication_fence_both_jobs_not_warm_time(self):
        m,v,p=self.fixture();warm=v['pilot_gate']['steps'][0]['validation']['measurements']['warm_edges']
        self.assertEqual(warm,[850702,854934])
        old,oldjoint=runtime.c2_publication_edges(warm)
        done,joint=runtime.c2_publication_edges(warm,1)
        self.assertEqual((done,joint),([1510167,2169631],2235167))
        self.assertEqual((done[0]-old[0],done[1]-old[1],joint-oldjoint),(1,2,2))
        longwarm=[first+999*8464+12562 for first in (204,4436)]
        self.assertEqual(runtime.c2_publication_edges(longwarm,1),([9127767,9787231],9852767))
        got=runtime.assess(m,v,p,'gfn16-pilot-c4d')
        self.assertEqual(got['build_label'],runtime.C2_LEAN_LABEL)
        self.assertFalse(got['host_gl_implemented']);self.assertFalse(got['rollback_implemented'])

    def test_exact_captured_inverse_geometry_ast_preserves_cache_and_seed(self):
        source=self.BASE/self.FULL_DIR/'source/fpga'
        name='reference/stream27_context_feedback12_model.py'
        raw=(source/'lineage'/name).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),runtime.C2_R12_SOURCE_PINS[name])
        nodes=[n for n in runtime.ast.parse(raw).body if isinstance(n,runtime.ast.FunctionDef) and n.name=='geometry']
        self.assertEqual(len(nodes),1);namespace={}
        exec(compile(runtime.ast.Module(body=nodes,type_ignores=[]),'[source-only R12 paired ingress geometry]','exec'),namespace)
        before=json.loads((R11TransportLeanC2LongTests.BASE/'continuous1000-measured-v1/manifest.json').read_text())['context_transport11']['geometry']
        g=self.source_models()[1][self.CONTEXT_KEY]['geometry']
        self.assertEqual(namespace['geometry'](before,feedback_ingress_reg=1,
            auto_correction_ingress_reg=1,c0_admission_direct=1),g)
        self.assertEqual((g['pointwise_accept'],g['correction_cache_latency'],g['term_seed_first'],g['term_seed_last']),
                         (4207,78,71,74))
        self.assertEqual((g['next_correction_accept'],g['next_cache_capture'],g['cache_margin']),(12562,12640,30))

    def test_cache79_naive_composition_source_substitution_and_protected_scope_refuse(self):
        m,v,p=self.fixture();key=self.CONTEXT_KEY
        changes=[('m',(key,'geometry','warm_interval'),8463),
            ('m',(key,'geometry','feedback_fifo_rows'),0),
            ('m',(key,'geometry','automatic_correction_input_edges_added'),0),
            ('m',(key,'geometry','cold_correction_input_edges_added'),1),
            ('m',(key,'geometry','next_correction_accept'),12561),
            ('m',(key,'geometry','correction_cache_latency'),79),
            ('m',(key,'R11_watchdog_source_retained_no_prior_execution_inheritance'),False),
            ('m',(key,'donor_results_not_inherited'),False),
            ('m',('build','parameters','FEEDBACK_INGRESS_REG'),0),
            ('m',('build','parameters','AUTO_CORRECTION_INGRESS_REG'),0),
            ('m',('build','parameters','C0_ADMISSION_DIRECT'),True),
            ('m',(key,'own_long','protected_fault_rollback_claim'),True),
            ('v',('forecast','generator'),runtime.C2_R11_HELPER),
            ('p',('pilot_report',),runtime.C2_FAMILIES[runtime.C2_R11_HELPER]['evidence_pins']['pilot_report'])]
        for name in dict(runtime.C2_R11_SOURCE_PINS,**runtime.C2_R12_SOURCE_PINS):
            changes.append(('m',('sources','lineage/'+name),'0'*64))
            changes.append(('m',(key,'source_sha256',name),'0'*64))
        for label,path,value in changes:
            a,b,c=copy.deepcopy((m,v,p));target={'m':a,'v':b,'p':c}[label]
            for name in path[:-1]:target=target[name]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.assess(a,b,c,'gfn16-pilot-c4d')
        g=m[key]['geometry']
        for selector in (True,-1,2):
            with self.subTest(selector=selector),self.assertRaises(ValueError):
                runtime.c2_frame_calendar(g,100,8464,1,1,1,selector)
        with self.assertRaises(ValueError):runtime.c2_frame_calendar(g,100,8464,1,1,1,0)

    def test_captured_r10_packet_identity_and_failures_not_relabelled(self):
        from fpga.tools import native_profile_variants_v14 as checker
        base=R11TransportLeanC2LongTests.BASE/'continuous1000-packet-v1'
        fingerprints=[]
        for name in ('packet-01','packet-23'):
            directory=base/name;m=json.loads((directory/'manifest.json').read_text());t=json.loads((directory/'ticket.json').read_text())
            family=tuple(m['sources'][rel] for rel in ('tools/native_long_class_v2.py','tools/native_long_package_v3.py'))
            self.assertEqual(family,('0449f13c9f078f2118aa2cda25dd72c99f4d4de383b0590129a2e706dd8dcef1',
                                   'e6d61b1ac565aa784fde36fd55ba463c8f55187ff65792caa63e2f5b6903065f'))
            self.assertIn(family,checker.LONG_FAMILIES)
            fingerprints.append(checker.functional_fingerprint(m,t['budget'],directory/'capture/source/fpga')['sha256'])
        self.assertEqual(fingerprints[0],fingerprints[1])


class ProtectedField100SourcePreparationTests(unittest.TestCase):
    """Source-only protected calendar preparation; no pilot rate invented."""
    BASE=ROOT/'results/throughput-20260929/trackS-c2-protected-field100-ownlong-v1'
    BUNDLE=ROOT/'results/throughput-20260929/trackS-c2-protected-field100-native-v1/full-normal-v2/production-bundle.json'

    def models(self):
        return [json.loads((self.BASE/name/'manifest.json').read_text())
                for name in ('own100-serial-v1','continuous1000-source-v1')]

    def test_frozen_header_config_and_separate_source_template(self):
        pilot,full=self.models();family=runtime.C2_FIELD100_SOURCE_TEMPLATE
        scalar=runtime.c2_scalar_functions(family)
        before=(self.BASE/'own100-serial-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        after=(self.BASE/'continuous1000-source-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        self.assertEqual(scalar['header'](before),after)
        self.assertEqual(scalar['config'](),full['steps'][0]['validator']['config'])
        self.assertIs(scalar['config']()['lean_production'],False)
        self.assertNotIn('evidence_pins',family);self.assertNotIn('typed_pin',family)
        self.assertIn(runtime.C2_FIELD100_HELPER,runtime.C2_FAMILIES)
        for model in (pilot,full):
            self.assertEqual(model['sources'][family['validator']],family['validator_pin'])
            self.assertEqual(model['sources'][family['cpp']],family['cpp_pin'])
        self.assertNotIn(runtime.C2_FIELD100_HELPER,runtime.PINS)
        self.assertNotIn(runtime.C2_FIELD100_VALIDATOR,runtime.PINS)

    def test_own_protected_200_and_2000_frame_calendar(self):
        for model,count in zip(self.models(),(100,1000)):
            context=model['context_protected_field100'];g=context['geometry']
            actual=runtime.c2_frame_calendar(g,count,8461,1,1,0,0,1)
            self.assertEqual(actual,context['own_long']['own_calendar'])
            self.assertEqual(actual['frames'],2*count)
            self.assertEqual(actual['launch_gaps'],[4230,4231])
            self.assertEqual(actual['feedback_peak_rows'],[1,1])
            self.assertEqual(actual['feedback_old_fifo_rows'],0)
            self.assertEqual((g['first_digit'],g['carry_done'],g['sink_accept']),(8459,12558,8417))
            self.assertEqual((g['next_correction_accept'],g['next_cache_capture'],g['cold_correction_input_edges_added']),
                             (12559,12637,0))

    def test_source_geometry_ast_pairs_ingress_without_r11_datapath(self):
        pilot,full=self.models();context=full['context_protected_field100']
        source=self.BASE/'continuous1000-source-v1/source/fpga'
        name='reference/stream27_context_feedback12_model.py';pin=runtime.C2_FIELD100_SOURCE_PINS[name]
        raw=(source/'lineage'/name).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),pin)
        nodes=[node for node in runtime.ast.parse(raw).body if isinstance(node,runtime.ast.FunctionDef) and node.name=='geometry']
        self.assertEqual(len(nodes),1);namespace={}
        exec(compile(runtime.ast.Module(body=nodes,type_ignores=[]),'[source-only protected paired ingress geometry]','exec'),namespace)
        before=context['contract']['calendar_before']
        derived=namespace['geometry'](before,feedback_ingress_reg=1,auto_correction_ingress_reg=1,c0_admission_direct=1)
        self.assertEqual(derived,context['geometry'])
        for key in ('pointwise_accept','sink_accept','first_digit','carry_done','correction_cache_latency','term_seed_first','term_seed_last'):
            self.assertEqual(derived[key],before[key])
        self.assertEqual((derived['crt_accept'],derived['carry_busy_edges']),(8417,4142))

    def test_exact_protected_source_and_separate_fault_scope(self):
        pilot,full=self.models();context=full['context_protected_field100']
        runtime.c2_field100_source_guard(full,pilot,context)
        for name in runtime.C2_FIELD100_SOURCE_PINS:
            for target in ('full','pilot','context'):
                a,b,c=copy.deepcopy((full,pilot,context))
                if target=='context':c['source_sha256'][name]='0'*64
                else:{'full':a,'pilot':b}[target]['sources']['lineage/'+name]='0'*64
                with self.subTest(name=name,target=target),self.assertRaises(ValueError):
                    runtime.c2_field100_source_guard(a,b,c)
        for key in ('protected_mode_source_restored','R11_transports_not_composed',
                    'publication_and_fault_report_native_qualification_separate','donor_results_not_inherited'):
            bad=copy.deepcopy(context);bad[key]=False
            with self.subTest(key=key),self.assertRaises(ValueError):
                runtime.c2_field100_source_guard(full,pilot,bad)
        for key in ('lean_production','host_GL_assumed_unimplemented','protected_fault_rollback_claim','promotion_allowed'):
            bad=copy.deepcopy(context);bad[key]=True
            with self.subTest(key=key),self.assertRaises(ValueError):
                runtime.c2_field100_source_guard(full,pilot,bad)

    def test_exact_eight_flags_bundle_and_publication_boundaries(self):
        pilot,full=self.models();family=runtime.C2_FIELD100_SOURCE_TEMPLATE
        self.assertEqual(pilot['build'],full['build'])
        self.assertEqual(full['build']['parameters'],family['parameters'])
        params=full['build']['parameters']
        for name in ('LEAN_PRODUCTION','CRT_TRANSPORT_REG','INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG','LEAN_PROGRESS_WATCHDOG'):
            self.assertNotIn(name,params)
        self.assertTrue(all(type(params[name]) is int and params[name]==1 for name in runtime.C2_FIELD100_FLAGS))
        self.assertEqual(full['context_protected_field100']['contract']['flags'],runtime.C2_FIELD100_FLAGS)
        self.assertEqual(len(full['build']['sv_sources']),59)
        self.assertEqual(len(full['context_protected_field100']['production_generated_sha256']),58)
        raw=self.BUNDLE.read_bytes();bundle=json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'f5f0617d989b64bb965b612a0d0cb8b6074c1ecd4f85f01ed66f970dfbf521f2')
        self.assertEqual(bundle['geometry'],full['context_protected_field100']['geometry'])
        for count,done,joint in ((100,[1509867,2169331],2234867),(1000,[9124767,9784231],9849767)):
            warm=[first+(count-1)*8461+12559 for first in (204,4434)]
            self.assertEqual(runtime.c2_publication_edges(warm,1),(done,joint))

    def test_old_lean_calendar_uncounted_feedback_or_cold_retime_refuse(self):
        g=self.models()[1]['context_protected_field100']['geometry']
        for key,value in (('warm_interval',8464),('first_digit',8462),('carry_done',12561),
            ('crt_accept',8418),('sink_accept',8419),('feedback_delay',0),('feedback_fifo_rows',0),
            ('explicit_feedback_register_rows',0),('automatic_correction_input_edges_added',0),
            ('cold_correction_input_edges_added',1),('correction_cache_latency',79),
            ('next_correction_accept',12558),('next_cache_capture',12636)):
            bad=copy.deepcopy(g);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                runtime.c2_frame_calendar(bad,100,8461,1,1,0,0,1)
        for selector in (True,-1,2):
            with self.subTest(selector=selector),self.assertRaises(ValueError):
                runtime.c2_frame_calendar(g,100,8461,1,1,0,0,selector)
        with self.assertRaises(ValueError):runtime.c2_frame_calendar(g,100,8461,1,1,1,0,1)
        with self.assertRaises(ValueError):runtime.c2_frame_calendar(g,100,8461,1,1,0,1,1)
        with self.assertRaises(ValueError):runtime.c2_frame_calendar(g,100,8461,1,1,0,0,0)


class ProtectedField100C2LongTests(R12FeedbackLeanC2LongTests):
    """Own protected source and serial pilot, not inherited lean evidence."""
    BASE=ROOT/'results/throughput-20260929/trackS-c2-protected-field100-ownlong-v1'
    NATIVE=ROOT/'queue/evidence/s4-p16-c2-protected-field100-own100-serial-q1-v1'
    HELPER=runtime.C2_FIELD100_HELPER
    VALIDATOR=runtime.C2_FIELD100_VALIDATOR
    HELPER_PIN='48acba5aafa33f0879df7026051ac088640070fac46c256a178b9afa3c1fa5f2'
    VALIDATOR_PIN='aa15e4c9c02333d3f661c8135a69a979e2283a6469e6cdd0f59dbe04dba3d000'
    CONTEXT_KEY='context_protected_field100'
    SOURCE_FAMILY='protected-field100-58'
    STEP='normal-full-c2-protected-field100-continuous1000-percontext'
    COMMAND_ESTIMATE=4815.999028819715
    OVERALL_ESTIMATE=5746.122359222019
    PARAMETERS=runtime.C2_FAMILIES[runtime.C2_FIELD100_HELPER]['parameters']
    CPP=runtime.C2_FIELD100_CPP

    def test_literal_oneshot_flags_and_independent_source_calendar(self):
        for model,count in zip(self.source_models(),(100,1000)):
            self.assertEqual(model['build']['parameters'],self.PARAMETERS)
            self.assertEqual(len(model['build']['sv_sources']),59)
            group=model[self.CONTEXT_KEY];g=group['geometry']
            self.assertEqual(len(group['production_generated_sha256']),58)
            self.assertEqual((g['warm_interval'],g['first_digit'],g['carry_done'],g['sink_accept']),
                             (8461,8459,12558,8417))
            self.assertEqual((g['correction_cache_latency'],g['term_seed_first'],g['term_seed_last']),
                             (78,71,74))
            self.assertEqual((g['feedback_fifo_rows'],g['existing_feedback_delay'],
                              g['explicit_feedback_register_rows'],g['cold_correction_input_edges_added']),
                             (1,0,1,0))
            self.assertEqual(runtime.c2_frame_calendar(g,count,8461,1,1,0,0,1),group['own_long']['own_calendar'])
            for key in ('lean_production','host_GL_assumed_unimplemented','protected_fault_rollback_claim'):
                self.assertIs(group[key],False);self.assertIs(group['own_long'][key],False)
            self.assertIs(group['protected_mode_source_restored'],True)
            self.assertIs(group['R11_transports_not_composed'],True)

    def test_source_specific_publication_fence_both_jobs_not_warm_time(self):
        m,v,p=self.fixture();warm=v['pilot_gate']['steps'][0]['validation']['measurements']['warm_edges']
        self.assertEqual(warm,[850402,854632])
        old,oldjoint=runtime.c2_publication_edges(warm)
        done,joint=runtime.c2_publication_edges(warm,1)
        self.assertEqual((done,joint),([1509867,2169331],2234867))
        self.assertEqual((done[0]-old[0],done[1]-old[1],joint-oldjoint),(1,2,2))
        longwarm=[first+999*8461+12559 for first in (204,4434)]
        self.assertEqual(runtime.c2_publication_edges(longwarm,1),([9124767,9784231],9849767))
        got=runtime.assess(m,v,p,'gfn16-pilot-c4d')
        self.assertNotIn('build_label',got)
        self.assertFalse(got['promotion_allowed'])

    def test_exact_captured_inverse_geometry_ast_preserves_cache_and_seed(self):
        source=self.BASE/self.FULL_DIR/'source/fpga';name='reference/stream27_context_feedback12_model.py'
        raw=(source/'lineage'/name).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),runtime.C2_FIELD100_SOURCE_PINS[name])
        nodes=[n for n in runtime.ast.parse(raw).body if isinstance(n,runtime.ast.FunctionDef) and n.name=='geometry']
        self.assertEqual(len(nodes),1);namespace={}
        exec(compile(runtime.ast.Module(body=nodes,type_ignores=[]),'[own protected FIELD100 geometry only]','exec'),namespace)
        full=self.source_models()[1];group=full[self.CONTEXT_KEY];g=group['geometry']
        self.assertEqual(namespace['geometry'](group['contract']['calendar_before'],feedback_ingress_reg=1,
            auto_correction_ingress_reg=1,c0_admission_direct=1),g)
        self.assertEqual((g['pointwise_accept'],g['sink_accept'],g['carry_busy_edges']),(4207,8417,4142))
        self.assertEqual((g['next_correction_accept'],g['next_cache_capture'],g['cache_margin']),(12559,12637,30))

    def test_cache79_naive_composition_source_substitution_and_protected_scope_refuse(self):
        m,v,p=self.fixture();key=self.CONTEXT_KEY
        changes=[('m',(key,'geometry','warm_interval'),8464),
            ('m',(key,'geometry','feedback_fifo_rows'),0),
            ('m',(key,'geometry','automatic_correction_input_edges_added'),0),
            ('m',(key,'geometry','cold_correction_input_edges_added'),1),
            ('m',(key,'geometry','next_correction_accept'),12558),
            ('m',(key,'geometry','correction_cache_latency'),79),
            ('m',(key,'protected_mode_source_restored'),False),
            ('m',(key,'R11_transports_not_composed'),False),
            ('m',(key,'publication_and_fault_report_native_qualification_separate'),False),
            ('m',(key,'donor_results_not_inherited'),False),
            ('m',(key,'lean_production'),True),
            ('m',(key,'own_long','host_GL_assumed_unimplemented'),True),
            ('m',(key,'own_long','protected_fault_rollback_claim'),True),
            ('v',('forecast','generator'),runtime.C2_R12_HELPER),
            ('p',('pilot_report',),runtime.C2_FAMILIES[runtime.C2_R12_HELPER]['evidence_pins']['pilot_report'])]
        for name in runtime.C2_FIELD100_FLAGS:
            changes.append(('m',('build','parameters',name),0))
            changes.append(('m',('build','parameters',name),True))
        for name in runtime.C2_FIELD100_SOURCE_PINS:
            changes.append(('m',('sources','lineage/'+name),'0'*64))
            changes.append(('m',(key,'source_sha256',name),'0'*64))
        for label,path,value in changes:
            a,b,c=copy.deepcopy((m,v,p));target={'m':a,'v':b,'p':c}[label]
            for name in path[:-1]:target=target[name]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.assess(a,b,c,'gfn16-pilot-c4d')
        for name in ('LEAN_PRODUCTION','CRT_TRANSPORT_REG','INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG','LEAN_PROGRESS_WATCHDOG'):
            bad=copy.deepcopy(m);bad['build']['parameters'][name]=1
            with self.subTest(extra=name),self.assertRaises(ValueError):runtime.assess(bad,v,p,'gfn16-pilot-c4d')

    def test_captured_r10_packet_identity_and_failures_not_relabelled(self):
        from fpga.tools import native_profile_variants_v14 as checker
        base=R12FeedbackLeanC2LongTests.BASE/'continuous1000-packet-v1';fingerprints=[]
        for name in ('packet-01','packet-23'):
            directory=base/name;m=json.loads((directory/'manifest.json').read_text());t=json.loads((directory/'ticket.json').read_text())
            family=tuple(m['sources'][rel] for rel in ('tools/native_long_class_v2.py','tools/native_long_package_v3.py'))
            self.assertEqual(family,('d729cb5dcc8625920781897637bd8d6f372619d01c5ecdc8c1801204b1cbc8de',
                                   '8918350fcc06bf7778df10b78cce080a2737656fa096975e373bb2ee0a3be4c0'))
            self.assertIn(family,checker.LONG_FAMILIES)
            fingerprints.append(checker.functional_fingerprint(m,t['budget'],directory/'capture/source/fpga')['sha256'])
        self.assertEqual(fingerprints[0],fingerprints[1])


class ProtectedRelay13SourcePreparationTests(unittest.TestCase):
    """Same scalar interval does not imply the same protected relay graph."""
    BASE=ROOT/'results/throughput-20260929/trackS-c2-protected-relay13-ownlong-v1'
    BUNDLE=ROOT/'results/throughput-20260929/trackS-c2-protected-relay13-native-v1/full-normal/production-bundle.json'

    def models(self):
        return [json.loads((self.BASE/name/'manifest.json').read_text())
                for name in ('own100-serial-v1','continuous1000-source-v1')]

    def test_own_header_config_without_measured_evidence(self):
        pilot,full=self.models();family=runtime.C2_RELAY13_SOURCE_TEMPLATE
        scalar=runtime.c2_scalar_functions(family)
        before=(self.BASE/'own100-serial-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        after=(self.BASE/'continuous1000-source-v1/source/fpga'/runtime.C2_HEADER).read_bytes()
        self.assertEqual(scalar['header'](before),after)
        self.assertEqual(scalar['config'](),full['steps'][0]['validator']['config'])
        self.assertIs(scalar['config']()['lean_production'],False)
        self.assertNotIn('evidence_pins',family);self.assertNotIn('typed_pin',family)
        self.assertIn(runtime.C2_RELAY13_HELPER,runtime.C2_FAMILIES)
        for model in (pilot,full):
            self.assertEqual(model['sources'][family['validator']],family['validator_pin'])
            self.assertEqual(model['sources'][family['cpp']],family['cpp_pin'])
        self.assertNotIn(runtime.C2_RELAY13_HELPER,runtime.PINS)
        self.assertNotIn(runtime.C2_RELAY13_VALIDATOR,runtime.PINS)

    def test_own_forward_pointwise_sink_and_carry_calendar(self):
        for model,count in zip(self.models(),(100,1000)):
            context=model['context_protected_relay13'];g=context['geometry']
            actual=runtime.c2_frame_calendar(g,count,8464,1,1,0,0,0,1)
            self.assertEqual(actual,context['own_long']['own_calendar'])
            self.assertEqual(actual['frames'],2*count)
            self.assertEqual(actual['launch_gaps'],[4232,4232])
            self.assertEqual(actual['feedback_peak_rows'],[1,1])
            self.assertEqual((g['pointwise_accept'],g['sink_accept'],g['carry_busy_edges'],g['cache_margin']),
                             (4208,8420,4142,31))
            self.assertEqual(actual['correction'][0]['pointwise_first'],4208)
            self.assertEqual((g['crt_transport_reg'],g['crt_delivery_after_field_sink_edges']),(0,0))
            self.assertEqual((g['existing_feedback_delay'],g['physical_feedback_FIFO_rows'],
                              g['explicit_feedback_register_rows'],g['cold_correction_input_edges_added']),
                             (0,0,1,0))

    def test_own_source_geometry_ast_and_bundle_not_equal_interval_parent(self):
        pilot,full=self.models();context=full['context_protected_relay13']
        source=self.BASE/'continuous1000-source-v1/source/fpga'
        name='reference/stream27_protected_relay13_model.py';raw=(source/'lineage'/name).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),runtime.C2_RELAY13_SOURCE_PINS[name])
        nodes=[node for node in runtime.ast.parse(raw).body if isinstance(node,runtime.ast.FunctionDef) and node.name=='geometry']
        self.assertEqual(len(nodes),1);namespace={}
        exec(compile(runtime.ast.Module(body=nodes,type_ignores=[]),'[own protected R13 source geometry only]','exec'),namespace)
        before=context['contract']['calendar_before']
        derived=namespace['geometry'](before,inverse_ingress_reg=1,term_join_transport_reg=1,forward_ingress_reg=1)
        self.assertEqual(derived,context['geometry'])
        for key in ('ct_output_latency','gs_output_latency','correction_cache_latency','term_seed_first','term_seed_last','input_delay'):
            self.assertEqual(derived[key],before[key])
        raw=self.BUNDLE.read_bytes();bundle=json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'229e07390fbed434131bba7e101c2492bde27f5a45ebceb7fa40e1d94fec5c53')
        self.assertEqual(bundle['geometry'],derived)
        top=context['production_top'];host=(source/'rtl'/(''+top+'.sv')).read_text()
        self.assertIn('SECOND_CORRECTION=8233',host)

    def test_exact_protected_relay_source_and_separate_fault_scope(self):
        pilot,full=self.models();context=full['context_protected_relay13']
        runtime.c2_relay13_source_guard(full,pilot,context)
        for name in runtime.C2_RELAY13_SOURCE_PINS:
            for target in ('full','pilot','context'):
                a,b,c=copy.deepcopy((full,pilot,context))
                if target=='context':c['source_sha256'][name]='0'*64
                else:{'full':a,'pilot':b}[target]['sources']['lineage/'+name]='0'*64
                with self.subTest(name=name,target=target),self.assertRaises(ValueError):
                    runtime.c2_relay13_source_guard(a,b,c)
        for key in ('protected_mode_source_restored','CRT_transport_off','protected_forward_term_inverse_relays_on',
                    'publication_and_fault_report_native_qualification_separate','donor_results_not_inherited'):
            bad=copy.deepcopy(context);bad[key]=False
            with self.subTest(key=key),self.assertRaises(ValueError):runtime.c2_relay13_source_guard(full,pilot,bad)
        for key in ('lean_production','host_GL_assumed_unimplemented','protected_fault_rollback_claim','promotion_allowed'):
            bad=copy.deepcopy(context);bad[key]=True
            with self.subTest(key=key),self.assertRaises(ValueError):runtime.c2_relay13_source_guard(full,pilot,bad)

    def test_mandatory_flags_and_own_publication_boundaries(self):
        pilot,full=self.models();family=runtime.C2_RELAY13_SOURCE_TEMPLATE
        self.assertEqual(pilot['build'],full['build'])
        self.assertEqual(full['build']['parameters'],family['parameters'])
        params=full['build']['parameters']
        for name in ('LEAN_PRODUCTION','LEAN_PROGRESS_WATCHDOG'):self.assertNotIn(name,params)
        self.assertTrue(all(type(params[name]) is int and params[name]==1 for name in runtime.C2_FIELD100_FLAGS))
        self.assertEqual(full['context_protected_relay13']['contract']['flags'],
                         dict(INVERSE_INGRESS_REG=1,TERM_JOIN_TRANSPORT_REG=1,FORWARD_INGRESS_REG=1))
        self.assertEqual(params['CRT_TRANSPORT_REG'],0)
        self.assertEqual(len(full['build']['sv_sources']),59)
        self.assertEqual(len(full['context_protected_relay13']['production_generated_sha256']),58)
        for count,done,joint in ((100,[1510167,2169631],2235167),(1000,[9127767,9787231],9852767)):
            warm=[first+(count-1)*8464+12562 for first in (204,4436)]
            self.assertEqual(runtime.c2_publication_edges(warm,1),(done,joint))

    def test_equal_interval_r12_geometry_and_wrong_source_selectors_refuse(self):
        g=self.models()[1]['context_protected_relay13']['geometry']
        for key,value in (('pointwise_accept',4207),('sink_accept',8419),('carry_busy_edges',4143),
            ('cache_margin',30),('crt_transport_reg',1),('crt_delivery_after_field_sink_edges',1),
            ('physical_feedback_FIFO_rows',1),('forward_ingress_reg',0),('cold_correction_input_edges_added',1),
            ('correction_cache_latency',79),('next_correction_accept',12561)):
            bad=copy.deepcopy(g);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                runtime.c2_frame_calendar(bad,100,8464,1,1,0,0,0,1)
        for selector in (True,-1,2):
            with self.subTest(selector=selector),self.assertRaises(ValueError):
                runtime.c2_frame_calendar(g,100,8464,1,1,0,0,0,selector)
        with self.assertRaises(ValueError):runtime.c2_frame_calendar(g,100,8464,1,1,1,1,0,1)
        with self.assertRaises(ValueError):runtime.c2_frame_calendar(g,100,8464,1,1,0,0,1,1)
        with self.assertRaises(ValueError):runtime.c2_frame_calendar(g,100,8464,1,1,0,0,0,0)


class ProtectedRelay13C2LongTests(ProtectedField100C2LongTests):
    """Own protected R13 measured source; equal-I R12 is not equivalent."""
    BASE=ROOT/'results/throughput-20260929/trackS-c2-protected-relay13-ownlong-v1'
    NATIVE=ROOT/'queue/evidence/s4-p16-c2-protected-relay13-own100-serial-q1-v1'
    HELPER=runtime.C2_RELAY13_HELPER
    VALIDATOR=runtime.C2_RELAY13_VALIDATOR
    HELPER_PIN='9cac2b4f657e2a0527231e0574f8ec2f5259a78e45aaa2a81dcdb4dd5f5ecf45'
    VALIDATOR_PIN='b1b844a00fe53c962eb2ab7e498a80691c9d6db6bb9feddb89aec82a2d060af5'
    CONTEXT_KEY='context_protected_relay13'
    SOURCE_FAMILY='protected-relay13-58'
    STEP='normal-full-c2-protected-relay13-continuous1000-percontext'
    COMMAND_ESTIMATE=4589.529179812525
    OVERALL_ESTIMATE=5515.146258758774
    PARAMETERS=runtime.C2_FAMILIES[runtime.C2_RELAY13_HELPER]['parameters']
    CPP=runtime.C2_RELAY13_CPP

    def test_literal_oneshot_flags_and_independent_source_calendar(self):
        for model,count in zip(self.source_models(),(100,1000)):
            self.assertEqual(model['build']['parameters'],self.PARAMETERS)
            self.assertEqual(len(model['build']['sv_sources']),59)
            group=model[self.CONTEXT_KEY];g=group['geometry']
            self.assertEqual(len(group['production_generated_sha256']),58)
            self.assertEqual((g['warm_interval'],g['first_digit'],g['carry_done']),(8464,8462,12561))
            self.assertEqual((g['pointwise_accept'],g['sink_accept'],g['carry_busy_edges'],g['cache_margin']),
                             (4208,8420,4142,31))
            self.assertEqual((g['correction_cache_latency'],g['term_seed_first'],g['term_seed_last']),(78,71,74))
            self.assertEqual(runtime.c2_frame_calendar(g,count,8464,1,1,0,0,0,1),group['own_long']['own_calendar'])
            for key in ('lean_production','host_GL_assumed_unimplemented','protected_fault_rollback_claim'):
                self.assertIs(group[key],False);self.assertIs(group['own_long'][key],False)
            self.assertIs(group['CRT_transport_off'],True)
            self.assertIs(group['protected_forward_term_inverse_relays_on'],True)

    def test_source_specific_publication_fence_both_jobs_not_warm_time(self):
        m,v,p=self.fixture();warm=v['pilot_gate']['steps'][0]['validation']['measurements']['warm_edges']
        self.assertEqual(warm,[850702,854934])
        old,oldjoint=runtime.c2_publication_edges(warm)
        done,joint=runtime.c2_publication_edges(warm,1)
        self.assertEqual((done,joint),([1510167,2169631],2235167))
        self.assertEqual((done[0]-old[0],done[1]-old[1],joint-oldjoint),(1,2,2))
        longwarm=[first+999*8464+12562 for first in (204,4436)]
        self.assertEqual(runtime.c2_publication_edges(longwarm,1),([9127767,9787231],9852767))
        got=runtime.assess(m,v,p,'gfn16-pilot-c4d')
        self.assertNotIn('build_label',got);self.assertFalse(got['promotion_allowed'])

    def test_exact_captured_inverse_geometry_ast_preserves_cache_and_seed(self):
        source=self.BASE/self.FULL_DIR/'source/fpga';name='reference/stream27_protected_relay13_model.py'
        raw=(source/'lineage'/name).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),runtime.C2_RELAY13_SOURCE_PINS[name])
        nodes=[n for n in runtime.ast.parse(raw).body if isinstance(n,runtime.ast.FunctionDef) and n.name=='geometry']
        self.assertEqual(len(nodes),1);namespace={}
        exec(compile(runtime.ast.Module(body=nodes,type_ignores=[]),'[own protected R13 source geometry only]','exec'),namespace)
        group=self.source_models()[1][self.CONTEXT_KEY];g=group['geometry']
        self.assertEqual(namespace['geometry'](group['contract']['calendar_before'],inverse_ingress_reg=1,
            term_join_transport_reg=1,forward_ingress_reg=1),g)
        self.assertEqual((g['pointwise_accept'],g['sink_accept'],g['carry_busy_edges'],g['cache_margin']),(4208,8420,4142,31))
        self.assertEqual((g['crt_transport_reg'],g['crt_delivery_after_field_sink_edges']),(0,0))

    def test_cache79_naive_composition_source_substitution_and_protected_scope_refuse(self):
        m,v,p=self.fixture();key=self.CONTEXT_KEY
        changes=[('m',(key,'geometry','pointwise_accept'),4207),
            ('m',(key,'geometry','sink_accept'),8419),
            ('m',(key,'geometry','carry_busy_edges'),4143),
            ('m',(key,'geometry','cache_margin'),30),
            ('m',(key,'geometry','crt_transport_reg'),1),
            ('m',(key,'geometry','physical_feedback_FIFO_rows'),1),
            ('m',(key,'geometry','cold_correction_input_edges_added'),1),
            ('m',(key,'protected_mode_source_restored'),False),
            ('m',(key,'CRT_transport_off'),False),
            ('m',(key,'protected_forward_term_inverse_relays_on'),False),
            ('m',(key,'publication_and_fault_report_native_qualification_separate'),False),
            ('m',(key,'lean_production'),True),
            ('m',(key,'own_long','protected_fault_rollback_claim'),True),
            ('v',('forecast','generator'),runtime.C2_R12_HELPER),
            ('p',('pilot_report',),runtime.C2_FAMILIES[runtime.C2_FIELD100_HELPER]['evidence_pins']['pilot_report'])]
        for name in tuple(runtime.C2_FIELD100_FLAGS)+('FORWARD_INGRESS_REG','TERM_JOIN_TRANSPORT_REG','INVERSE_INGRESS_REG'):
            changes.append(('m',('build','parameters',name),0))
            changes.append(('m',('build','parameters',name),True))
        changes.append(('m',('build','parameters','CRT_TRANSPORT_REG'),1))
        for name in runtime.C2_RELAY13_SOURCE_PINS:
            changes.append(('m',('sources','lineage/'+name),'0'*64))
            changes.append(('m',(key,'source_sha256',name),'0'*64))
        for label,path,value in changes:
            a,b,c=copy.deepcopy((m,v,p));target={'m':a,'v':b,'p':c}[label]
            for name in path[:-1]:target=target[name]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.assess(a,b,c,'gfn16-pilot-c4d')
        for name in ('LEAN_PRODUCTION','LEAN_PROGRESS_WATCHDOG'):
            bad=copy.deepcopy(m);bad['build']['parameters'][name]=1
            with self.subTest(extra=name),self.assertRaises(ValueError):runtime.assess(bad,v,p,'gfn16-pilot-c4d')


class LeanR7C2LongTests(unittest.TestCase):
    """Own lean pilot; exact wrapper and source-correct geometry bridge only."""
    BASE=ROOT/'results/throughput-20260929/trackS-c2-lean-r7-ownlong-v1'
    NATIVE=ROOT/'queue/evidence/s4-p16-c2-lean-r7-own100-serial-q1-v1'
    FULL=BASE/'continuous1000-source-v2'

    def paths(self):
        raw=self.NATIVE/'attempt-0/collected/output/native'
        return dict(forecast=self.FULL/'forecast.json',pilot_manifest=raw/'approved-manifest.json',
            pilot_report=raw/'report.json',pilot_gate=self.NATIVE/'gate-receipt.json')

    def fixture(self):
        paths=self.paths()
        return (json.loads((self.FULL/'manifest.json').read_text()),
            {k:json.loads(p.read_text()) for k,p in paths.items()},
            {k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()})

    def test_actual_own_pilot_wrapper_duration_and_scope(self):
        m,v,p=self.fixture();got=runtime.assess(m,v,p,'gfn16-pilot-c4d')
        self.assertEqual(got['model_step'],'normal-full-c2-lean-r7-continuous1000-percontext')
        self.assertEqual(got['shape']['model_threads'],1)
        self.assertAlmostEqual(got['model_seconds_estimate'],4351.536746164893)
        self.assertAlmostEqual(got['overall_seconds_estimate'],5273.7996400234115)
        self.assertFalse(got['promotion_allowed'])
        self.assertEqual(got['build_label'],runtime.C2_LEAN_LABEL)
        self.assertFalse(got['host_gl_implemented'])
        self.assertFalse(got['rollback_implemented'])
        self.assertFalse(got['twin_fault_immunity_inherited'])
        family=runtime.c2_source_family(v['forecast'])
        self.assertEqual(family['source_family'],'lean-r7-55')
        scalar=runtime.c2_scalar_functions(family)
        self.assertEqual(scalar['config'](),m['steps'][0]['validator']['config']['parent_config'])
        self.assertNotIn(runtime.C2_LEAN_HELPER,runtime.PINS)
        self.assertNotIn(runtime.C2_LEAN_VALIDATOR,runtime.PINS)
        original=runtime.importlib.util.spec_from_file_location
        def framework_only(name,path,*args,**kwargs):
            self.assertNotIn(Path(path).name,(Path(runtime.C2_LEAN_HELPER).name,Path(runtime.C2_LEAN_VALIDATOR).name))
            return original(name,path,*args,**kwargs)
        with patch.object(runtime.importlib.util,'spec_from_file_location',side_effect=framework_only):
            runtime.assess(m,v,p,'gfn16-pilot-c4d')

    def test_exact_cpp_label_only_and_header_prefix(self):
        before=(R7FaultlocalC2LongTests.BASE/'own100-serial-v1/source/fpga'/runtime.C2_CPP).read_bytes()
        source=self.BASE/'own100-serial-v1/source/fpga'
        after=(source/runtime.C2_CPP).read_bytes()
        marker=b'return gfn16_runtime::probe(context,d);'
        self.assertEqual(before.count(marker),1)
        self.assertEqual(before.replace(marker,marker+b'std::cout<<"lean build; host GL assumed (unimplemented)\\n";'),after)
        self.assertRegex(after.decode(),r'VerilatedContext context;gfn16_runtime::configure\(context,argc,argv\);DUT d\{&context\};')
        family=runtime.C2_FAMILIES[runtime.C2_LEAN_HELPER]
        self.assertEqual(hashlib.sha256(after).hexdigest(),family['cpp_pin'])
        scalar=runtime.c2_scalar_functions(family)
        self.assertEqual(scalar['header']((source/runtime.C2_HEADER).read_bytes()),
            (self.FULL/'source/fpga'/runtime.C2_HEADER).read_bytes())

    def test_exact_bundle_assets_and_independent_healthy_calendars(self):
        m,v,p=self.fixture();source=self.FULL/'source/fpga';lean=m['lean_production']
        raw=(source/runtime.C2_LEAN_GEOMETRY_ASSET).read_bytes()
        bundle_raw=(source/runtime.C2_LEAN_BUNDLE_ASSET).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),runtime.C2_LEAN_GEOMETRY_PIN)
        self.assertEqual(hashlib.sha256(bundle_raw).hexdigest(),runtime.C2_LEAN_BUNDLE_PIN)
        asset=json.loads(raw);bundle=json.loads(bundle_raw)
        for key in ('geometry','healthy_calendars','production_generated_sha256'):
            self.assertEqual(lean[key],asset[key])
        self.assertEqual(bundle['geometry'],lean['geometry'])
        self.assertEqual(bundle['generated_sha256'],lean['production_generated_sha256'])
        self.assertEqual(len(bundle['generated_sha256']),55)
        self.assertEqual(bundle['parameters'],{k:x for k,x in m['build']['parameters'].items() if not k.startswith('EPOCH_')})
        for count in (100,1000):
            self.assertEqual(lean['healthy_calendars'][str(count)],runtime.c2_frame_calendar(lean['geometry'],count,8459,1))
        self.assertEqual(v['pilot_manifest']['r84']['geometry']['correction_cache_latency'],77)
        self.assertEqual(lean['geometry']['correction_cache_latency'],78)
        self.assertTrue(all(hashlib.sha256((source/name).read_bytes()).hexdigest()==pin for name,pin in m['sources'].items()))

    def test_wrong_wrapper_geometry_source_scope_and_twin_evidence_refuse(self):
        m,v,p=self.fixture();key='lean_production'
        changes=[('m',('steps',0,'validator','config','parent_source_sha256'),'0'*64),
            ('m',('steps',0,'validator','config'),v['forecast']['full_config']),
            ('m',('build','parameters','LEAN_PRODUCTION'),0),
            ('m',('sources',runtime.C2_CPP),runtime.C2_CPP_PIN),
            ('m',('sources',runtime.C2_LEAN_HELPER),'0'*64),
            ('m',('sources',runtime.C2_LEAN_BUNDLE_ASSET),'0'*64),
            ('m',(key,'geometry','correction_cache_latency'),77),
            ('m',(key,'healthy_calendars','1000','frames'),200),
            ('m',(key,'geometry_provenance','original_pilot_unchanged'),False),
            ('m',(key,'host_gl_implemented'),True),
            ('m',(key,'rollback_implemented'),True),
            ('m',(key,'fault_immunity_inherited'),True),
            ('m',(key,'own_serial_pilot','no_reset_reload_or_checkpoint_barriers'),False),
            ('v',('forecast','lean_build_label'),'protected build'),
            ('v',('pilot_gate','steps',0,'typed_validator_sha256'),runtime.C2_FAMILIES[runtime.C2_R7_HELPER]['typed_pin']),
            ('p',('pilot_report',),runtime.C2_FAMILIES[runtime.C2_R7_HELPER]['evidence_pins']['pilot_report'])]
        for label,path,value in changes:
            a,b,c=copy.deepcopy((m,v,p));target={'m':a,'v':b,'p':c}[label]
            for name in path[:-1]:target=target[name]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.assess(a,b,c,'gfn16-pilot-c4d')
        # Stale captured pilot r84 is descriptive; using it as authoritative is rejected.
        bad=copy.deepcopy(m);bad[key]['geometry']=v['pilot_manifest']['r84']['geometry']
        with self.assertRaises(ValueError):runtime.assess(bad,v,p,'gfn16-pilot-c4d')

    def test_actual_bind_dual_safe_stage_and_source_identity(self):
        from fpga.tools import native_long_package_v3 as package,native_long_stage_v3 as stage
        from fpga.tools import native_profile_variants_v14 as checker
        from fpga.tools.candidate_ladder import budget_from_hourly
        original=(self.FULL/'manifest.json').read_bytes()
        with tempfile.TemporaryDirectory(prefix='lean-long-metadata-') as temporary:
            out=Path(temporary).resolve();bound=out/'bound'
            result=package.bind_role(self.FULL/'manifest.json',self.FULL/'source/fpga',self.paths(),bound,host='gfn16-pilot-c4d')
            self.assertEqual(result['admission']['shape']['model_threads'],1)
            budget=out/'budget.json';budget.write_text(json.dumps(budget_from_hourly()))
            fingerprints=[]
            for profile in ('gcp-c4d-static01-v1','gcp-c4d-static23-v1'):
                dest=out/profile
                prepared=package.prepare(bound/'manifest.json',bound/'source/fpga',profile,'metadata-lean-'+profile,'run',dest,budget)
                _,ticket,manifest,_=stage.worker().inspect_archive(dest/'package.tar.gz',prepared['archive_sha256'],prepared['ticket_sha256'])
                family=(package.EXECUTOR_SHA,stage.PACKAGE_SHA)
                with patch.object(checker,'LONG_FAMILIES',checker.LONG_FAMILIES|{family}),patch.dict(checker.LONG_PHASES,{family:runtime.PHASE_PIN}):
                    fingerprints.append(checker.functional_fingerprint(manifest,ticket['budget'],dest/'capture/source/fpga')['sha256'])
                runtime.duration.validate(manifest,dest/'capture/source/fpga','gfn16-pilot-c4d')
                self.assertEqual(ticket['max_seconds'],10800)
                self.assertEqual(len(manifest['build']['sv_sources']),56)
                self.assertEqual(manifest['sources'][runtime.C2_LEAN_BUNDLE_ASSET],runtime.C2_LEAN_BUNDLE_PIN)
            self.assertEqual(fingerprints[0],fingerprints[1])
        self.assertEqual((self.FULL/'manifest.json').read_bytes(),original)

    def test_captured_r9_stays_exact_and_qualified(self):
        from fpga.tools import native_profile_variants_v14 as checker
        base=R9RegisteredErrorC2LongTests.BASE/'continuous1000-packet-v1'
        fingerprints=[]
        for name in ('packet-01','packet-23'):
            directory=base/name;m=json.loads((directory/'manifest.json').read_text());t=json.loads((directory/'ticket.json').read_text())
            family=tuple(m['sources'][rel] for rel in ('tools/native_long_class_v2.py','tools/native_long_package_v3.py'))
            self.assertEqual(family,('68a8cbe5a5152becc799597db78178399004ac1a6c3e196cd3d7a538cb372c99','3755e800988c9cff196e549a279302a623816412a7d5cb7999ac11070bf1b147'))
            self.assertIn(family,checker.LONG_FAMILIES)
            fingerprints.append(checker.functional_fingerprint(m,t['budget'],directory/'capture/source/fpga')['sha256'])
        self.assertEqual(fingerprints[0],fingerprints[1])


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

    def test_r2_boundary_register_keeps8459_but_has_own_seed_cache_calendar(self):
        # Source-only R95 readiness. Actual R2 pilot/forecast admission stays
        # unavailable until its own frozen helper and selected native receipt.
        base=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-boundary-native-v1/full-normal'
        bundle=json.loads((base/'production-bundle.json').read_text())
        g=bundle['geometry']
        self.assertEqual(g['warm_interval'],8459)
        self.assertEqual(g['first_digit'],8458)
        self.assertEqual(g['carry_done'],12557)
        self.assertEqual(g['correction_cache_latency'],78)
        self.assertEqual([g['term_seed_first'],g['term_seed_last']],[71,74])
        from fpga.reference import s4_two_context_model_v1 as ports
        for count in (100,1000):
            got=runtime.c2_frame_calendar(g,count,8459,boundary_inputreg=1)
            frames=sorted([ports.Frame(c,1,((65534,42)[c]+k)&65535,k,
                k*8459+c*4229,(604832956,999999937)[c])
                for c in (0,1) for k in range(count)],key=lambda row:row.start)
            expected=json.loads(json.dumps(ports.correction_calendar(frames,g,pair_interval=60)))
            self.assertEqual(got['correction'],expected)
            self.assertEqual(got['lease_peak'],3)
            self.assertEqual(got['correction'][2]['margin'],30)
        with self.assertRaises(ValueError):runtime.c2_frame_calendar(g,1000,8459)
        for selector in (True,2,-1):
            with self.subTest(selector=selector),self.assertRaises(ValueError):
                runtime.c2_frame_calendar(g,1000,8459,boundary_inputreg=selector)
        for key in ('warm_interval','carry_done','first_digit','correction_cache_latency','term_seed_first',
                    'term_seed_last','boundary_inputreg','boundary_frontend_added'):
            bad=copy.deepcopy(g);bad[key]+=1
            with self.subTest(key=key),self.assertRaises(ValueError):
                runtime.c2_frame_calendar(bad,1000,8459,boundary_inputreg=1)


class R14HostOffloadLongTests(unittest.TestCase):
    """Actual metadata/capture checks only; no R14 import or full-N arithmetic."""
    BASE=ROOT/'results/throughput-20260929/trackS-r14-host-offload-ownlong-v1'
    FULL=BASE/'continuous1000-source-v1'
    NATIVE=ROOT/'queue/evidence/s4-r14-host-offload-own100-q1-v1'

    def paths(self):
        raw=self.NATIVE/'attempt-0/collected/output/native'
        return dict(forecast=self.FULL/'own-pilot-forecast.json',pilot_manifest=raw/'approved-manifest.json',
            pilot_report=raw/'report.json',pilot_gate=self.NATIVE/'gate-receipt.json')

    def fixture(self):
        paths=self.paths()
        return (json.loads((self.FULL/'manifest.json').read_bytes()),
            {k:json.loads(p.read_bytes()) for k,p in paths.items()},
            {k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()})

    def test_actual_own_r14_serial_full_command_forecast_and_no_parent_calendar(self):
        m,v,p=self.fixture();got=runtime.duration_for(1).assess(m,v,p,'gfn16-pilot-c4d')
        self.assertEqual(got['status'],'PASS_R14_own_measured_finite_duration_only')
        self.assertAlmostEqual(got['model_seconds_estimate'],2552.3835476651584)
        self.assertAlmostEqual(got['overall_seconds_estimate'],3861.1771871018937)
        self.assertEqual(got['model_step'],runtime.R14_FULL_STEP)
        self.assertFalse(got['promotion_allowed']);self.assertFalse(got['FPGA_throughput_or_clock_claim'])
        self.assertTrue(got['host_phase_excluded_from_FPGA'])
        self.assertEqual(runtime.model_threads(m),1)
        for count in (4,8):
            with self.subTest(count=count),self.assertRaises(ValueError):
                runtime.duration_for(count).assess(m,v,p,'gfn16-pilot-c4d')
        # All private numeric/validator source pins remain functional identity.
        self.assertNotIn(runtime.R14_HELPER,runtime.PINS)
        self.assertNotIn(runtime.R14_VALIDATOR,runtime.PINS)

    def test_exact_scalar_header_prefix_native_runtime_and_reference_closure(self):
        m,v,p=self.fixture();pilot=self.BASE/'own100-v1/source/fpga';full=self.FULL/'source/fpga'
        for count,source,key in ((100,pilot,'pilot_sha256'),(1000,full,'full_sha256')):
            self.assertEqual((source/runtime.C2_HEADER).read_bytes(),runtime.r14_header(count))
            self.assertEqual(hashlib.sha256(runtime.r14_header(count)).hexdigest(),runtime.R14_HEADER_DELTA[key])
        self.assertEqual([row[:100] for row in runtime.r14_bits(1000)],runtime.r14_bits(100))
        self.assertEqual(sum(map(sum,runtime.r14_bits(1000))),1022)
        self.assertEqual(len(m['build']['sv_sources']),66)
        self.assertTrue(all(hashlib.sha256((full/name).read_bytes()).hexdigest()==pin for name,pin in m['sources'].items()))
        cpp=(full/runtime.R14_CPP).read_text()
        self.assertLess(cpp.index('gfn16_runtime::configure(context,argc,argv)'),cpp.index('DUT d(&context)'))
        for marker in ('R14_LONG_EVERY_EDGE_CALENDAR','R14_LONG_RAW_DONE_W_PLUS_TWO',
                       'R14_LONG_RAW_OWNER_ORDER','R14_LONG_ALL_N_REFERENCE','R14_LONG_FINITE_NO_RELOAD'):
            self.assertIn(marker,cpp)
        self.assertEqual(hashlib.sha256((full/runtime.R14_CPP).read_bytes()).hexdigest(),runtime.R14_CPP_PIN)

    def test_one_actual_prediction_ast_without_private_candidate_import(self):
        m,v,p=self.fixture();original=runtime.importlib.util.spec_from_file_location
        def framework_only(name,path,*args,**kwargs):
            self.assertNotIn(Path(path).name,(Path(runtime.R14_HELPER).name,Path(runtime.R14_VALIDATOR).name))
            return original(name,path,*args,**kwargs)
        with patch.object(runtime.importlib.util,'spec_from_file_location',side_effect=framework_only):
            predict=runtime.r14_predictor();got=runtime.assess(m,v,p,'gfn16-pilot-c4d')
            self.assertEqual(predict(145.85048843800905,550.8754252590006),v['forecast']['forecast'])
            self.assertEqual(got['shape']['outer_seconds'],10800)
        for count in (True,1,99,1001):
            with self.subTest(count=count),self.assertRaises(ValueError):runtime.r14_config(count)

    def test_wrong_source_parent_ledger_words_scope_and_measurements_refuse(self):
        base,values,pins=self.fixture()
        changes=[('m',('sources',runtime.R14_CPP),'0'*64),
            ('m',('sources',runtime.R14_HELPER),'0'*64),('m',('sources',runtime.R14_VALIDATOR),'0'*64),
            ('m',('sources',runtime.C2_HEADER),runtime.R14_HEADER_DELTA['pilot_sha256']),
            ('m',('build','parameters','HOST_OFFLOAD'),0),('m',('build','parameters','HOST_OFFLOAD'),True),
            ('m',('build','parameters','LEAN_PRODUCTION'),1),('m',('build','runtime_threads'),8),
            ('m',('probe','expected_json','context_threads'),8),('m',('fixed_execution',),{}),
            ('m',('r14_own_long','no_reload'),False),('m',('r14_own_long','raw_done_warm_plus'),655360),
            ('m',('r14_own_long','host_C_cold_final'),False),('m',('r14_own_long','initial_resets'),2),
            ('m',('r14_own_long','count_per_context'),100),('m',('steps',0,'validator','config','count'),100),
            ('m',('steps',0,'validator','config','first'),[204,4435]),
            ('m',('steps',0,'argv'),['{exe}','1000']),('m',('test_role',),'deliberate_fault'),
            ('v',('forecast','schema'),runtime.C2_SCHEMA),('v',('forecast','generator_sha256'),'0'*64),
            ('v',('forecast','FPGA_throughput_or_clock_claim'),True),('v',('forecast','parent_forecast_inherited'),True),
            ('v',('forecast','forecast','measured_command_seconds'),1),
            ('v',('forecast','forecast','overall_seconds_estimate'),1),
            ('v',('pilot_manifest','sources',runtime.C2_HEADER),'0'*64),
            ('v',('pilot_gate','steps',0,'typed_validator_sha256'),'0'*64),
            ('v',('pilot_gate','status'),'FAIL'),('v',('pilot_report','seconds'),float('inf')),
            ('v',('pilot_report','model_threads'),8),('v',('pilot_report','compile_workers'),4),
            ('v',('pilot_report','host'),'gfn16-azure-sim-f32'),
            ('v',('pilot_report','limits','cpu_max'),['800000','100000']),
            ('v',('pilot_report','limits','swap_max_bytes'),1),
            ('p',('pilot_report',),'0'*64)]
        for label,path,value in changes:
            m,v,p=copy.deepcopy((base,values,pins));target={'m':m,'v':v,'p':p}[label]
            for name in path[:-1]:target=target[name]
            target[path[-1]]=value
            with self.subTest(path=path),self.assertRaises((ValueError,KeyError)):
                runtime.assess(m,v,p,'gfn16-pilot-c4d')
        # Mutate all copies together: shape/source/typed calendar guards still reject.
        for key,value in (('checked_words',65536),('done_edges',[1509768,2169232]),
                          ('cycles',2235167),('input_words',131072),('initial_resets',2),
                          ('raw_words',262144),('model_seconds',float('nan'))):
            m,v,p=copy.deepcopy((base,values,pins))
            for native in (v['forecast']['pilot_native_validation'],v['pilot_gate']['steps'][0]['validation'],
                           v['pilot_report']['validations'][runtime.R14_PILOT_STEP]):
                native['measurements'][key]=value
            with self.subTest(measurement=key),self.assertRaises(ValueError):runtime.assess(m,v,p,'gfn16-pilot-c4d')

    def test_actual_bind_dual_safe_stage_and_same_functional_identity(self):
        from fpga.tools import native_long_package_v3 as package,native_long_stage_v3 as stage
        from fpga.tools import native_profile_variants_v14 as checker
        from fpga.tools.candidate_ladder import budget_from_hourly
        original=(self.FULL/'manifest.json').read_bytes()
        with tempfile.TemporaryDirectory(prefix='r14-long-metadata-') as temporary:
            out=Path(temporary).resolve();bound=out/'bound'
            result=package.bind_role(self.FULL/'manifest.json',self.FULL/'source/fpga',self.paths(),bound,host='gfn16-pilot-c4d')
            self.assertEqual(result['admission']['status'],'PASS_R14_own_measured_finite_duration_only')
            budget=out/'budget.json';budget.write_text(json.dumps(budget_from_hourly()));fingerprints=[]
            for profile in ('gcp-c4d-static01-v1','gcp-c4d-static23-v1'):
                dest=out/profile
                prepared=package.prepare(bound/'manifest.json',bound/'source/fpga',profile,'metadata-r14-'+profile,'run',dest,budget)
                _,ticket,manifest,_=stage.worker().inspect_archive(dest/'package.tar.gz',prepared['archive_sha256'],prepared['ticket_sha256'])
                runtime.duration.validate(manifest,dest/'capture/source/fpga','gfn16-pilot-c4d')
                fingerprint=checker.functional_fingerprint(manifest,ticket['budget'],dest/'capture/source/fpga')
                fingerprints.append(fingerprint['sha256'])
                self.assertNotIn(runtime.R14_HELPER,fingerprint['ignored_exact_controls'])
                self.assertEqual(ticket['max_seconds'],10800)
                self.assertEqual(manifest['build']['runtime_threads'],1)
                self.assertEqual(manifest['steps'][0]['validator']['config']['count'],1000)
                self.assertEqual(len(manifest['build']['sv_sources']),66)
            self.assertEqual(fingerprints[0],fingerprints[1])
        self.assertEqual((self.FULL/'manifest.json').read_bytes(),original)

    def test_captured_r13_field100_family_is_retained_without_workspace_substitution(self):
        from fpga.tools import native_profile_variants_v14 as checker
        self.assertIn(checker.PRE_R14_LONG,checker.LONG_FAMILIES)
        self.assertEqual(checker.LONG_PHASES[checker.PRE_R14_LONG],runtime.PHASE_PIN)
        for folder in ('trackS-c2-protected-relay13-ownlong-v1','trackS-c2-protected-field100-ownlong-v1'):
            base=ROOT/'results/throughput-20260929'/folder/'continuous1000-packet-v1'
            fingerprints=[]
            for name in ('packet-01','packet-23'):
                path=base/name;m=json.loads((path/'manifest.json').read_bytes());t=json.loads((path/'ticket.json').read_bytes())
                family=tuple(m['sources'][k] for k in ('tools/native_long_class_v2.py','tools/native_long_package_v3.py'))
                self.assertEqual(family,checker.PRE_R14_LONG)
                fingerprints.append(checker.functional_fingerprint(m,t['budget'],path/'capture/source/fpga')['sha256'])
            self.assertEqual(fingerprints[0],fingerprints[1])


if __name__=='__main__':unittest.main()

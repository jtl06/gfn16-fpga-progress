"""Existing long policy, real closed role templates, mocked scalar pilot only."""
import copy
import ast
import functools
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import types
from contextlib import nullcontext
import unittest
from unittest.mock import patch

from fpga.tools import native_long_class_v2 as runtime
from fpga.tools import native_long_package_v3 as package
from fpga.tools import native_long_stage_v3 as stage

ROOT=Path(__file__).resolve().parents[1]
ROLE=ROOT/'artifacts/s4-p8-canon1-continuous1000-role-v1'
PILOT=ROOT/'artifacts/s4-p8-canon1-continuous100-role-v1'


def captured_azure_meter_fixture(test):
    """Replay the declared old Azure meter in an isolated, exact-source tree.

    The live meter has advanced under wrap-up authority, so the old long
    descriptor must not be silently relabelled as current Azure admission.
    No captured file, live financial guard, package or queue is modified.
    """
    @functools.wraps(test)
    def replay(self):
        frozen=ROOT/'results/throughput-20260929/s4-p16-diet-continuous1000-thread8-native-v1/packet-v3/capture/source/fpga/cloud/host_hours_azure_signed_v1.py'
        meter_pin='9c3d902e3da0969145c4148f06a51ec9ca22a322513068074f7b338cb8ddf137'
        self.assertEqual(hashlib.sha256(frozen.read_bytes()).hexdigest(),meter_pin)
        live_meter=ROOT/'cloud/host_hours_azure_signed_v1.py'
        live_pin=hashlib.sha256(live_meter.read_bytes()).hexdigest()
        spec=importlib.util.spec_from_file_location('_captured_azure_meter_fixture',frozen)
        meter=importlib.util.module_from_spec(spec);spec.loader.exec_module(meter)
        # Its unchanged parser reads only individually pinned repository data;
        # __file__ remains the genuine captured source for descriptor identity.
        meter.ROOT=ROOT
        with tempfile.TemporaryDirectory(prefix='captured-azure-meter-') as temporary:
            isolated=Path(temporary).resolve()/'fpga';(isolated/'tools').mkdir(parents=True)
            worker=package.worker()
            files={worker.source_name(name):worker.helper_path(name) for name in worker.PINS}
            files['tools/native_long_package_v3.py']=Path(package.__file__)
            for version in range(1,15):
                name=f'tools/native_profile_variants_v{version}.py'
                files[name]=ROOT/name
            for version in (1,2,3):
                for kind in ('package','stage'):
                    name=f'tools/native_threaded_wide_{kind}_v{version}.py'
                    files[name]=ROOT/name
            for name,path in files.items():
                target=isolated/name;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(path,target)
                self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),hashlib.sha256(path.read_bytes()).hexdigest())
            def financial_closure(descriptor):
                self.assertEqual(descriptor['checker_sha256'],meter_pin)
                for name,pin in meter.evidence_pins(descriptor).items():
                    source=frozen if name=='cloud/host_hours_azure_signed_v1.py' else ROOT/name
                    self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),pin)
                    target=isolated/name;target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(source,target)
            old_budget=json.loads((ROOT/'results/throughput-20260929/s4-p16-diet-continuous1000-thread8-native-v1/budget.json').read_text())
            financial_closure(old_budget)
            spec=importlib.util.spec_from_file_location('_current_long_with_captured_meter',isolated/'tools/native_long_package_v3.py')
            closed=importlib.util.module_from_spec(spec);spec.loader.exec_module(closed)
            actual_prepare=closed.prepare
            def prepare(*args,**kwargs):
                financial_closure(json.loads(Path(args[6] if len(args)>6 else kwargs['budget']).read_text()))
                return actual_prepare(*args,**kwargs)
            closed.prepare=prepare
            import fpga.cloud as cloud
            from fpga.tools import global_queue_v1 as queue, native_profile_variants_v14 as matcher
            # The real intake bytecode uses the exact same checker source,
            # now rooted at this closed historical financial fixture.
            identity=types.FunctionType(queue.functional_identity.__code__,
                dict(queue.functional_identity.__globals__,FPGA=isolated))
            with patch.object(sys.modules[__name__],'package',closed), \
                 patch.dict(sys.modules,{'fpga.cloud.host_hours_azure_signed_v1':meter}), \
                 patch.object(cloud,'host_hours_azure_signed_v1',meter,create=True), \
                 patch.object(queue,'functional_identity',identity), \
                 patch.object(matcher,'HERE',isolated/'tools'):
                result=test(self)
            self.assertEqual(hashlib.sha256(frozen.read_bytes()).hexdigest(),meter_pin)
            self.assertEqual(hashlib.sha256(live_meter.read_bytes()).hexdigest(),live_pin)
            return result
    return replay


class CurrentLongTests(unittest.TestCase):
    def test_captured_meter_replay_does_not_grant_current_azure_admission(self):
        budget=json.loads((ROOT/'results/throughput-20260929/s4-p16-diet-continuous1000-thread8-native-v1/budget.json').read_text())
        current=hashlib.sha256((ROOT/'cloud/host_hours_azure_signed_v1.py').read_bytes()).hexdigest()
        self.assertNotEqual(current,budget['checker_sha256'])
        with self.assertRaisesRegex(ValueError,'signed meter source'):
            package.worker(budget,8)
        changed=dict(budget,checker_sha256=current)
        with self.assertRaisesRegex(ValueError,'exact source-bound serial Azure10815 descriptor'):
            package.azure_binding(changed,changed['host'])

    def test_future_compiler_count_uses_actual_own_rss_and_reserved_cores(self):
        bound=ROOT/'results/throughput-20260929/s4-p16-diet-continuous1000-thread8-native-v1/bound'
        manifest=json.loads((bound/'manifest.json').read_text())
        report=json.loads((bound/'source/fpga'/manifest['runtime_duration']['evidence']['pilot_report']['path']).read_text())
        receipt=runtime.compilation_bound(manifest,report,3)
        self.assertEqual(receipt['compiler_peak_rss_bytes'],1862980*1024)
        self.assertLess(receipt['estimated_peak_bytes'],8<<30)
        for count in (True,0,-1,4,8,9):
            with self.subTest(count=count),self.assertRaises(ValueError):runtime.compilation_bound(manifest,report,count)
        for bad in (True,-1,0,float('inf')):
            wrong=copy.deepcopy(report)
            next(row for row in wrong['steps'] if row['name']=='build')['native_child_usage']['peak_rss_kib']=bad
            with self.subTest(rss=bad),self.assertRaises(ValueError):runtime.compilation_bound(manifest,wrong,3)
        actual=copy.deepcopy(manifest);actual['fixed_execution']['runtime_allocation']['compile_workers']=3
        actual['compile_allocation']=receipt
        selected=runtime.selected_for(actual)
        self.assertEqual(selected['compile_workers'],3)
        self.assertEqual(selected['cpus'],list(range(8)))
        old=runtime.build_identity(manifest,runtime.selected_for(manifest))
        new=runtime.build_identity(actual,selected)
        self.assertNotEqual(old['build_key'],new['build_key'])
        self.assertEqual(new['identity']['model_threads'],8)
        self.assertEqual(new['identity']['compile_workers'],3)
        self.assertEqual(new['identity']['runtime_allocation']['compile_workers'],3)
        # A source with a smaller actual peak may use all eight owned cores;
        # this is a synthetic sizing fixture, not P16 memory qualification.
        tiny=copy.deepcopy(report)
        next(row for row in tiny['steps'] if row['name']=='build')['native_child_usage']['peak_rss_kib']=100000
        self.assertEqual(runtime.compilation_bound(manifest,tiny,8)['compile_workers'],8)

    @captured_azure_meter_fixture
    def test_future_override_packages_truthful_config_without_mutating_role(self):
        bound=ROOT/'results/throughput-20260929/s4-p16-diet-continuous1000-thread8-native-v1'
        raw=(bound/'bound/manifest.json').read_bytes()
        with tempfile.TemporaryDirectory(prefix='compile-allocation-test-',dir=ROOT/'results') as temporary:
            out=Path(temporary).resolve()/'packet'
            prepared=package.prepare(bound/'bound/manifest.json',bound/'bound/source/fpga',
                'azure-burst16-thread-wide07-v1','metadata-only-compile3','run',out,bound/'budget.json',compile_workers=3)
            payload,ticket,captured,placed=stage.worker().inspect_archive(out/'package.tar.gz',prepared['archive_sha256'],prepared['ticket_sha256'])
            self.assertEqual(captured['fixed_execution']['runtime_allocation']['compile_workers'],3)
            self.assertEqual(ticket['fixed_execution'],captured['fixed_execution'])
            self.assertEqual(placed['compile_workers'],3)
            self.assertEqual(captured['build']['runtime_threads'],8)
            runtime.duration_for(8).validate(captured,out/'capture/source/fpga',captured['host'])
            self.assertEqual((bound/'bound/manifest.json').read_bytes(),raw)
            broken=copy.deepcopy(captured);broken['compile_allocation']['compiler_peak_rss_bytes']-=1
            with self.assertRaisesRegex(ValueError,'compiler RAM estimate'):
                runtime.duration_for(8).validate(broken,out/'capture/source/fpga',captured['host'])
            before=json.loads(payload['ticket.json']);before['fixed_execution']['runtime_allocation']['compile_workers']=8
            with self.assertRaises(ValueError):stage.worker().profile_from_payload(payload,before,captured['sources'])
            # Real public intake in an isolated queue, including the own typed
            # pilot lookup and a distinct truthful compile-allocation identity.
            from fpga.tools import global_queue_v1 as queue
            declared=json.loads((bound/'global-ticket-v3.json').read_text())
            declared.update(id='isolated-own-p16-compile3-normal')
            declared.pop('normal_test_submitted_at_utc',None);declared.pop('infra_retry_of',None)
            entry=declared['packages'][0]
            entry.update(runner_sha256=stage.PACKAGE_SHA,stager_sha256=hashlib.sha256(Path(stage.__file__).read_bytes()).hexdigest(),
                         archive=str(out/'package.tar.gz'),sha256=prepared['archive_sha256'],
                         ticket_sha256=prepared['ticket_sha256'],manifest_sha256=hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest(),
                         native_root=prepared['native_root'],worker_id=ticket['id'],fixed_execution=captured['fixed_execution'])
            declared['fixed_execution']=captured['fixed_execution']
            known=queue.registry();pilot=known['r75-p16-diet-threads8-q1-v1']
            ancestry={};todo=[pilot['id']]
            while todo:
                name=todo.pop()
                if name in ancestry:continue
                ancestry[name]=known[name]
                todo.extend(row['id'] if type(row) is dict else row for row in known[name].get('after',[]))
            isolated=Path(temporary)/'queue';isolated.mkdir()
            for name in ('pending','running','done'): (isolated/name).mkdir()
            (isolated/'loop-state.json').write_text(json.dumps(dict(status='running',consumer_contract=queue.CONSUMER_CONTRACT)))
            input_path=Path(temporary)/'global.json';input_path.write_text(json.dumps(declared))
            with patch.object(queue,'QUEUE',isolated),patch.object(queue,'registry',return_value=ancestry):
                result=queue.submit(input_path)
                self.assertEqual(result['status'],'pending')
                submitted=json.loads((isolated/'pending'/('isolated-own-p16-compile3-normal.json')).read_text())
                self.assertEqual(submitted['fixed_execution']['runtime_allocation']['compile_workers'],3)
                with self.assertRaisesRegex(ValueError,'unique queue id'):queue.submit(input_path)

    def fixture(self):
        full=json.loads((ROLE/'manifest.json').read_text())
        pilot=json.loads((PILOT/'manifest.json').read_text())
        pins={k:hashlib.sha256(k.encode()).hexdigest() for k in runtime.duration.EVIDENCE}
        counters=dict(pilot['continuous']['counts_ordinary_source_projection'],special=0)
        native=dict(status='PASS_expected_contracts',canonical_pipe_stages=1,base=604832956,
            operations=100,independent_reference_equal=True,
            candidate_root_sha256=full['continuous']['plan']['candidate_root_sha256'],
            final_actual_sha256='a'*64,final_expected_sha256='a'*64,
            counts=counters,phase_wall_ms=dict(candidate_ms=1000,reference_ms=100,read_ms=100))
        report=dict(host='gfn16-azure-sim-f32',status='completed_native_commands_unreviewed',
            probe=full['probe']['expected_json'],model_threads=1,
            manifest_sha256=pins['pilot_manifest'],seconds=2.5,
            steps=[dict(name=runtime.phase.STEP,returncode=0,error=None,sha256='b'*64,seconds=1.5)],
            validations={runtime.phase.STEP:native})
        gate=dict(status='PASS_expected_contracts',promotion_allowed=False,
            manifest_sha256=pins['pilot_manifest'],report_sha256=pins['pilot_report'],
            steps=[dict(name=runtime.phase.STEP,actual_returncode=0,stdout_sha256='b'*64,validation=native)])
        forecast=dict(schema='stream27-s4-continuous-phase-forecast-v1',status='PASS_S4_measured_phase_forecast',
            generator_sha256=runtime.PHASE_PIN,compatible_hosts=[report['host']],
            short_manifest_sha256=pins['pilot_manifest'],short_report_sha256=pins['pilot_report'],short_gate_sha256=pins['pilot_gate'],
            source_model_build=full['build'],source_model_pins=dict(full['sources']),canonical_pipe_stages=1,
            pilot_native_validation=native,forecast=runtime.phase.predict(counters['candidate_cycles'],
                full['continuous']['counts_ordinary_source_projection']['candidate_cycles']+65536,
                native['phase_wall_ms'],1.5,2.5))
        return full,dict(forecast=forecast,pilot_manifest=pilot,pilot_report=report,pilot_gate=gate),pins

    def test_actual_source_template_phase_assess_and_refusals(self):
        full,values,pins=self.fixture()
        receipt=runtime.assess(full,values,pins,'gfn16-azure-sim-f32')
        self.assertEqual(receipt['shape'],runtime.base.duration.SHAPE)
        self.assertFalse(receipt['promotion_allowed'])
        for change in ('host','source','header','counts','timing','infinity','threads','proof','outcome'):
            m,v=copy.deepcopy((full,values))
            if change=='host':v['pilot_report']['host']='gfn16-pilot-c4d'
            elif change=='source':m['sources'][m['build']['cpp_source']]='0'*64
            elif change=='header':v['forecast']['source_model_pins'].pop('rtl/tb/native_runtime_context_v1.h')
            elif change=='counts':v['pilot_gate']['steps'][0]['validation']['counts']['readbacks']=2
            elif change=='timing':v['forecast']['forecast']['continuous_command_seconds_estimate']+=1
            elif change=='infinity':v['pilot_report']['seconds']=float('inf')
            elif change=='threads':m['probe']['expected_json']['model_threads']=2
            elif change=='proof':v['forecast']['generator_sha256']='0'*64
            else:m['steps'][0]['expected_returncode']=1
            with self.subTest(change=change),self.assertRaises((ValueError,KeyError)):
                runtime.assess(m,v,pins,'gfn16-azure-sim-f32')

    def test_host_binding_reuses_exact_frozen_copy_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);report=base/'report.json'
            report.write_text(json.dumps(dict(host='gfn16-azure-sim-f32')))
            paths=dict(pilot_report=report)
            # Exercise both host constants in the real trusted inherited function;
            # no artifacts are written because assessment deliberately stops.
            with patch.object(package.duration,'assess',side_effect=RuntimeError('reached actual Azure host')) as assess:
                full,values,pins=self.fixture()
                for key in package.duration.EVIDENCE:
                    path=base/(key+'.json');path.write_text(json.dumps(values[key]));paths[key]=path
                manifest=base/'manifest.json';manifest.write_text(json.dumps(full))
                with self.assertRaisesRegex(RuntimeError,'actual Azure host'):
                    package.bind_role(manifest,ROLE/'source/fpga',paths,base/'bound')
                self.assertEqual(assess.call_args.args[-1],'gfn16-azure-sim-f32')
            with self.assertRaises(ValueError):package.bind_role(manifest,ROLE/'source/fpga',paths,base/'other','gfn16-pilot-c4d')

    def test_safe_data_only_all_eight_existing_pairs(self):
        value=stage.worker()
        self.assertIs(value.stage.__globals__,value.__dict__)
        raw=(ROOT/stage.ENVELOPE).read_bytes()
        payload={'capture/source/fpga/'+stage.ENVELOPE:raw}
        sources={stage.ENVELOPE:stage.ENVELOPE_SHA,'tools/native_long_class_v2.py':package.EXECUTOR_SHA,
            'tools/native_long_package_v3.py':stage.PACKAGE_SHA}
        names=json.loads(raw)['profiles']
        for name in names:
            placement=value.profile_from_payload(payload,dict(profile=name),sources)
            self.assertEqual((len(placement['cpus']),placement['memory_bytes'],placement['cpu_quota_percent']),(2,8*2**30,200))
        for name in ('azure-burst16-static01-v1','azure-burst16-static24g01-v1'):
            with self.assertRaises(ValueError):value.profile_from_payload(payload,dict(profile=name),sources)
        broken=dict(sources);broken[stage.ENVELOPE]='0'*64
        with self.assertRaises(ValueError):value.profile_from_payload(payload,dict(profile=next(iter(names))),broken)

    def test_live_namespace_and_descriptor_not_repeated_money_admission(self):
        value=runtime.parent('azure-burst16-static8g01-v1')
        self.assertIs(value.load_manifest.__globals__,value.__dict__)
        self.assertEqual(set(value.PROFILES),{'gfn16-azure-sim-f32'})
        self.assertEqual(runtime.profile('azure-burst16-static8g01-v1')['memory_bytes'],8*2**30)
        descriptor=dict(schema='azure-host-hours-budget-v5',kind='azure-host-hours-v5',provider='azure',host='gfn16-azure-sim-f32',
            max_seconds=10815,checker_sha256='9c3d902e3da0969145c4148f06a51ec9ca22a322513068074f7b338cb8ddf137',
            source_sha256='a'*64,profile=dict(sha256='b'*64))
        package.azure_binding(descriptor,descriptor['host'])
        for key,value in [('max_seconds',3715),('source_sha256','x'*64),('provider','gcp')]:
            wrong=copy.deepcopy(descriptor);wrong[key]=value
            with self.assertRaises(ValueError):package.azure_binding(wrong,descriptor['host'])

    @captured_azure_meter_fixture
    def test_real_measured_bound_role_closed_packet_and_safe_inspection(self):
        bound=ROOT/'results/throughput-20260929/s4-p8-canon1-continuous-bound-v1'
        manifest=json.loads((bound/'manifest.json').read_text())
        source=bound/'source/fpga'
        # Only package/inspect source metadata; the actual Linux pilot evidence
        # is consumed as data, and no model or numerical reference is executed.
        from fpga.cloud import host_hours_azure_signed_v1 as meter
        from fpga.tools import global_queue_v1 as queue
        provider=queue.provider_capture_ref()
        profile=runtime.profile('azure-burst16-static8g01-v1')
        descriptor=meter.make_budget(profile['host'],10815,str(Path(provider['path']).relative_to(ROOT)),provider['sha256'],
            package.source_identity(manifest),profile['profile_sha256'],
            transition_path='results/throughput-20260929/azure-sim-resize-r49-v1/rate-transition-v1.json',
            transition_sha256='c4923266e1fabaeeca7cbf6e5f2444455c299accf5ed89c122927c47ed56ac92')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();budget=root/'budget.json'
            budget.write_text(json.dumps(descriptor))
            prepared=package.prepare(bound/'manifest.json',source,'azure-burst16-static8g01-v1',
                'metadata-long-azure8-closed','run',root/'packet',budget)
            value=stage.worker()
            payload,ticket,captured,_=value.inspect_archive(root/'packet/package.tar.gz',
                prepared['archive_sha256'],prepared['ticket_sha256'])
            self.assertEqual(ticket['max_seconds'],10800)
            self.assertEqual(captured['runtime_duration']['shape'],runtime.duration.SHAPE)
            self.assertEqual(value.profile_from_payload(payload,ticket,captured['sources'])['memory_bytes'],8*2**30)

    def test_actual_execute_routes_through_actual_host_selector_before_any_model(self):
        def safe_static_execute(path,pin,out):
            # The real outer adapters inject their actual profile function into
            # this harmless code; no process, HDL or physical lock is touched.
            return profile(json.loads(Path(path).read_text())['cpu_profile'])
        safe=types.SimpleNamespace(sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest(),
            load=lambda name:types.SimpleNamespace(lock=lambda *args:nullcontext(7)),execute=safe_static_execute)
        for selector,adapter in [('azure-burst16-static8g01-v1',runtime.burst.policy.policy.host),
                                 ('gcp-c4d-static24g23-v1',runtime.base.base.policy.policy.host)]:
            with self.subTest(selector=selector),tempfile.TemporaryDirectory() as temporary:
                path=Path(temporary)/'manifest.json';path.write_text(json.dumps(dict(cpu_profile=selector,source_root=temporary)))
                with patch.dict(adapter.execute_with_parent.__globals__,dict(static_module=lambda:safe)),\
                     patch.object(runtime.duration,'validate',return_value=dict(model_step=runtime.phase.STEP)) as check:
                    selected=runtime.execute(path,hashlib.sha256(path.read_bytes()).hexdigest(),Path(temporary)/'output')
                self.assertEqual(selected['profile_id'],selector)
                self.assertEqual(check.call_args.args[-1],selected['host'])
                self.assertEqual(selected['memory_bytes'],(8 if selector.startswith('azure') else 24)*2**30)

    def test_retained_failure_is_exact_precommand_cause_not_numerical(self):
        from fpga.tools import global_queue_v1 as queue
        path=ROOT/'queue/done/s4-p8-canon1-continuous1000-normal-q1-v1.json'
        original=json.loads(path.read_text())
        self.assertTrue(queue.verified_long_selector_failure(original))
        for key,value in [('ExecMainStatus','0'),('MainPID','1'),('ControlGroup','/live')]:
            wrong=copy.deepcopy(original);wrong['result']['properties'][key]=value
            self.assertFalse(queue.verified_long_selector_failure(wrong))
        wrong=copy.deepcopy(original);wrong['result']['queue_report']['error']="ValueError('arithmetic mismatch')"
        self.assertFalse(queue.verified_long_selector_failure(wrong))

    def wide_fixture(self,count=8):
        full,values,pins=self.fixture();pilot=values['pilot_manifest']
        config=runtime.wide.base().load('native_thread_config_v1.py',runtime.wide.base().RUNTIME_SHA)
        selected=runtime.profile('azure-burst16-thread-wide815-v1')
        from fpga.tools.native_threaded_wide_package_v3 import execution_contract
        execution=execution_contract(selected)
        for model in (full,pilot):
            original={key:copy.deepcopy(model[key]) for key in ('build','probe','steps','sources')}
            model['build']=config.configure_build(model['build'],count)
            model['probe']['expected_json']=config.expected_probe(count)
            model.update(host=selected['host'],cpu_profile=selected['profile_id'],fixed_execution=execution,
                wide_thread_pilot=dict(schema='gfn16-fixed-wide-thread-pilot-role-v1',thread_count=count,
                    fixed_profile=selected['profile_id'],placement=selected['fixed_placement'],serial_contract=original,
                    serial_contract_sha256=runtime.duration.digest(original)))
        report=values['pilot_report'];report.update(probe=full['probe']['expected_json'],model_threads=count,
            context_threads=count,compile_workers=2,
            limits=dict(affinity=selected['cpus'],physical_cores=selected['runtime_allocation']['physical_cores'],
                memory_max_bytes=8<<30,swap_max_bytes=0,cpu_max=['800000','100000']),
            exact_build_identity=dict(identity=dict(runtime_allocation=selected['runtime_allocation'])))
        values['forecast'].update(model_threads=count,source_model_build=full['build'])
        return full,values,pins

    def test_wide_long_owns_actual_thread_proof_and_same_hard_bounds(self):
        for count in (4,8):
            full,values,pins=self.wide_fixture(count);policy=runtime.duration_for(count)
            receipt=policy.assess(full,values,pins,'gfn16-azure-sim-f32')
            self.assertEqual(receipt['shape']['model_threads'],count)
            self.assertEqual((receipt['shape']['model_command_seconds'],receipt['shape']['overall_seconds'],receipt['shape']['outer_seconds']),(10450,10700,10800))
            for kind in ('serial-timing','physical','quota','source','shape'):
                m,v=copy.deepcopy((full,values))
                if kind=='serial-timing':v['pilot_report'].update(model_threads=1,probe=dict(context_threads=1,model_threads=1,expected_threads=1))
                elif kind=='physical':v['pilot_report']['limits']['physical_cores']=[[0,0]]*8
                elif kind=='quota':v['pilot_report']['limits']['cpu_max']=['200000','100000']
                elif kind=='source':m['sources'][m['build']['cpp_source']]='0'*64
                else:v['forecast']['model_threads']=1
                with self.subTest(count=count,kind=kind),self.assertRaises((ValueError,KeyError)):policy.assess(m,v,pins,'gfn16-azure-sim-f32')

    def test_wide_actual_execute_adapter_builds_shared_namespace_and_exact_bounds(self):
        def safe_outer(path,pin,out):
            return parent(__import__('json').loads(Path(path).read_text())['cpu_profile'])
        selected=runtime.profile('azure-burst16-thread-wide815-v1')
        policy=types.SimpleNamespace(SHAPE=runtime.duration_for(8).SHAPE,
            validate=lambda *args:dict(model_step=runtime.phase.STEP))
        with tempfile.TemporaryDirectory() as temporary:
            from fpga.tools.native_threaded_wide_package_v3 import execution_contract
            path=Path(temporary)/'manifest.json';path.write_text(json.dumps(dict(cpu_profile=selected['profile_id'],source_root=temporary,
                fixed_execution=execution_contract(selected),build=dict(runtime_threads=8))))
            with patch.object(runtime,'duration_for',return_value=policy),patch.object(runtime.wide,'validate_threaded',return_value=8),\
                 patch.object(runtime.wide,'execute',safe_outer):
                value=runtime.execute(path,hashlib.sha256(path.read_bytes()).hexdigest(),Path(temporary)/'output')
            self.assertIs(value.execute.__globals__,value.__dict__)
            value.LEASE_FDS=tuple(range(15));self.assertEqual(value.execute.__globals__['LEASE_FDS'],tuple(range(15)))
            self.assertTrue(callable(value.MeasuredPopen))
            self.assertIn(10450,value.execute.__code__.co_consts)
            self.assertIn(10700,value.execute.__code__.co_consts)
            self.assertIn(1800,value.execute.__code__.co_consts)
            with patch.object(runtime.wide.time,'time',return_value=runtime.wide.DEADLINE-runtime.wide.DRAIN_LEAD_SECONDS-10814):
                with self.assertRaisesRegex(ValueError,'full wide10815'):value.guard_protected(selected)

    @captured_azure_meter_fixture
    def test_wide_long_real_closed_package_data_stage_and_namespace(self):
        full,values,pins=self.wide_fixture();policy=runtime.duration_for(8)
        from fpga.cloud import host_hours_azure_signed_v1 as meter
        from fpga.tools import global_queue_v1 as queue
        import shutil
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();source=root/'source/fpga';shutil.copytree(ROLE/'source/fpga',source)
            evidence={}
            for name,data in values.items():
                path=source/'long-duration'/(name+'.json');path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(data))
                full['sources'][str(path.relative_to(source))]=hashlib.sha256(path.read_bytes()).hexdigest()
                evidence[name]=dict(path=str(path.relative_to(source)),sha256=full['sources'][str(path.relative_to(source))])
            actual_pins={key:value['sha256'] for key,value in evidence.items()}
            # Refresh only fixture raw bindings after serializing mocked data.
            values['pilot_report']['manifest_sha256']=actual_pins['pilot_manifest']
            report=source/evidence['pilot_report']['path'];report.write_text(json.dumps(values['pilot_report']))
            evidence['pilot_report']['sha256']=queue.sha(report);full['sources'][evidence['pilot_report']['path']]=queue.sha(report)
            values['pilot_gate'].update(manifest_sha256=actual_pins['pilot_manifest'],report_sha256=queue.sha(report))
            gate=source/evidence['pilot_gate']['path'];gate.write_text(json.dumps(values['pilot_gate']))
            evidence['pilot_gate']['sha256']=queue.sha(gate);full['sources'][evidence['pilot_gate']['path']]=queue.sha(gate)
            values['forecast'].update(short_manifest_sha256=actual_pins['pilot_manifest'],short_report_sha256=queue.sha(report),short_gate_sha256=queue.sha(gate))
            forecast=source/evidence['forecast']['path'];forecast.write_text(json.dumps(values['forecast']))
            evidence['forecast']['sha256']=queue.sha(forecast);full['sources'][evidence['forecast']['path']]=queue.sha(forecast)
            full['runtime_duration']=dict(shape=policy.SHAPE,evidence=evidence,contract_sha256=policy.contract(full))
            manifest=root/'manifest.json';manifest.write_text(json.dumps(full))
            profile=runtime.profile(full['cpu_profile']);provider=queue.provider_capture_ref()
            descriptor=meter.make_budget(profile['host'],10815,str(Path(provider['path']).relative_to(ROOT)),provider['sha256'],
                package.source_identity(full),profile['hardware_profile_sha256'],
                transition_path='results/throughput-20260929/azure-sim-resize-r49-v1/rate-transition-v1.json',
                transition_sha256='c4923266e1fabaeeca7cbf6e5f2444455c299accf5ed89c122927c47ed56ac92')
            budget=root/'budget.json';budget.write_text(json.dumps(descriptor))
            result=package.prepare(manifest,source,full['cpu_profile'],'r75-wide-long-source-only','run',root/'packet',budget)
            _,ticket,captured,placed=stage.worker().inspect_archive(root/'packet/package.tar.gz',result['archive_sha256'],result['ticket_sha256'])
            self.assertEqual(ticket['runtime_duration'],policy.SHAPE)
            self.assertEqual(ticket['placement'],profile['fixed_placement'])
            from fpga.tools import native_profile_variants_v14 as matcher
            family=(package.EXECUTOR_SHA,stage.PACKAGE_SHA)
            # Offline future-family qualification does not replace the live
            # consumer's checker while its captured long job is executing.
            with patch.object(matcher,'LONG_FAMILIES',matcher.LONG_FAMILIES|{family}),\
                 patch.dict(matcher.LONG_PHASES,{family:runtime.PHASE_PIN}):
                fingerprint=matcher.functional_fingerprint(captured,ticket['budget'],root/'packet/capture/source/fpga')
            self.assertEqual(len(fingerprint['sha256']),64)
            self.assertEqual(placed['cpus'],list(range(8,16)))
            self.assertEqual(captured['probe']['expected_json']['model_threads'],8)

    def test_actual_run_cli_reads_native_ticket_shape_without_model_execution(self):
        tree=ast.parse(Path(package.__file__).read_text())
        main=tree.body[-1]
        dispatch=next(node for node in main.body if isinstance(node,ast.If) and
                      isinstance(node.test,ast.Compare) and isinstance(node.test.left,ast.Attribute))
        branch=dispatch.orelse[0].orelse
        code=compile(ast.Module(body=branch,type_ignores=[]),package.__file__,'exec')
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'ticket.json'
            for count in (1,4,8):
                path.write_text(json.dumps(dict(budget={'source_sha256':'a'*64},runtime_duration=runtime.duration_for(count).SHAPE)))
                events=[]
                def harmless_worker(budget,selected):
                    events.append((budget,selected))
                    return types.SimpleNamespace(run=lambda ticket,pin:'no native execution')
                scope=dict(args=types.SimpleNamespace(ticket=path,ticket_sha256=hashlib.sha256(path.read_bytes()).hexdigest()),
                           hashlib=hashlib,json=json,worker=harmless_worker)
                exec(code,scope)
                self.assertEqual(events,[({'source_sha256':'a'*64},count)])
                self.assertEqual(scope['result'],'no native execution')

    @captured_azure_meter_fixture
    def test_public_worker_run_uses_real_wide_parent_before_commands(self):
        # The production failure occurred in package run's source preflight,
        # before execute(). Import the actual closed package and call run;
        # Mock local placement/duration and kernel measurement files only.
        # Exercise actual source/build-key/budget/cgroup checks and final
        # execute routing. The claim is a spy; no real lock/child/HDL runs.
        import importlib.util
        import os
        import shutil
        bound=ROOT/'results/throughput-20260929/s4-p16-diet-continuous1000-thread8-native-v1'
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary).resolve()
            package.prepare(bound/'bound/manifest.json',bound/'bound/source/fpga',
                'azure-burst16-thread-wide07-v1','wide-parent-routing-regression','run',folder/'packet',bound/'budget.json',compile_workers=3)
            for suffix in ('07','815'):
                selector='azure-burst16-thread-wide'+suffix+'-v1'
                base=folder/suffix;root=base/'jobs/wide-parent-routing-regression'
                shutil.copytree(folder/'packet',root);source=root/'capture/source/fpga'
                spec=importlib.util.spec_from_file_location('_actual_closed_long_'+suffix,source/'tools/native_long_package_v3.py')
                captured=importlib.util.module_from_spec(spec);spec.loader.exec_module(captured)
                worker=captured.worker(json.loads((root/'ticket.json').read_text())['budget'],8)
                actual_load=worker.load;shared=actual_load('native_long_class_v2.py')
                profile=shared.profile(selector);profile['base']=str(base)
                seen=[];actual_parent=shared.parent
                def checked_parent(name,selected=None):
                    parent=actual_parent(name,selected=selected)
                    self.assertIs(parent.check_sources.__globals__,parent.__dict__)
                    parent.LEASE_FDS=(5,6,7);self.assertEqual(parent.execute.__globals__['LEASE_FDS'],(5,6,7))
                    check=parent.check_sources
                    def source_check(path,pins):check(path,pins);seen.append(name)
                    parent.check_sources=source_check
                    return parent
                worker.load=lambda name:shared if name=='native_long_class_v2.py' else actual_load(name)
                manifest=json.loads((root/'manifest.json').read_text());manifest.update(cpu_profile=selector,source_root=str(source))
                from fpga.tools.native_threaded_wide_package_v3 import execution_contract
                manifest['fixed_execution']=copy.deepcopy(execution_contract(profile))
                manifest['fixed_execution']['runtime_allocation']['compile_workers']=3
                manifest['wide_thread_pilot'].update(fixed_profile=selector,placement=profile['fixed_placement'])
                (root/'manifest.json').write_text(json.dumps(manifest))
                ticket=json.loads((root/'ticket.json').read_text());ticket.update(profile=selector,native_root=str(root),
                    manifest_sha256=hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest())
                identity=worker.load('build_identity_v1.py').build_identity(manifest,shared.selected_for(manifest,profile))
                self.assertEqual(identity['identity']['compile_workers'],3)
                self.assertEqual(identity['identity']['verilator_flags'][4],'3')
                ticket['fixed_execution']=manifest['fixed_execution'];ticket['placement']=profile['fixed_placement']
                ticket['build_key']=identity['build_key']
                ticket['run_key']=hashlib.sha256(worker.load('native_test_queue_v1.py').canonical(dict(
                    build_key=ticket['build_key'],steps=manifest['steps'],probe=manifest['probe'],phase=ticket['phase'],id=ticket['id']))).hexdigest()
                (root/'ticket.json').write_text(json.dumps(ticket));pin=hashlib.sha256((root/'ticket.json').read_bytes()).hexdigest()
                measurements=base/'measurements'
                def measured_path(value):
                    value=str(value)
                    return measurements/value.lstrip('/') if value.startswith(('/sys/','/proc/')) else Path(value)
                def observed(name,value):
                    path=measured_path(name);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(str(value))
                observed('/sys/devices/system/cpu/online','0-15')
                for cpu,topology in profile['topology'].items():
                    prefix='/sys/devices/system/cpu/cpu'+cpu
                    for key,value in zip(('physical_package_id','core_id'),topology):observed(prefix+'/topology/'+key,value)
                    observed(prefix+'/topology/thread_siblings_list',cpu)
                    for key,value in profile['observed_l3'].items():observed(prefix+'/cache/index3/'+key,value)
                observed('/proc/self/cgroup','0::/job')
                observed('/proc/meminfo','MemAvailable: 67108864 kB\n')
                # Online siblings and cache identity are recorded performance
                # details, not equality prerequisites for the owned subset.
                observed('/sys/devices/system/cpu/online','0-7')
                observed('/sys/devices/system/cpu/cpu'+str(profile['cpus'][0])+'/cache/index3/id','changed-cache-metadata')
                for name,value in (('memory.max',str(8<<30)),('memory.swap.max','0'),('cpu.max','800000 100000')):
                    observed('/sys/fs/cgroup/job/'+name,value)
                (base/'claims').mkdir();claims=[]
                def safe_outer(path,pin,out):
                    value=parent(json.loads(Path(path).read_text())['cpu_profile'])
                    assert value.execute.__globals__ is value.__dict__
                    assert 10450 in value.execute.__code__.co_consts
                    assert 10700 in value.execute.__code__.co_consts
                    assert callable(value.MeasuredPopen)
                    assert value.PROFILES[json.loads(Path(path).read_text())['host']]['compile_workers']==3
                    raise RuntimeError('public wide execute reached after real caps')
                policy=types.SimpleNamespace(SHAPE=shared.duration_for(8).SHAPE,
                    validate=lambda *args:dict(model_step=shared.phase.STEP))
                queue=worker.load('native_test_queue_v1.py');prior_load=worker.load
                worker.load=lambda name:queue if name=='native_test_queue_v1.py' else prior_load(name)
                old_cwd=Path.cwd()
                try:
                    os.chdir(source)
                    with patch.object(shared,'profile',return_value=profile),patch.object(shared,'parent',side_effect=checked_parent),\
                         patch.object(worker.duration_policy,'validate',return_value={}),patch.object(shared,'duration_for',return_value=policy),\
                         patch.object(shared.wide,'Path',side_effect=measured_path),patch.object(shared.wide.socket,'gethostname',return_value=profile['host']),\
                         patch.object(shared.wide.os,'geteuid',return_value=profile['uid']),patch.object(shared.wide.os,'sched_getaffinity',return_value=set(profile['cpus']),create=True),\
                         patch.object(shared.wide.pwd,'getpwuid',return_value=types.SimpleNamespace(pw_name=profile['user'])),\
                         patch.object(shared.wide,'execute',safe_outer),patch.object(queue,'claim',side_effect=lambda *args:claims.append(args)):
                        with self.assertRaisesRegex(RuntimeError,'public wide execute reached after real caps'):
                            worker.run(root/'ticket.json',pin)
                        self.assertEqual(seen,[selector])
                        self.assertEqual(len(claims),1)
                        (root/'queue-report.json').unlink()
                        observed('/sys/fs/cgroup/job/cpu.max','900000 100000')
                        with self.assertRaisesRegex(ValueError,'within reservation'):worker.run(root/'ticket.json',pin)
                        self.assertEqual(len(claims),1)
                        observed('/sys/fs/cgroup/job/cpu.max','800000 100000')
                        observed('/sys/fs/cgroup/job/memory.max',str(9<<30))
                        with self.assertRaisesRegex(ValueError,'within reservation'):worker.run(root/'ticket.json',pin)
                        observed('/sys/fs/cgroup/job/memory.max',str(8<<30))
                        observed('/sys/devices/system/cpu/cpu'+str(profile['cpus'][1])+'/topology/core_id',profile['runtime_allocation']['physical_cores'][0][1])
                        with self.assertRaisesRegex(ValueError,'physical ownership'):worker.run(root/'ticket.json',pin)
                        observed('/sys/devices/system/cpu/cpu'+str(profile['cpus'][1])+'/topology/core_id',profile['runtime_allocation']['physical_cores'][1][1])
                        compiled=source/manifest['build']['sv_sources'][0]
                        compiled.write_bytes(compiled.read_bytes()+b'\n// fixture drift\n')
                        with self.assertRaises(ValueError):worker.run(root/'ticket.json',pin)
                        self.assertEqual(seen,[selector]*4)
                finally:os.chdir(old_cwd)
                self.assertFalse((root/'output/native').exists())
                self.assertEqual(list((base/'claims').iterdir()),[])

    def test_real_p16_baseline_and_timing7_source_own_thread_phase_only(self):
        for family,timing in (('s4-p16-diet',0),('s4-p16-timing7',1)):
            for count in (1,8):
                _,values,pins=self.fixture()
                folder=ROOT/'results/throughput-20260929'
                full=json.loads((folder/(family+'-continuous1000-normal-v1/input/manifest.json')).read_text())
                pilot=json.loads((folder/(family+'-continuous100-normal-v1/input/manifest.json')).read_text())
                if count==8:
                    from fpga.tools.native_threaded_wide_package_v3 import execution_contract
                    profile=runtime.profile('azure-burst16-thread-wide07-v1')
                    config=runtime.wide.base().load('native_thread_config_v1.py',runtime.wide.base().RUNTIME_SHA)
                    for model in (full,pilot):
                        contract={key:copy.deepcopy(model[key]) for key in ('build','probe','steps','sources')}
                        model['build']=config.configure_build(model['build'],8)
                        model['probe']['expected_json']=config.expected_probe(8)
                        model.update(host=profile['host'],cpu_profile=profile['profile_id'],fixed_execution=execution_contract(profile),
                            wide_thread_pilot=dict(schema='gfn16-fixed-wide-thread-pilot-role-v1',thread_count=8,
                                fixed_profile=profile['profile_id'],placement=profile['fixed_placement'],
                                serial_contract=contract,serial_contract_sha256=runtime.duration.digest(contract)))
                    values['pilot_report'].update(limits=dict(affinity=profile['cpus'],physical_cores=profile['runtime_allocation']['physical_cores'],
                        memory_max_bytes=8<<30,swap_max_bytes=0,cpu_max=['800000','100000']),
                        exact_build_identity=dict(identity=dict(runtime_allocation=profile['runtime_allocation'])))
                values['pilot_manifest']=pilot
                native=values['pilot_report']['validations'][runtime.phase.STEP]
                native.update(p16_diet=1,p16_timing=timing,candidate_root_sha256=full['continuous']['plan']['candidate_root_sha256'],
                              counts=dict(pilot['continuous']['counts_ordinary_source_projection'],special=0))
                values['pilot_report'].update(probe=full['probe']['expected_json'],model_threads=count)
                values['pilot_gate']['steps'][0]['validation']=native
                values['forecast'].update(model_threads=count,p16_diet=1,p16_timing=timing,
                    source_model_build=full['build'],source_model_pins=dict(full['sources']),pilot_native_validation=native,
                    forecast=runtime.phase.predict(native['counts']['candidate_cycles'],
                        full['continuous']['counts_ordinary_source_projection']['candidate_cycles']+65536,
                        native['phase_wall_ms'],1.5,2.5))
                policy=runtime.duration_for(count)
                self.assertEqual(policy.assess(full,values,pins,'gfn16-azure-sim-f32')['shape']['model_threads'],count)
                for defect in ('borrowed_thread','old_p8_proof','calendar','missing_native_p16','changed_source'):
                    m,v=copy.deepcopy((full,values))
                    if defect=='borrowed_thread':v['pilot_report']['model_threads']=4
                    elif defect=='old_p8_proof':v['forecast']['generator_sha256']=runtime.PREVIOUS_PHASE_PIN
                    elif defect=='calendar':v['pilot_manifest']['continuous']['plan']['geometry']['interval']+=1
                    elif defect=='missing_native_p16':v['pilot_gate']['steps'][0]['validation']['p16_diet']=0
                    else:m['sources'][m['build']['cpp_source']]='0'*64
                    with self.subTest(family=family,count=count,defect=defect),self.assertRaises((ValueError,KeyError)):
                        policy.assess(m,v,pins,'gfn16-azure-sim-f32')


if __name__=='__main__':unittest.main()

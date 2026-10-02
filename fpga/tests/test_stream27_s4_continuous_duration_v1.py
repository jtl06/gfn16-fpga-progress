"""Pure scalar duration terms; no native/fullN oracle or role import."""
import math
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import stream27_s4_continuous_duration_v1 as d


class PhaseForecast(unittest.TestCase):
    def fixture(self, root):
        source_names = {'rtl/model.sv', 'rtl/tb/harness.cpp', 'reference/validator.py', 'continuous/plan.json',
            'rtl/tb/stream27_s4_continuous_config_v1.h', 'rtl/tb/native_runtime_context_v1.h',
            'rtl/tb/stream27_host_chain_full_reference_v1.h', 'rtl/tb/stream27_shared_reference_ntt_v1.h'}
        source = {name: hashlib.sha256(name.encode()).hexdigest() for name in source_names}
        case = '0' * 64
        def counts(count):
            return dict(case_id=case, operations=count, doubles=count//2, resets=1, loads=1, starts=1, readbacks=1,
                canonical_cycles=9*65536, candidate_cycles=102+(count-1)*16653+24847+2+10*65536+4, special=0)
        def model(count):
            return dict(build=dict(sv_sources=['rtl/model.sv'], cpp_source='rtl/tb/harness.cpp',
                                   parameters={'CANONICAL_PIPE_STAGES':1}),
                probe=dict(expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)), sources=source,
                steps=[dict(name=d.STEP,argv=['{exe}',str(count)],validator=dict(source='reference/validator.py',
                    config=dict(operations=count,negative='none',canonical_pipe_stages=1),assets={'plan':'continuous/plan.json'}))],
                continuous=dict(canonical_pipe_stages=1,operations=count,plan={'candidate_root_sha256':'1'*64},
                    counts_ordinary_source_projection=counts(count)))
        m,p=model(1000),model(100)
        validation=dict(status='PASS_expected_contracts', canonical_pipe_stages=1, base=604832956,
            candidate_root_sha256='1'*64, independent_reference_equal=True,operations=100,
            final_actual_sha256='2'*64,final_expected_sha256='2'*64,counts=counts(100),
            phase_wall_ms=dict(candidate_ms=700000,reference_ms=5000,read_ms=20000))
        report=dict(host='gfn16-azure-sim-f32',status='completed_native_commands_unreviewed',seconds=1045,
            probe=dict(context_threads=1,model_threads=1,expected_threads=1),model_threads=1,
            steps=[dict(name=d.STEP,returncode=0,error=None,seconds=745)],validations={d.STEP:validation})
        role=root/'role';pilot=root/'pilot';role.mkdir();pilot.mkdir()
        for name in source_names:
            path=role/'source/fpga'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(name)
        (role/'manifest.json').write_text(json.dumps(m))
        (pilot/'approved-manifest.json').write_text(json.dumps(p))
        report['manifest_sha256']=d.sha(pilot/'approved-manifest.json')
        (pilot/'report.json').write_text(json.dumps(report))
        gate=dict(status='PASS_expected_contracts',promotion_allowed=False,
            manifest_sha256=report['manifest_sha256'],report_sha256=d.sha(pilot/'report.json'),
            steps=[dict(name=d.STEP,actual_returncode=0,validation=validation)])
        gate_path=root/'gate.json';gate_path.write_text(json.dumps(gate))
        return role,pilot,gate_path,m,p,report,gate

    def test_explicit_separate_work_terms_and_shape(self):
        timers = dict(candidate_ms=700000, reference_ms=5000, read_ms=20000)
        result = d.predict(2328962, 17382198, timers, 745, 1045)
        self.assertEqual(result['margin'], 1.75)
        self.assertAlmostEqual(result['candidate_seconds_estimate'], 700 * 17382198 / 2328962 * 1.75)
        self.assertEqual(result['native_reference_seconds_estimate'], 87.5)
        self.assertEqual(result['read_seconds_estimate'], 35)
        self.assertEqual(result['fixed_model_seconds_estimate'], 35)
        self.assertEqual(result['nonmodel_seconds_estimate'], 525)
        self.assertEqual(result['full_reference_replay_seconds_estimate'], 0)
        self.assertTrue(result['fits_finite_shape'])
        self.assertGreater(result['overall_seconds_estimate'], result['continuous_command_seconds_estimate'])

    def test_slow_actual_measurements_remain_blocked(self):
        result = d.predict(2328962, 17382198,
                           dict(candidate_ms=1500000, reference_ms=5000, read_ms=20000), 1545, 1845)
        self.assertFalse(result['fits_finite_shape'])
        self.assertGreater(result['continuous_command_seconds_estimate'], 10450)

    def test_bad_measurements_cannot_silently_weaken_margin_or_fixed_terms(self):
        timers = dict(candidate_ms=700000, reference_ms=5000, read_ms=20000)
        for cycles, full in ((True, 17382198), (0, 17382198), (2328962, True), (2328962, 1)):
            with self.assertRaises(ValueError): d.predict(cycles, full, timers, 745, 1045)
        for model, overall, margin in ((math.inf, 1045, 1.75), (745, math.nan, 1.75),
                                      (700, 1045, 1.75), (745, 740, 1.75), (745, 1045, 1.7)):
            with self.assertRaises(ValueError): d.predict(2328962, 17382198, timers, model, overall, margin)
        for changed in (dict(timers, extra=1), dict(timers, read_ms=True), dict(timers, reference_ms=0)):
            with self.assertRaises(ValueError): d.predict(2328962, 17382198, changed, 745, 1045)

    def test_metadata_binding_and_source_specific_rejections(self):
        # Fake small source bytes and metadata only; no array, oracle or HDL.
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);role,pilot,gate_path,m,p,report,gate=self.fixture(root)
            result=d.prepare(role,pilot,gate_path,root/'out')
            self.assertEqual(result['status'],'PASS_S4_measured_phase_forecast')
            self.assertEqual(result['compatible_hosts'],['gfn16-azure-sim-f32'])
            self.assertFalse(result['local_full_n_integer_computation'])
            self.assertEqual(result['forecast']['continuous_candidate_cycles_max'],17382198)
            mutant=copy.deepcopy(m);mutant['build']['parameters']['CANONICAL_PIPE_STAGES']=0
            (role/'manifest.json').write_text(json.dumps(mutant))
            with self.assertRaises(ValueError):d.prepare(role,pilot,gate_path,root/'wrong-source')
            (role/'manifest.json').write_text(json.dumps(m))
            for i,key in enumerate(('candidate_cycles','loads','case_id')):
                q=copy.deepcopy(gate);q['steps'][0]['validation']['counts'][key]=2
                gate_path.write_text(json.dumps(q))
                with self.assertRaises(ValueError):d.prepare(role,pilot,gate_path,root/f'bad{i}')
            gate_path.write_text(json.dumps(gate))
            (role/'source/fpga/rtl/tb/harness.cpp').write_text('drift')
            with self.assertRaises(ValueError):d.prepare(role,pilot,gate_path,root/'drift')

    def test_exact_model_thread_contract_and_actual_probe(self):
        for count in (1,4,8):
            b=dict(runtime_threads=count,cflags=[f'-DGFN16_RUNTIME_THREADS={count}'])
            probe=dict(context_threads=count,model_threads=count,expected_threads=count)
            self.assertEqual(d.model_threads(b,probe),count)
            for bad in (dict(b,runtime_threads=True),dict(b,runtime_threads=2),
                        dict(b,cflags=b['cflags']+['-UGFN16_RUNTIME_THREADS']),
                        dict(b,cflags=[f'-DGFN16_RUNTIME_THREADS={count} -DGFN16_RUNTIME_THREADS=1'])):
                with self.assertRaises(ValueError):d.model_threads(bad,probe)
            with self.assertRaises(ValueError):d.model_threads(b,dict(probe,model_threads=2))
        self.assertEqual(d.model_threads({},dict(context_threads=1,model_threads=1,expected_threads=1)),1)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);role,pilot,gate_path,m,p,r,g=self.fixture(root)
            r['model_threads']=8;(pilot/'report.json').write_text(json.dumps(r))
            g['report_sha256']=d.sha(pilot/'report.json');gate_path.write_text(json.dumps(g))
            with self.assertRaises(ValueError):d.prepare(role,pilot,gate_path,root/'borrowed-runtime')

    def test_explicit_boundary_case_and_thread8_keep_same_scalar_prediction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);role,pilot,gate_path,m,p,r,g=self.fixture(root)
            for obj in (m,p):
                obj['build'].update(runtime_threads=8,cflags=['-DGFN16_RUNTIME_THREADS=8'])
                obj['probe']['expected_json']=dict(context_threads=8,model_threads=8,expected_threads=8)
                obj['build']['parameters']['BOUNDARY_INPUTREG']=1
                obj['continuous']['boundary_inputreg']=1
                obj['continuous']['plan']['boundary_inputreg']=1
                obj['steps'][0]['validator']['config']['boundary_inputreg']=1
            native=r['validations'][d.STEP];native['boundary_inputreg']=1
            r.update(model_threads=8,probe=m['probe']['expected_json'])
            g['steps'][0]['validation']=native
            (role/'manifest.json').write_text(json.dumps(m));(pilot/'approved-manifest.json').write_text(json.dumps(p))
            r['manifest_sha256']=d.sha(pilot/'approved-manifest.json');(pilot/'report.json').write_text(json.dumps(r))
            g.update(manifest_sha256=r['manifest_sha256'],report_sha256=d.sha(pilot/'report.json'))
            gate_path.write_text(json.dumps(g))
            result=d.prepare(role,pilot,gate_path,root/'out')
            self.assertEqual(result['model_threads'],8);self.assertEqual(result['boundary_inputreg'],1)
            self.assertEqual(result['forecast'],d.predict(2328962,17382198,native['phase_wall_ms'],745,1045))
            m['steps'][0]['validator']['config'].pop('boundary_inputreg');(role/'manifest.json').write_text(json.dumps(m))
            with self.assertRaises(ValueError):d.prepare(role,pilot,gate_path,root/'wrong-target')

    def test_exact_p16_baseline_and_sevenflag_source_selection(self):
        for timing in (0,1):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);role,pilot,gate_path,m,p,r,g=self.fixture(root)
                geo=dict(interval=8460 if timing else 8459,carry_done=12558 if timing else 12557,
                         first_digit=8459 if timing else 8458,cold_first=102)
                flags=dict(BOUNDARY_INPUTREG=1,DESCRIPTOR_FIFO_FF=1,QUARANTINE_REPLICAS=1,
                    FINAL_GS_INPUTREG=1,CANONICAL_LOCALBASE=1,CARRY_LOCALBASE=1,TERM_SELECT_TOKEN=1)
                plan=dict(candidate_root_sha256='0011468ec67d7ca7ebb86fac88103fd19ea0207dc75685289da64d508228ea28' if timing else 'b683cb1113a17652f5d6266c4298c5eb825c6af6b9f92bd28f758dba9b8de898',
                    geometry=geo,profile=dict(aw=16,n=65536,p=16,contexts=1,base=604832956,epoch_seed=65534,
                        canonical_pipe_stages=1,p16_diet=1,corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1))
                if timing:plan['profile'].update(p16_timing=1,timing_flags=flags)
                for obj,count in ((m,1000),(p,100)):
                    obj['build']['parameters'].update(AW=16,P=16,CONTEXTS=1,EPOCH_SEED=65534,CORR_SERIAL_BFS=2,COMM_STAGE_SHARED_MLAB=1,MONT_FACTORED=1)
                    obj['continuous'].update(p16_diet=1,plan=plan)
                    if timing:
                        obj['build']['parameters'].update(flags);obj['continuous']['p16_timing']=1
                    obj['steps'][0]['validator']['config']=d.normal_config(count,d.source_selection(obj))
                    obj['continuous']['counts_ordinary_source_projection']['candidate_cycles']=102+(count-1)*geo['interval']+geo['carry_done']+2+10*65536+4
                native=r['validations'][d.STEP];native.update(p16_diet=1,candidate_root_sha256=plan['candidate_root_sha256'],counts=p['continuous']['counts_ordinary_source_projection'])
                if timing:native['p16_timing']=1
                g['steps'][0]['validation']=native
                (role/'manifest.json').write_text(json.dumps(m));(pilot/'approved-manifest.json').write_text(json.dumps(p))
                r['manifest_sha256']=d.sha(pilot/'approved-manifest.json');(pilot/'report.json').write_text(json.dumps(r))
                g.update(manifest_sha256=r['manifest_sha256'],report_sha256=d.sha(pilot/'report.json'));gate_path.write_text(json.dumps(g))
                result=d.prepare(role,pilot,gate_path,root/'out')
                self.assertEqual(result['p16_diet'],1);self.assertEqual(result.get('p16_timing',0),timing)
                self.assertEqual(result['forecast']['continuous_candidate_cycles_max'],9119566+65536 if timing else 9118566+65536)
                for field in ('interval','carry_done','first_digit'):
                    bad=copy.deepcopy(m);bad['continuous']['plan']['geometry'][field]+=1
                    with self.subTest(field=field),self.assertRaises(ValueError):d.source_selection(bad)
                for field in ('P','CORR_SERIAL_BFS','MONT_FACTORED'):
                    bad=copy.deepcopy(m);bad['build']['parameters'][field]+=1
                    with self.subTest(field=field),self.assertRaises(ValueError):d.source_selection(bad)
                if timing:
                    bad=copy.deepcopy(m);bad['build']['parameters']['TERM_SELECT_TOKEN']=0
                    with self.assertRaises(ValueError):d.source_selection(bad)

    def test_exact_p8_r75_source_and_phase_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);role,pilot,gate_path,m,p,r,g=self.fixture(root)
            flags=dict(BOUNDARY_INPUTREG=1,DESCRIPTOR_FIFO_FF=1,QUARANTINE_REPLICAS=1,
                FINAL_GS_INPUTREG=1,CANONICAL_LOCALBASE=1,CARRY_LOCALBASE=1)
            plan=dict(candidate_root_sha256='c13871f9d9bf13bdd50c2e4c0084d58351a5d30cdeca614537d0445dd62458d7',
                geometry=dict(interval=16654,carry_done=24848,first_digit=16653,cold_first=102),
                profile=dict(aw=16,n=65536,p=8,contexts=1,base=604832956,epoch_seed=65534,
                    canonical_pipe_stages=1,p8_r75=1,timing_flags=flags))
            for obj,count in ((m,1000),(p,100)):
                obj['build']['parameters']=dict(AW=16,P=8,CONTEXTS=1,EPOCH_SEED=65534,CANONICAL_PIPE_STAGES=1,**flags)
                obj['continuous'].update(p8_r75=1,plan=copy.deepcopy(plan))
                obj['steps'][0]['validator']['config']=d.normal_config(count,d.source_selection(obj))
                obj['continuous']['counts_ordinary_source_projection']['candidate_cycles']=680316+(count-1)*16654
            native=r['validations'][d.STEP];native.update(p8_r75=1,candidate_root_sha256=plan['candidate_root_sha256'],counts=p['continuous']['counts_ordinary_source_projection'])
            g['steps'][0]['validation']=native
            (role/'manifest.json').write_text(json.dumps(m));(pilot/'approved-manifest.json').write_text(json.dumps(p))
            r['manifest_sha256']=d.sha(pilot/'approved-manifest.json');(pilot/'report.json').write_text(json.dumps(r))
            g.update(manifest_sha256=r['manifest_sha256'],report_sha256=d.sha(pilot/'report.json'));gate_path.write_text(json.dumps(g))
            result=d.prepare(role,pilot,gate_path,root/'out')
            self.assertEqual(result['p8_r75'],1)
            self.assertEqual(result['forecast']['measured_candidate_cycles'],2329062)
            self.assertEqual(result['forecast']['continuous_candidate_cycles_max'],17317662+65536)
            mutants=[]
            for field in ('interval','carry_done','first_digit'):
                bad=copy.deepcopy(m);bad['continuous']['plan']['geometry'][field]-=1;mutants.append(bad)
            for field in flags:
                bad=copy.deepcopy(m);bad['build']['parameters'][field]=0;mutants.append(bad)
            bad=copy.deepcopy(m);bad['continuous']['plan']['candidate_root_sha256']='140e2b306e39a5fba02046917d0733eb31ed1e2f9c80f81be7fd086181b8c051';mutants.append(bad)
            bad=copy.deepcopy(m);bad['continuous']['p8_r75']=True;mutants.append(bad)
            bad=copy.deepcopy(m);bad['continuous']['p16_diet']=1;mutants.append(bad)
            bad=copy.deepcopy(m);bad['continuous']['boundary_inputreg']=1;mutants.append(bad)
            bad=copy.deepcopy(m);bad['build']['parameters']['TERM_SELECT_TOKEN']=1;mutants.append(bad)
            for bad in mutants:
                with self.assertRaises(ValueError):d.source_selection(bad)
            m['steps'][0]['validator']['config'].pop('p8_r75');(role/'manifest.json').write_text(json.dumps(m))
            with self.assertRaises(ValueError):d.prepare(role,pilot,gate_path,root/'missing-source-config')


if __name__ == '__main__': unittest.main()

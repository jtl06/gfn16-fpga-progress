"""Dashboard presentation guards; fixtures are not physical performance evidence."""
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fpga.progress import dashboard as d


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patch = patch.object(d, 'RESULTS', self.root)
        self.patch.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.patch.stop)

    def save(self, name, value):
        (self.root / name).write_text(json.dumps(value))

    def test_missing_report_never_passes(self):
        r = d.experiment(dict(id='x', gate='missing.json'), {}, self.root)
        self.assertEqual(r['stages'][1], 'not archived')
        self.assertNotEqual(r['state'], 'validated')
        self.assertTrue(r['evidence'][0]['missing'])

    def test_prefill_small_gate_is_not_fullsize_throughput(self):
        self.save('small.json',dict(status='passed_aw5_group_only',aw=5,group='normal',metrics=[{}]*568))
        row=d.experiment(dict(id='core27_prefill',gate='small.json'),{},self.root)
        self.assertEqual(row['state'],'partial')
        self.assertNotIn('warm_cycles',row)
        self.assertEqual(row['measurements'],{})

    def test_prefill_fullsize_normal_stays_partial_but_has_simulation_cycles(self):
        metrics=[dict(readback=1)]*9+[dict(readback=0)]*2
        metrics.append(dict(case='full-random-s1-d1',n=65536,base=604832956,
                            prefill_before=1,readback=1,cycles=28823))
        self.save('full.json',dict(status='passed_aw16_normal_only',aw=16,group='normal',metrics=metrics))
        row=d.experiment(dict(id='core27_prefill',gate='full.json'),{},self.root)
        self.assertEqual(row['state'],'partial')
        self.assertEqual(row['warm_cycles'],28823)
        self.assertEqual(d.simulation_candidate([row]),row)
        self.assertEqual(row['measurements'],{})
        self.assertNotIn('clock_mhz',row)

    def test_crt_positive_is_not_complete_g2(self):
        self.save('crt.json', {'status':'verified_positive_only_mutations_pending','complete_g2':False})
        row=d.experiment(dict(id='crt27_mont',gate='crt.json'),{},self.root)
        self.assertEqual(row['state'],'partial')
        self.assertIn('negatives pending',row['stages'][1])
        self.assertEqual(row['stages'][2:],['not run','not run'])
        self.assertNotEqual(row['gate_status'],'passed')

    def test_selected_clock_requires_all_corners_and_original_preservation(self):
        corners=['Slow 900mV 100C Model','Slow 900mV 0C Model','Fast 900mV 100C Model','Fast 900mV 0C Model']
        receipt=dict(status='passed_scoped_internal_sta',original_unchanged=True,
            helpers_rechecked=True,final_verification_errors=[],audit_clock={'period_ns':11.764},
            timing={'audit85':{c:{k:dict(status='measured',slack_ns=.015,tns_ns=0,failing_endpoints=0)
                for k in ('setup','hold','mpw')} for c in corners}})
        spec=dict(id='rootfused85_audit',gate='sta.json')
        self.save('sta.json',receipt)
        row=d.experiment(spec,{},self.root)
        self.assertEqual(row['audited_internal_clock_mhz'],85)
        self.assertEqual(row['stages'][-1],'not signed off')
        self.assertNotIn('fmax_mhz',row['measurements'])
        receipt['original_unchanged']=False;self.save('sta.json',receipt)
        self.assertNotIn('audited_internal_clock_mhz',d.experiment(spec,{},self.root))
        receipt['original_unchanged']=True
        receipt['timing']['audit85'][corners[0]]['hold']['slack_ns']=-.001
        self.save('sta.json',receipt)
        self.assertNotIn('audited_internal_clock_mhz',d.experiment(spec,{},self.root))
        del receipt['timing']['audit85'][corners[0]]
        self.save('sta.json',receipt)
        self.assertEqual(d.experiment(spec,{},self.root)['state'],'blocked')

    def test_streaming_arithmetic_is_not_rtl_or_cycle_qualification(self):
        self.save('model.json', {'status':'passed_arithmetic_only'})
        row=d.experiment(dict(id='stream_ntt_s1',gate='model.json'),{},self.root)
        self.assertEqual(row['state'],'partial')
        self.assertEqual(row['stage_labels'][0],'Arithmetic model')
        self.assertEqual(row['stages'][2:],['pending','not run'])
        self.assertNotIn('warm_cycles',row)
        self.assertEqual(row['measurements'],{})

    def test_host_memory_scope_is_not_generic_core_qualification(self):
        self.save('host.json',{'status':'passed_host_memory_pair','profile':{'aw':8},'sources':{}})
        row=d.experiment(dict(id='host_broadcast_memory',gate='host.json'),{},self.root)
        self.assertEqual(row['state'],'validated')
        self.assertEqual(row['stages'][1],'host-memory AW8 passed')
        self.assertIn('not full-core',row['gate_scope'])
        self.assertEqual(row['stages'][2:],['not run','not run'])
        self.assertNotIn('warm_cycles',row)
        self.assertNotEqual(d.experiment(dict(id='unrelated',gate='host.json'),{},self.root)['state'],'validated')

    def test_joined_stream_model_never_becomes_hardware_measurement(self):
        gate=dict(status='PASS',n=65536,p=8,cases=[dict(status='PASS') for _ in range(4)],
                  queued_events=dict(epochs_checked=2,interval=16660))
        self.save('joined.json',gate)
        spec=dict(id='stream_ntt_s1',gate='joined.json')
        row=d.experiment(spec,{},self.root)
        self.assertEqual(row['state'],'partial')
        self.assertEqual(row['model_interval_clocks'],16660)
        self.assertNotIn('warm_cycles',row)
        self.assertEqual(row['measurements'],{})
        self.assertEqual(row['stages'][-1],'not run')
        gate['cases'].pop();self.save('joined.json',gate)
        self.assertEqual(d.experiment(spec,{},self.root)['state'],'blocked')

    def test_fit_complete_is_not_clock_closure(self):
        self.save('gate.json', {'status':'passed', 'sources':{'rtl/kernel/a.sv':'abc'}})
        self.save('fit.json', {'test':{'manifest':{'clock_period_ns':5, 'source_sha256':{'a.sv':'abc'}}, 'fit_success':True, 'internal_timing_met':False, 'fmax_mhz':125, 'dsp_blocks_placed':3, 'dsp_blocks_needed':2}})
        r = d.experiment(dict(id='x', gate='gate.json', fit='fit.json'), {}, self.root)
        self.assertEqual(r['stages'][2:], ['passed','failed'])
        self.assertEqual(r['state'], 'tradeoff')
        self.assertTrue(r['source_match'])
        self.assertEqual(r['measurements']['dsp_blocks_placed'], 3)
        self.assertEqual(r['measurements']['dsp_blocks_needed'], 2)

    def test_periodmask_component_scope_is_not_whole_core(self):
        self.save('pair.json', {'status':'passed_component_pair','profile':{'lanes':64,'field':1}})
        row=d.experiment(dict(id='periodmask64',gate='pair.json'),{},self.root)
        self.assertEqual(row['state'],'validated')
        self.assertEqual(row['stages'][1],'L64/P1 component passed')
        self.assertEqual(row['stages'][2:],['not run','not run'])
        self.assertIn('no mutation',row['gate_scope'])
        self.assertNotIn('warm_cycles',row)
        self.save('pair.json', {'status':'passed_component_pair','profile':{'lanes':16,'field':2}})
        row=d.experiment(dict(id='periodmask64',gate='pair.json'),{},self.root)
        self.assertEqual(row['state'],'blocked')

    def test_rowcompact_gate_retains_normal_profile_scope(self):
        for identity in ('rowcompact64','rowcompact_wrapper'):
            self.save('row.json',{'status':'passed','aw':16})
            row=d.experiment(dict(id=identity,gate='row.json'),{},self.root)
            self.assertEqual(row['stages'][1],'full-N normal passed')
            self.assertIn('not complete mutation qualification',row['gate_scope'])
            self.assertEqual(row['stages'][2:],['not run','not run'])

    def test_source_mismatch_blocks_comparison(self):
        self.save('gate.json', {'status':'passed', 'sources':{'rtl/kernel/a.sv':'wrong'}})
        self.save('fit.json', {'test':{'manifest':{'clock_period_ns':5, 'source_sha256':{'a.sv':'abc'}}, 'fit_success':True, 'internal_timing_met':True}})
        r = d.experiment(dict(id='x', gate='gate.json', fit='fit.json'), {}, self.root)
        self.assertFalse(r['source_match'])
        self.assertEqual(r['state'], 'blocked')

    def test_host_broadcast_whole_gate_keeps_profile_scope(self):
        for aw,label in ((5,'N32 normal passed'),(16,'full-N normal passed')):
            self.save('host-core.json',{'status':'passed','aw':aw})
            row=d.experiment(dict(id='atomic27_host_broadcast',gate='host-core.json'),{},self.root)
            self.assertEqual(row['stages'][1],label)
            self.assertEqual(row['state'],'validated')
            self.assertIn('not complete mutation qualification',row['gate_scope'])
            self.assertNotIn('fmax_mhz',row['measurements'])

    def test_running_requires_observed_process(self):
        spec = dict(id='x', host='gcp', match='candidate-x')
        self.assertNotEqual(d.experiment(spec, {'gcp':{'status':'checked','jobs':[]}}, self.root)['state'], 'running')
        host = {'gcp':{'checked_at':'2026-09-30T00:00:00Z','jobs':[{'pid':1,'name':'quartus_fit','cpu_percent':100,'rss_mib':500,'cwd':'/candidate-x','args':'probe'}]}}
        row = d.experiment(spec, host, self.root)
        self.assertEqual(row['state'], 'running')
        self.assertEqual(row['observed_at'], '2026-09-30T00:00:00Z')
        self.assertNotIn('args', row['processes'][0])

    def test_policy_abort_is_not_route_failure(self):
        self.save('abort.json', {'status':'aborted_by_policy','project':'exact','main_pid_after':0})
        spec=dict(id='x',host='aws',match='exact',cancellation='abort.json')
        row=d.experiment(spec,{},self.root)
        self.assertEqual(row['state'],'aborted')
        self.assertIsNone(row['fit_success'])
        self.assertNotIn('fit_failure_reason',row)
        self.assertEqual(row['stages'][3],'not established')
        # A live process observation wins over historical terminal evidence.
        hosts={'aws':{'jobs':[dict(pid=1,name='quartus_fit',cpu_percent=100,rss_mib=20,args='exact',cwd='')]}}
        self.assertEqual(d.experiment(spec,hosts,self.root)['state'],'running')
        spec['match']='different'
        self.assertNotEqual(d.experiment(spec,{},self.root)['state'],'aborted')

    def test_link_and_hash_come_from_file_bytes(self):
        self.save('gate.json', {'status':'passed'})
        value, e = d.read_evidence('gate.json', self.root / 'dashboard')
        self.assertEqual(e['href'], '../gate.json')
        self.assertEqual(len(e['sha256']), 64)
        self.assertEqual(value['status'], 'passed')

    def test_checklist_sources_and_local_evidence(self):
        self.save('evidence.json', {'status':'passed'})
        item={'id':'one','considered':True,'status':'tested','sources':[{'url':'https://example.com/paper'}], 'local_evidence':[{'path':'evidence.json'}]}
        self.save('optimization_research.json', {'schema_version':1,'items':[item]})
        with patch.object(d,'__file__',str(self.root/'dashboard.py')), patch.object(d,'LAB',self.root):
            result=d.checklist(self.root/'dashboard')
            self.assertTrue(result['items'][0]['local_evidence'][0]['available'])
            self.assertEqual(len(result['items'][0]['local_evidence'][0]['sha256']),64)
            item['sources'][0]['url']='javascript:alert(1)'
            self.save('optimization_research.json', {'schema_version':1,'items':[item]})
            with self.assertRaises(ValueError):d.checklist(self.root)

    def test_checklist_rejects_contradictory_status_and_external_path(self):
        item={'id':'one','considered':False,'status':'adopted','sources':[{'url':'https://example.com/paper'}], 'local_evidence':[]}
        self.save('optimization_research.json', {'schema_version':1,'items':[item]})
        with patch.object(d,'__file__',str(self.root/'dashboard.py')), patch.object(d,'LAB',self.root):
            with self.assertRaises(ValueError):d.checklist(self.root)
            item['considered']=True;item['local_evidence']=[{'path':'../../outside.txt'}]
            self.save('optimization_research.json', {'schema_version':1,'items':[item]})
            with self.assertRaises(ValueError):d.checklist(self.root)

    def test_hold_failure_is_blocked_even_if_summary_claims_timing_pass(self):
        self.save('gate.json',{'status':'passed','sources':{'rtl/kernel/a.sv':'abc'}})
        self.save('fit.json',{'x':{'manifest':{'clock_period_ns':10,'source_sha256':{'a.sv':'abc'}},
            'fit_success':True,'internal_timing_met':True,'hold_slack_ns':-.096,'fmax_mhz':87.89}})
        row=d.experiment(dict(id='x',gate='gate.json',fit='fit.json'),{},self.root)
        self.assertTrue(row['hold_failed']);self.assertEqual(row['state'],'blocked')

    def test_failed_routing_has_no_fitted_clock(self):
        self.save('gate.json',{'status':'passed','sources':{'rtl/kernel/a.sv':'abc'}})
        self.save('fit.json',{'x':{'manifest':{'clock_period_ns':10,'source_sha256':{'a.sv':'abc'}},
            'fit_success':False,'internal_timing_met':False,'alms_placed':408681}})
        (self.root/'fit.log').write_text('Fitter routing phase terminated due to routing congestion\nError (170143)')
        row=d.experiment(dict(id='atomic27',gate='gate.json',fit='fit.json',fit_log='fit.log'),{},self.root)
        self.assertEqual(row['state'],'blocked')
        self.assertEqual(row['fit_failure_reason'],'routing congestion')
        self.assertNotIn('fmax_mhz',row['measurements'])

    def test_warm_cycles_require_passed_exact_representative_readback(self):
        metric=dict(n=65536,base=604832956,case='full-random-s1-d1',root_cache_warm=True,readback=True,cycles=32153)
        self.save('gate.json',{'status':'running','metrics':[metric]})
        self.assertNotIn('warm_cycles',d.experiment(dict(id='x',gate='gate.json'),{},self.root))
        self.save('gate.json',{'status':'passed','metrics':[metric]})
        self.assertEqual(d.experiment(dict(id='x',gate='gate.json'),{},self.root)['warm_cycles'],32153)
        self.save('gate.json',{'status':'passed','metrics':[metric,metric]})
        self.assertNotIn('warm_cycles',d.experiment(dict(id='x',gate='gate.json'),{},self.root))
        profile={**metric,'cycles':32968,'profile_cache_warm':True}
        del profile['root_cache_warm']
        self.save('gate.json',{'status':'passed','metrics':[profile]})
        self.assertEqual(d.experiment(dict(id='x',gate='gate.json'),{},self.root)['warm_cycles'],32968)

    def test_native_r2_warm_cycle_requires_explicit_integer_cache_counters(self):
        metric=dict(n=65536,base=604832956,case='full-random-s1-d1',readback=1,
                    profile_before=1,profile_loads=0,profile_hits=1,cycles=32965)
        for identity in ('atomic27_prefetch_r2','atomic27_host_broadcast','prefetch_orient8'):
            self.save('gate.json',{'status':'passed','metrics':[metric]})
            self.assertEqual(d.experiment(dict(id=identity,gate='gate.json'),{},self.root)['warm_cycles'],32965)
            for key,value in (('readback',0),('profile_before',0),('profile_loads',1),('profile_hits',0),('readback','1')):
                self.save('gate.json',{'status':'passed','metrics':[{**metric,key:value}]})
                self.assertNotIn('warm_cycles',d.experiment(dict(id=identity,gate='gate.json'),{},self.root))
        self.save('gate.json',{'status':'passed','metrics':[metric]})
        self.assertNotIn('warm_cycles',d.experiment(dict(id='unknown',gate='gate.json'),{},self.root))

    def test_longchain_never_completes_from_process_absence(self):
        spec=dict(id='longchain',gate='missing.json',host='aethia',match='longchain')
        row=d.experiment(spec,{'aethia':{'status':'checked','jobs':[]}},self.root)
        self.assertEqual(row['state'],'in_progress')
        self.assertNotEqual(row['stages'][1],'passed')
        self.save('missing.json',{'status':'failed'})
        self.assertEqual(d.experiment(spec,{},self.root)['state'],'blocked')

    def test_formal_component_scope_is_not_whole_core_pass(self):
        self.save('proof.json',{'status':'passed','proof_kind':'finite combinational equivalence'})
        row=d.experiment(dict(id='formal_tree',gate='proof.json'),{},self.root)
        self.assertEqual(row['stages'][2:],["not proved","not tested"])

    def test_ambiguous_source_basename_does_not_match(self):
        self.save('gate.json',{'status':'passed','sources':{'rtl/kernel/a.sv':'abc','/other/rtl/kernel/a.sv':'abc'}})
        self.save('fit.json',{'x':{'manifest':{'clock_period_ns':10,'source_sha256':{'a.sv':'abc'}},'fit_success':True}})
        self.assertFalse(d.experiment(dict(id='x',gate='gate.json',fit='fit.json'),{},self.root)['source_match'])

    def test_planning_headline_refuses_failed_hold_and_borrowed_clock(self):
        folder=self.root/'core27-ntt16-fit';folder.mkdir()
        projection=dict(status='integrated_simulation_and_fit_not_hardware',clock_mhz=80,
                        cached_chain_projection=dict(approx_prp_seconds=2262,warm_cycles_sample_max=94686))
        (folder/'performance80.json').write_text(json.dumps(projection))
        row=dict(id='atomic27_16',name='test',fit_success=True,source_match=True,
                 measurements=dict(hold_slack_ns=.02,fmax_mhz=83.32))
        self.assertIsNotNone(d.planning_headline([row],self.root))
        row['measurements']['hold_slack_ns']=-.01
        self.assertIsNone(d.planning_headline([row],self.root))
        row['measurements'].update(hold_slack_ns=.02,fmax_mhz=70)
        self.assertIsNone(d.planning_headline([row],self.root))
        row['measurements']['fmax_mhz']=83.32;row['source_match']=False
        self.assertIsNone(d.planning_headline([row],self.root))

    def test_stream16_planning_requires_matched_gate_and_fmax_bound(self):
        folder=self.root/'core27-stream-ntt16-fit';folder.mkdir()
        projection=dict(status='integrated_simulation_and_fit_not_hardware',clock_mhz=85,
                        base=604832956,n=65536,cached_chain_projection=dict(
                            approx_prp_seconds=2035.9950264235295,warm_cycles_sample_max=90521))
        comparison=dict(status='matched_integrated_planning_comparison_not_hardware',
                        candidate=projection,regression_sha256={'candidate':'a'*64})
        path=folder/'matched-comparison-80-85.json';path.write_text(json.dumps(comparison))
        row=dict(id='atomic27_stream16',name='Precision-stream whole core · 16 lanes',fit_success=True,
                 source_match=True,gate='gate.json',evidence=[{'label':'gate.json','sha256':'a'*64}],
                 warm_cycles=90521,stages=['implemented','passed','passed','failed'],
                 measurements=dict(hold_slack_ns=.017,fmax_mhz=87.67,target_mhz=100))
        headline=d.planning_headline([row],self.root)
        self.assertAlmostEqual(headline['minutes'],33.93325044,places=5)
        self.assertFalse(headline['target_met'])
        row['evidence'][0]['sha256']='b'*64
        self.assertIsNone(d.planning_headline([row],self.root))
        row['evidence'][0]['sha256']='a'*64
        projection['clock_mhz']=90;path.write_text(json.dumps(comparison))
        self.assertIsNone(d.planning_headline([row],self.root))

    def test_host_view_redacts_commands_and_uses_current_allowances(self):
        cloud=self.root/'cloud';cloud.mkdir()
        (cloud/'aws-plan.json').write_text(json.dumps(dict(instance_type='m8i.8xlarge',vcpus=32,physical_cores=16,memory_gib=128,approved_total_aws_budget_usd=80)))
        (cloud/'pilot-plan.json').write_text(json.dumps(dict(approved_pilot_budget_usd=60,requested_upgrade={'machine_type':'c4-highmem-8'})))
        with patch.object(d,'LAB',self.root):
            hosts=d.host_inventory({'aws':{'jobs':[{'pid':1,'name':'quartus_fit','args':'PRIVATE COMMAND','cwd':'PRIVATE PATH'}]}})
        self.assertNotIn('PRIVATE',json.dumps(hosts));self.assertEqual(hosts['aws']['logical_cpus'],32)
        self.assertEqual(hosts['aws']['allowance_usd'],80);self.assertEqual(hosts['gcp']['allowance_usd'],60)
        self.assertEqual(hosts['gcp']['planned'],'c4-highmem-8')

    def test_latest_simulation_candidate_excludes_cancelled_and_fitted(self):
        old=dict(id='atomic27_prefetch_r2',gate_status='passed',warm_cycles=32965)
        new=dict(id='rootfused_crtmont_g4',gate_status='passed',warm_cycles=32920)
        self.assertEqual(d.simulation_candidate([old,new]),new)
        new['fit_success']=True
        self.assertIsNone(d.simulation_candidate([old,new]))
        new['fit_success']=False;new['gate_status']='failed'
        self.assertIsNone(d.simulation_candidate([new]))

    def test_m8azn_trial_does_not_reuse_stale_resize_capacity(self):
        cloud=self.root/'cloud';cloud.mkdir()
        (cloud/'aws-plan.json').write_text(json.dumps(dict(instance_type='m8azn.3xlarge',
            vcpus=12,physical_cores=12,memory_gib=48,fit_slots=2,approved_total_aws_budget_usd=120)))
        observed={'aws':dict(status='checked',checked_at='2026-10-01T01:59:55Z',jobs=[],
            resources=dict(logical_cpus=16,physical_cores=8,memory_bytes=64*2**30))}
        with patch.object(d,'LAB',self.root):
            host=d.host_inventory(observed)['aws']
        self.assertEqual((host['logical_cpus'],host['physical_cores'],host['memory_gib']),(12,12,48))
        self.assertEqual(host['resources'],{})
        self.assertEqual(host['status'],'capacity_changed_since_observation')
        self.assertIn('Two 6-core / 20 GiB capped fit trials proposed',host['role'])
        self.assertIn('neither concurrent operation nor sufficiency qualified',host['role'])
        self.assertNotIn('topology-checked fit slots',host['role'])
        self.assertEqual(host['process_count'],0)

    def test_p2_synthesis_requires_pinned_inventory_and_never_becomes_fit(self):
        base=self.root/d.P2_SYNTHESIS_PATH
        (base/'output_files').mkdir(parents=True);(base/'rtl').mkdir()
        source=b'module fixture; endmodule\n';(base/'rtl/fixture.sv').write_bytes(source)
        manifest=dict(source_sha256={'fixture.sv':hashlib.sha256(source).hexdigest()})
        (base/'manifest.json').write_text(json.dumps(manifest))
        summary=base/'output_files/probe.syn.summary'
        summary.write_text('Synthesis Status : Successful\nLogic utilization estimate (in ALMs) : 47,349\nTotal registers : 79808\nEstimated DSP Blocks Post-Merging : 152\n')
        files={p.relative_to(base).as_posix():dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest())
               for p in base.rglob('*') if p.is_file()}
        inventory=base/'collection-inventory-v1.json'
        inventory.write_text(json.dumps(dict(status='completed_synthesis_snapshot_fit_still_running',files=files,observed_at='2026-10-01T02:59:10Z')))
        spec=dict(id='stream_p2');row=dict(state='queued',evidence=[],measurements={})
        with patch.object(d,'P2_INVENTORY_SHA',hashlib.sha256(inventory.read_bytes()).hexdigest()),\
             patch.object(d,'P2_PROJECT_SHA',files['manifest.json']['sha256']):
            d.apply_p2_synthesis(row,self.root)
            self.assertEqual(row['synthesis_estimates']['alms'],47349)
            self.assertEqual(row['measurements'],{})
            self.assertNotIn('fit_success',row);self.assertNotIn('clock_mhz',row)
            self.assertEqual(row['stages'][-1],'not established')
            summary.write_text(summary.read_text()+'tamper\n')
            bad=dict(state='queued',evidence=[],measurements={});d.apply_p2_synthesis(bad,self.root)
            self.assertNotIn('synthesis_estimates',bad)
        bad=dict(state='queued',evidence=[],measurements={});d.apply_p2_synthesis(bad,self.root)
        self.assertNotIn('synthesis_estimates',bad)

    def test_prp_small_native_result_requires_exact_replay_and_report(self):
        folder=self.root/'core27-crtmont-prp-aw5-native-v1';folder.mkdir()
        report=folder/'report.json';report.write_text(json.dumps(dict(status='completed_native_commands_unreviewed')))
        replay=dict(status='passed_small_aw5_prp_residues_and_comparator',operations=4650,final_readbacks=8,
                    report_sha256=hashlib.sha256(report.read_bytes()).hexdigest())
        self.save('prp.json',replay);pin=hashlib.sha256((self.root/'prp.json').read_bytes()).hexdigest()
        with patch.object(d,'PRP_AW5_REPLAY_SHA',pin):
            row=d.experiment(dict(id='prp_aw5',gate='prp.json'),{},self.root)
            self.assertEqual(row['prp_operations'],4650);self.assertEqual(row['prp_final_residues'],8)
            self.assertEqual(row['state'],'partial');self.assertEqual(row['measurements'],{})
            self.assertNotIn('warm_cycles',row)
            report.write_text('{}')
            self.assertNotIn('prp_operations',d.experiment(dict(id='prp_aw5',gate='prp.json'),{},self.root))

    def test_t5b_normal_review_is_hash_bound_and_has_no_clock(self):
        report='core27-t5b-aw16-normal-aethia-v1/report.json'
        (self.root/report).parent.mkdir()
        self.save(report,dict(status='completed_native_commands_unreviewed'))
        pin=__import__('hashlib').sha256((self.root/report).read_bytes()).hexdigest()
        review=dict(status='PASS_scoped_T5b_AW16_native_normal_and_exact_cycle_delta',
            pins=dict(report_sha256=pin),native_result=dict(n=65536,squares=12,readbacks=10,warm_total_cycles=28826))
        self.save('review.json',review)
        row=d.experiment(dict(id='core27_t5b',gate='review.json'),{},self.root)
        self.assertEqual(row['warm_cycles'],28826)
        self.assertEqual(row['measurements'],{})
        self.assertEqual(row['stages'][2:],['not run','not run'])
        self.assertEqual(d.simulation_candidate([row]),row)
        parent=dict(id='core27_prefill',normal_simulation_passed=True,warm_cycles=28823,fit_success=False)
        self.assertEqual(d.simulation_candidate([parent,row]),row)
        review['pins']['report_sha256']='bad';self.save('review.json',review)
        row=d.experiment(dict(id='core27_t5b',gate='review.json'),{},self.root)
        self.assertEqual(row['state'],'blocked')
        self.assertNotIn('warm_cycles',row)

    def test_routed_seconds_require_projection_replay_and_exact_lineage(self):
        receipt=dict(projected_compute_minutes=12.3574,projected_compute_seconds=741.444,
                     clock_mhz=85,warm_cycles_sample_max=32965,n=65536,base=604832956)
        self.save('rootfused85-compute-projection-v1.json',receipt)
        rows=[dict(id='rootfused64',fit_success=True,source_match=True,warm_cycles=32965),
              dict(id='rootfused85_audit',audited_internal_clock_mhz=85)]
        with patch('fpga.synthesis.rootfused85_projection.estimate',return_value=receipt):
            self.assertEqual(d.routed_projection(rows,self.root)['minutes'],12.3574)
            rows[0]['warm_cycles']=32920
            self.assertIsNone(d.routed_projection(rows,self.root))
            rows[0]['warm_cycles']=32965;rows[1]['audited_internal_clock_mhz']=86.7
            self.assertIsNone(d.routed_projection(rows,self.root))
        rows[1]['audited_internal_clock_mhz']=85
        with patch('fpga.synthesis.rootfused85_projection.estimate',side_effect=ValueError('drift')):
            self.assertIsNone(d.routed_projection(rows,self.root))

    def test_operations_template_keeps_history_collapsed_and_hold_visible(self):
        template=Path(d.__file__).with_name('dashboard_operations.html').read_text()
        self.assertIn('<details class="archive" id="history">',template)
        self.assertNotIn('<details class="archive" id="history" open',template)
        self.assertIn('Simulation cycles · N = 65,536',template)
        self.assertIn("byId('core27_prefill')?.gate_scope",template)
        self.assertIn('<td>Board measured</td>',template)
        self.assertIn('<tbody id="active-jobs"></tbody>',template)
        self.assertNotIn('class="card',template)
        self.assertIn('<th>Hold ns</th>',template)
        self.assertNotIn('fetch(',template)

    def test_tracks_are_primary_and_fallback_is_collapsed(self):
        template=Path(d.__file__).with_name('dashboard_operations.html').read_text()
        self.assertIn('GFN16 · Track A / Track S',template)
        self.assertIn('Track A · routed whole64',template)
        self.assertIn('Track S · streaming P8',template)
        self.assertIn('<details class="archive" id="legacy">',template)
        self.assertNotIn('id="legacy" open',template)
        self.assertIn("$('fallback-overview').innerHTML=",template)
        self.assertNotIn("$('overview').innerHTML=`<tr><td>Routed 16-lane",template)

    def test_native_clock_needs_all_corners_and_explicit_scope(self):
        corners=('Slow 900mV 100C Model','Slow 900mV 0C Model',
                 'Fast 900mV 100C Model','Fast 900mV 0C Model')
        timing={c:{k:dict(status='measured',slack_ns=.01,tns_ns=0,failing_endpoints=0)
                   for k in ('setup','hold','mpw')} for c in corners}
        r=dict(status='passed_scoped_selected_clock_sta',original_unchanged=True,
               final_verification_errors=[],mode='selected_clock',period_ns='10',
               timing={'selected_clock':timing})
        self.assertEqual(d.scoped_native_clock(r),100)
        timing[corners[0]]['hold']['slack_ns']=-.01
        self.assertIsNone(d.scoped_native_clock(r))
        timing[corners[0]]['hold']['slack_ns']=.01
        r['original_unchanged']=False
        self.assertIsNone(d.scoped_native_clock(r))
        r['original_unchanged']=True
        del timing[corners[1]]
        self.assertIsNone(d.scoped_native_clock(r))

    def test_track_a_projection_requires_exact_replay(self):
        receipt=dict(projected_compute_minutes=10.489487604,projected_compute_seconds=629.36925623,
                     clock_mhz=100,warm_cycles_sample_max=32920,n=65536,base=604832956)
        self.save('crtmont100-compute-projection-v1.json',receipt)
        with patch('fpga.synthesis.crtmont100_projection.estimate',return_value=receipt):
            result=d.track_a_projection(self.root)
            self.assertEqual(result['clock_mhz'],100)
            self.assertEqual(result['warm_cycles'],32920)
            changed=dict(receipt,warm_cycles_sample_max=28823)
            self.save('crtmont100-compute-projection-v1.json',changed)
            self.assertIsNone(d.track_a_projection(self.root))
        self.save('crtmont100-compute-projection-v1.json',receipt)
        with patch('fpga.synthesis.crtmont100_projection.estimate',side_effect=ValueError('source drift')):
            self.assertIsNone(d.track_a_projection(self.root))

    def test_selected96_dashboard_clock_requires_independent_matching_replay(self):
        corners=('Slow 900mV 100C Model','Slow 900mV 0C Model',
                 'Fast 900mV 100C Model','Fast 900mV 0C Model')
        timing={c:{k:dict(status='measured',slack_ns=.095,tns_ns=0,failing_endpoints=0)
                   for k in ('setup','hold','mpw')} for c in corners}
        native=dict(status='passed_scoped_selected_clock_sta_awaiting_independent_replay',
            mode='selected_clock',period_ns='9.6',original_unchanged=True,
            final_verification_errors=[],promotion_allowed=False,independent_archive_replay_required=True,
            timing={'selected_clock':timing})
        review=dict(status='passed_independent_local_archive_review_scoped_internal_sta_crtmont96',
            recorded_original_unchanged=True,corners=timing,
            clock=dict(measured_constraint_period_ns=9.6,constraint_frequency_mhz=1000/9.6))
        self.assertIsNone(d.scoped_reviewed_clock96(native,{}))
        self.assertEqual(d.scoped_reviewed_clock96(native,review),1000/9.6)
        review['clock']['constraint_frequency_mhz']=105.21
        self.assertIsNone(d.scoped_reviewed_clock96(native,review))
        review['clock']['constraint_frequency_mhz']=1000/9.6
        for kind in ('setup','hold','mpw'):
            timing[corners[0]][kind]['slack_ns']=-.001
            self.assertIsNone(d.scoped_reviewed_clock96(native,review))
            timing[corners[0]][kind]['slack_ns']=.095
        native['original_unchanged']=False
        self.assertIsNone(d.scoped_reviewed_clock96(native,review))
        native['original_unchanged']=True
        del timing[corners[0]]
        self.assertIsNone(d.scoped_reviewed_clock96(native,review))

    def test_track_a_prefers_exact96_projection_and_keeps100_fallback(self):
        old=dict(projected_compute_minutes=10.489487604,projected_compute_seconds=629.36925623,
                 clock_mhz=100,warm_cycles_sample_max=32920,n=65536,base=604832956)
        new=dict(old,projected_compute_minutes=10.06990809968,
                 projected_compute_seconds=604.1944859808,clock_mhz=1000/9.6)
        self.save('crtmont100-compute-projection-v1.json',old)
        self.save('crtmont96-compute-projection-v1.json',new)
        with patch('fpga.synthesis.crtmont96_projection.estimate',return_value=new),\
             patch('fpga.synthesis.crtmont100_projection.estimate',return_value=old):
            self.assertEqual(d.track_a_projection(self.root)['clock_mhz'],1000/9.6)
            self.save('crtmont96-compute-projection-v1.json',dict(new,warm_cycles_sample_max=28823))
            self.assertEqual(d.track_a_projection(self.root)['clock_mhz'],100)
        self.save('crtmont96-compute-projection-v1.json',new)
        with (patch('fpga.synthesis.crtmont96_projection.estimate',side_effect=ValueError('unreviewed')),
              patch('fpga.synthesis.crtmont100_projection.estimate',return_value=old)):
            self.assertEqual(d.track_a_projection(self.root)['clock_mhz'],100)

    def test_clock96_dashboard_catalog_does_not_promote_T5_or_streaming(self):
        rows={spec['id']:spec for spec in d.CATALOG}
        self.assertIn('9.6ns',rows['rootfused_crtmont_g4']['next'])
        self.assertIn('not a measured PRP or T5 clock',rows['rootfused_crtmont_g4']['next'])
        self.assertIn('setup failed',rows['core27_prefill']['next'])
        self.assertIn('not an audited clock',rows['core27_prefill']['next'])
        self.assertIn('no streaming fitted clock',rows['stream_ntt_s1']['next'])
        self.assertEqual(rows['core27_prefill']['gate'],'core27-prefill-aw16-normal-v1/report.json')

    def test_t5_terminal_failure_supersedes_stale_process_without_clock_promotion(self):
        review=dict(status='PASS_scoped_T5_whole64_terminal_fit_archive_replay_NO_CLOCK_PROMOTION',
                    raw_timing=dict(usable_clock_mhz=None,promotion_allowed=False,setup_slack_ns=-2.675,reported_fmax_mhz=78.9),
                    fit=dict(needed_alms=253327,partially_or_completely_used_labs=36726))
        row=dict(state='running',stages=['implemented','full-N normal passed','running','not run'],evidence=[],measurements={})
        with patch.object(d,'read_evidence',return_value=(review,dict(sha256=d.T5_TERMINAL_SHA))):
            d.apply_t5_terminal(row,self.root)
        self.assertEqual(row['state'],'tradeoff')
        self.assertEqual(row['stages'][2:],['route complete','100 MHz setup failed'])
        self.assertIsNone(row['physical_terminal']['usable_clock_mhz'])
        self.assertNotIn('fmax_mhz',row['measurements'])
        self.assertNotIn('audited_internal_clock_mhz',row)

    def test_t5_terminal_unpinned_review_cannot_replace_state(self):
        row=dict(state='partial')
        with patch.object(d,'read_evidence',return_value=({'status':'PASS'},dict(sha256='0'*64))):
            d.apply_t5_terminal(row,self.root)
        self.assertEqual(row,dict(state='partial'))


if __name__ == '__main__':
    unittest.main()

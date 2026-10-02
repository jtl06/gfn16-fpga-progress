"""Scheduling/observation safety tests; no transports or native model work."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fpga.tools import global_queue_v1 as q


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.host = json.loads((q.QUEUE / 'hosts/gcp-c4d-q1.json').read_text())
        self.lane = self.host['lanes'][0]
        self.ticket = dict(id='example', created='2026-10-01T07:00:00Z', priority='P1', promotion_bound=False,
            needs='verilator', tool_identity=self.host['tool_identity'], resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4),
            package=dict(profile='gcp-c4d-static01-v1', max_seconds=3700))

    def test_priority_then_oldest(self):
        older = dict(self.ticket, id='older', created='2026-10-01T06:00:00Z')
        urgent = dict(self.ticket, id='urgent', priority='P0')
        self.assertEqual([t['id'] for t in q.ordered([self.ticket, older, urgent])], ['urgent', 'older', 'example'])

    def test_q1_seed_order_preserves_true_timestamps(self):
        p16 = dict(self.ticket, id='p16c-aw6-q1-v1', created='2026-10-01T07:30:00Z')
        f2 = dict(self.ticket, id='f2-l64-q1-v3', created='2026-10-01T07:00:00Z')
        a10 = dict(self.ticket, id='a10-aw5-f0-native-class-v1', created='2026-10-01T06:00:00Z')
        self.assertEqual([t['id'] for t in q.ordered([a10, f2, p16])], [p16['id'], f2['id'], a10['id']])
        self.assertEqual(p16['created'], '2026-10-01T07:30:00Z')

    def test_missing_package_ineligible(self):
        self.ticket.pop('package')
        self.assertFalse(q.eligible(self.ticket, self.host, self.lane)[0])

    def test_profile_affinity_is_exact(self):
        self.assertFalse(q.eligible(self.ticket, self.host, self.host['lanes'][1])[0])

    def test_wrong_tool_ineligible(self):
        self.ticket['tool_identity'] = 'azure'
        self.assertFalse(q.eligible(self.ticket, self.host, self.lane)[0])

    def test_promotion_l3_required(self):
        self.ticket['promotion_bound'] = True
        self.host['admission']['level'] = 'L1'
        self.assertFalse(q.eligible(self.ticket, self.host, self.lane)[0])

    def test_drain_uses_hard_bound(self):
        self.host['deadline_epoch'] = 10000
        self.assertFalse(q.eligible(self.ticket, self.host, self.lane, now=100)[0])

    def test_ram_cap(self):
        self.ticket['resources']['ram_gib'] = 9
        self.assertFalse(q.eligible(self.ticket, self.host, self.lane)[0])

    def test_missing_hourly_cost_status_fails_closed(self):
        with patch.object(q,'cached_provider_cost',return_value=dict(status='UNRESOLVED',reason='no hourly producer')):
            with self.assertRaisesRegex(ValueError, 'hourly cost UNRESOLVED'):
                q.budget(self.host, 3715, Path('/private/tmp'))

    def test_unknown_unit_retains_lane(self):
        ticket = dict(self.ticket, dispatch=dict(unit='unknown.service', host=self.host['name'], lane='gcp01', phase='launch_sent'))
        with tempfile.TemporaryDirectory() as directory, patch.object(q, 'ssh', return_value={'returncode':0,'stdout':str(Path(directory)/'stdout')}):
            (Path(directory)/'stdout').write_text('LoadState=not-found\n')
            with self.assertRaisesRegex(ValueError, 'lane retained'):
                q.poll(ticket, self.host, Path(directory))
        self.assertEqual(ticket['dispatch']['phase'], 'launch_sent')

    def test_launch_not_replayed_after_sent(self):
        ticket = dict(self.ticket, dispatch=dict(phase='launch_sent'))
        with patch.object(q, 'ssh') as remote:
            q.launch(ticket, self.host, self.lane, Path('/private/tmp'))
        remote.assert_not_called()

    def test_launch_intent_precedes_exactly_one_send(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(q,'QUEUE',Path(directory)):
            ticket=dict(self.ticket,package=dict(native_root='/worker/jobs/example',max_seconds=3700),dispatch=dict(phase='staged',unit='example.service'))
            def send(host,code,evidence,name):
                recorded=json.loads((Path(directory)/'running/example.json').read_text())
                self.assertEqual(recorded['dispatch']['phase'],'launch_sent')
                self.assertIn('systemd-run',code)
                return dict(returncode=0)
            with patch.object(q,'ssh',side_effect=send) as remote:
                q.start_worker(ticket,self.host,self.lane,Path(directory),['python3','worker.py'],'/worker')
            self.assertEqual(remote.call_count,1)
            self.assertEqual(ticket['dispatch']['phase'],'launch_sent')

    def test_real_shared_hourly_cost_abi(self):
        # Actual shared producer receipt, not a new per-job accounting call.
        with tempfile.TemporaryDirectory() as directory:
            value = q.budget(self.host, 3715, Path(directory))
        self.assertEqual(value['schema'], 'provider-hourly-cost-status-v1')
        self.assertEqual(value['status'], 'PASS')
        self.assertEqual(value['admission']['host_id'], 'gcp-c4d')
        self.assertEqual(value['outer_runtime_plus_stop_seconds'], 3715)
        self.assertEqual(value['admission']['per_job_charge_usd'], 0)

    def test_missing_dependency_rejected(self):
        ticket = dict(self.ticket, after=['absent'])
        with self.assertRaisesRegex(ValueError, 'missing dependency'):
            q.bind_dependencies(ticket, {})

    def test_cycles_rejected(self):
        known = {'a':dict(id='a',after=[dict(id='b')]), 'b':dict(id='b',after=[dict(id='a')])}
        with self.assertRaisesRegex(ValueError, 'cyclic'):
            q.validate_graph(known)

    def test_dependency_source_mismatch_rejected(self):
        ticket = dict(self.ticket, after=[dict(id='a',functional_sha256='b'*64)])
        with patch.object(q,'expected_identity',return_value='a'*64):
            with self.assertRaisesRegex(ValueError,'binding mismatch'):
                q.bind_dependencies(ticket, {'a':dict(id='a')})

    def test_native_receipt_releases_successor_not_raw_rc0(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(q,'QUEUE',Path(directory)), patch.object(q,'expected_identity',return_value='a'*64):
            target = Path(directory)/'evidence/a/gate-receipt.json'
            receipt = dict(schema='gfn16-native-gate-receipt-v1',status='PASS_expected_contracts',id='a',
                manifest_sha256='b'*64,contract_sha256='c'*64,candidate_source_sha256='d'*64,promotion_allowed=False,
                steps=[dict(expected_returncode=1,actual_returncode=1)])
            q.atomic(target,receipt)
            upstream = dict(id='a',result=dict(status='needs_independent_review'),dependency_gate=dict(
                status='PASS_expected_contracts',path=str(target),sha256=q.sha(target),manifest_sha256='b'*64,
                contract_sha256='c'*64,candidate_source_sha256='d'*64,functional_sha256='a'*64))
            child = dict(self.ticket,after=[dict(id='a',functional_sha256='a'*64)])
            self.assertTrue(q.dependency_state(child,{'a':upstream})[0])
            upstream.pop('dependency_gate')
            self.assertFalse(q.dependency_state(child,{'a':upstream})[0])

    def test_malformed_receipt_never_passes(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(q,'QUEUE',Path(directory)), patch.object(q,'expected_identity',return_value='a'*64):
            target = Path(directory)/'evidence/a/gate-receipt.json'
            q.atomic(target,dict(status='PASS_expected_contracts'))
            upstream=dict(id='a',dependency_gate=dict(status='PASS_expected_contracts',path=str(target),sha256=q.sha(target)))
            child=dict(self.ticket,after=[dict(id='a',functional_sha256='a'*64)])
            self.assertIn('invalid dependency evidence',q.dependency_state(child,{'a':upstream})[1])

    def test_observation_timeout_waits_without_failure(self):
        child=dict(self.ticket,after=[dict(id='a',functional_sha256='a'*64)])
        with patch.object(q,'expected_identity',return_value='a'*64):
            ready,reason=q.dependency_state(child,{'a':dict(id='a',dispatch=dict(phase='launch_sent',observation_timeout=True))})
        self.assertFalse(ready)
        self.assertTrue(reason.startswith('waiting'))

    def test_failed_a_cancels_unstarted_b_but_independent_c_proceeds(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(q,'QUEUE',Path(directory)), patch.object(q,'expected_identity',return_value='a'*64):
            for state in ('done','pending','running'):
                (Path(directory)/state).mkdir()
            q.atomic(Path(directory)/'done/a.json',dict(id='a',result=dict(status='terminal_failure')))
            child=dict(self.ticket,id='b',after=[dict(id='a',functional_sha256='a'*64)])
            independent=dict(self.ticket,id='c')
            q.atomic(Path(directory)/'pending/b.json',child)
            q.atomic(Path(directory)/'pending/c.json',independent)
            errors=[];q.reconcile_dependencies(errors)
            self.assertEqual(q.rows('done')[-1]['result']['status'],'cancelled_unstarted_dependency_failure')
            self.assertEqual([t['id'] for t in q.rows('pending')],['c'])
            with patch.object(q,'role_host_compatible',return_value=True):
                self.assertTrue(q.eligible(independent,self.host,self.lane)[0])

    def test_collected_checker_gap_waits_without_cancel_and_reconciles(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(q,'QUEUE',Path(directory)),patch.object(q,'expected_identity',return_value='a'*64):
            parent=dict(self.ticket,id='a',result=dict(status='needs_independent_review',queue_report=dict(worker_status='completed_native_commands_unreviewed')))
            q.await_consumer_gate(parent,q.ConsumerUnavailableError('cross-host functional checker awaits qualified consumer adoption'))
            child=dict(self.ticket,id='b',after=[dict(id='a',functional_sha256='a'*64)])
            q.atomic(Path(directory)/'done/a.json',parent);q.atomic(Path(directory)/'pending/b.json',child)
            with patch.object(q,'gate_result',side_effect=q.ConsumerUnavailableError('cross-host functional checker awaits qualified consumer adoption')):
                q.reconcile_dependencies([])
            self.assertTrue((Path(directory)/'pending/b.json').exists())
            self.assertTrue(q.dependency_state(child,{'a':q.rows('done')[0]})[1].startswith('waiting consumer infrastructure'))
            def success(ticket):
                path=Path(directory)/'evidence/a/gate-receipt.json'
                receipt=dict(schema='gfn16-native-gate-receipt-v1',status='PASS_expected_contracts',id='a',manifest_sha256='b'*64,
                    contract_sha256='c'*64,candidate_source_sha256='d'*64,promotion_allowed=False)
                q.atomic(path,receipt)
                ticket['dependency_gate']=dict(status='PASS_expected_contracts',path=str(path),sha256=q.sha(path),
                    manifest_sha256='b'*64,contract_sha256='c'*64,candidate_source_sha256='d'*64,functional_sha256='a'*64)
                ticket['result']['status']='PASS_expected_contracts'
            with patch.object(q,'gate_result',side_effect=success):q.reconcile_dependencies([])
            self.assertTrue(q.dependency_state(child,{'a':q.rows('done')[0]})[0])
            self.assertEqual(json.loads((Path(directory)/'notifications/a.json').read_text())['result'],'PASS_expected_contracts')

    def test_only_exact_legacy_infrastructure_misclassification_recovers_with_history(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(q,'QUEUE',Path(directory)):
            ticket=dict(self.ticket,id='a',dispatch=dict(invocation='e'*32),result=dict(status='terminal_contract_failure',
                properties=dict(Result='success',ExecMainStatus='0',MainPID='0',ControlGroup=''),
                queue_report=dict(worker_status='completed_native_commands_unreviewed')),
                dependency_gate=dict(status='FAIL_expected_contracts',error='cross-host functional checker awaits qualified consumer adoption'))
            self.assertTrue(q.legacy_consumer_gate_error(ticket))
            for defect in ('error','unit','worker'):
                bad=copy.deepcopy(ticket)
                if defect=='error':bad['dependency_gate']['error']='arithmetic mismatch'
                elif defect=='unit':bad['result']['properties']['ExecMainStatus']='1'
                else:bad['result']['queue_report']['worker_status']='native_command_failure'
                self.assertFalse(q.legacy_consumer_gate_error(bad))
            q.atomic(Path(directory)/'done/a.json',ticket);q.notify_terminal(ticket)
            def success(value):
                value['result']['status']='PASS_expected_contracts';value['dependency_gate']=dict(status='PASS_expected_contracts',sha256='f'*64)
            with patch.object(q,'gate_result',side_effect=success):q.reconcile_dependencies([])
            done=q.rows('done')[0]
            self.assertEqual(json.loads((Path(directory)/'evidence/a/consumer-classification-before-recovery.json').read_text()),ticket)
            self.assertFalse(done['consumer_identity_recovery']['native_replayed'])
            self.assertEqual(json.loads((Path(directory)/'notifications/a.json').read_text())['result'],'PASS_expected_contracts')
            self.assertEqual(len(list((Path(directory)/'notifications/history/a').glob('*.json'))),1)

    def test_actual_captured_pass_survives_checker_gap_without_native_replay(self):
        identifier='s4-p16-diet-term-select-aw16-f1-normal-q1-r2'
        captured=json.loads((q.QUEUE/'done'/(identifier+'.json')).read_text())
        receipt=(q.QUEUE/'evidence'/identifier/'gate-receipt.json').read_bytes()
        self.assertEqual(json.loads(receipt)['status'],'PASS_expected_contracts')
        with tempfile.TemporaryDirectory() as directory,patch.object(q,'QUEUE',Path(directory)):
            original=copy.deepcopy(captured)
            original['result']['status']='terminal_contract_failure'
            original['dependency_gate']=dict(status='FAIL_expected_contracts',error='cross-host functional checker awaits qualified consumer adoption')
            q.atomic(Path(directory)/'done'/(identifier+'.json'),original)
            with patch.object(q,'functional_identity',side_effect=q.ConsumerUnavailableError('cross-host functional checker awaits qualified consumer adoption')):
                q.reconcile_dependencies([])
            waiting=q.rows('done')[0]
            self.assertEqual(waiting['result']['status'],'awaiting_consumer_gate_identity')
            q.reconcile_dependencies([])
            recovered=q.rows('done')[0]
            self.assertEqual(recovered['result']['status'],'PASS_expected_contracts')
            self.assertEqual((Path(directory)/'evidence'/identifier/'gate-receipt.json').read_bytes(),receipt)
            self.assertEqual(recovered['dispatch']['invocation'],captured['dispatch']['invocation'])
            self.assertFalse(recovered['consumer_identity_recovery']['native_replayed'])

    def test_actual_wide_preflight_failure_is_narrow_infrastructure_retry(self):
        identifier='s4-p16-diet-continuous1000-thread8-normal-q1-v1'
        original=q.registry()[identifier]
        self.assertTrue(q.verified_long_selector_failure(original))
        self.assertTrue(q.verified_long_selector_failure(q.registry()['s4-p16-diet-continuous1000-thread8-normal-q1-v2']))
        for defect in ('invocation','runner','active','numerical_output'):
            ticket=copy.deepcopy(original)
            if defect=='invocation':ticket['result']['properties']['InvocationID']='f'*32
            elif defect=='runner':ticket['package']['runner_sha256']='f'*64
            elif defect=='active':ticket['result']['properties']['MainPID']='999'
            else:ticket['result']['queue_report']={'error':'numerical mismatch'}
            self.assertFalse(q.verified_long_selector_failure(ticket))


if __name__ == '__main__':
    unittest.main()

"""Standing audit callback tests; no cloud or native command allowed."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('backend', ROOT/'tools/fit_audit_backend.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class CallbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='audit-backend-test-', dir=ROOT/'artifacts')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.backend = b.AuditBackend(self.root)
        self.no_rpc = patch.object(b.subprocess, 'run', side_effect=AssertionError('native RPC forbidden'))
        self.no_rpc.start()
        self.addCleanup(self.no_rpc.stop)

    def fixture(self, succeeded=True):
        parent = dict(id='p8-fixture', host=self.backend.ad.FIT, slot='c', unit='gfn16-p8-fixture.service',
                      invocation_id='a'*32, request_sha256='b'*64)
        receipt = dict(project='/home/azureuser/gfn16-worker/p8-fixture', native_job_succeeded=succeeded,
                       scope='whole_core',
                       host=parent['host'], unit=parent['unit'], invocation_id=parent['invocation_id'],
                       terminal_proven=True, source_request_sha256=parent['request_sha256'])
        path = self.root/'parent.json'
        path.write_text(json.dumps(receipt))
        return parent, dict(receipt=str(path), receipt_sha256=b.sha(path))

    def test_actual_collection_condition_releases_baseline_data_only(self):
        parent, bundle = self.fixture()
        action = self.backend.next(parent, bundle, [])
        self.assertEqual(action['kind'], 'audit')
        self.assertEqual(action['id'], 'p8-fixture-audit0')
        self.assertIsNone(action['selected_period_ns'])
        self.assertIsNone(action['selection_reason'])
        self.assertEqual(action['slot'], 'c')
        self.assertEqual(action['cutoff_utc'], b.END.isoformat())

    def test_failed_parent_does_not_release_audit(self):
        parent, bundle = self.fixture(False)
        self.assertIsNone(self.backend.next(parent, bundle, []))

    def test_actual_nine_ns_receipt_releases_own_layout_search(self):
        spec=importlib.util.spec_from_file_location('nine_ns_state',ROOT/'tools/fit_dispatch.py');state=importlib.util.module_from_spec(spec);spec.loader.exec_module(state)
        records=state.Journal(ROOT/'queue/standing-fit-state',ROOT/'queue/standing-fits').current()
        parent=records['s4-p8-r75-whole-9000-high-effort-v1'];audit=records['s4-p8-r75-whole-9000-high-effort-v1-audit0']
        action=self.backend.next(parent['handle'],parent['bundle'],[audit['bundle']])
        self.assertEqual(action['selected_period_ns'],'10.764')
        self.assertEqual(action['parent_handle']['invocation_id'],parent['handle']['invocation_id'])

    def test_any_exact_parent_slot_is_preferred_without_moving_layout(self):
        parent,bundle=self.fixture()
        parent['slot']='a'
        action=self.backend.next(parent,bundle,[])
        self.assertEqual(action['slot'],'a')
        self.assertEqual(action['parent_handle']['slot'],'a')
        parent['slot']='unknown'
        with self.assertRaisesRegex(ValueError,'exact same-host parent'):
            self.backend.next(parent,bundle,[])

    def test_hourly_native_admission_never_calls_financial_meter(self):
        ad=self.backend.ad
        status=dict(schema='provider-hourly-cost-status-v1',provider='azure',status='PASS')
        request=dict(host=ad.FIT,host_hours_budget=dict(hourly_provider_status=status))
        with patch.object(ad,'meter',side_effect=AssertionError('per-launch financial call')):
            self.assertEqual(ad.admission(request,ROOT)['per_job_charge_usd'],0)
            pins=ad.runtime_pins(ad.FIT,request['host_hours_budget'],ROOT)
            self.assertEqual(set(pins),{'plain_fit_audit_signed_v1.py',ad.AUDIT,ad.TCL})
            for state in ('BLOCKED','UNRESOLVED'):
                status['status']=state
                with self.assertRaisesRegex(ValueError,'must PASS'):
                    ad.admission(request,ROOT)

    def test_original_handle_and_receipt_tamper_fail_closed(self):
        parent, bundle = self.fixture()
        parent['invocation_id'] = 'c'*32
        with self.assertRaisesRegex(ValueError, 'exact same-host parent'):
            self.backend.next(parent, bundle, [])
        bundle['receipt_sha256'] = 'd'*64
        with self.assertRaisesRegex(ValueError, 'SHA drift'):
            self.backend.next(parent, bundle, [])

    def test_implementation_pins_and_horizon(self):
        for relative, expected in b.PINS.items():
            self.assertEqual(b.sha(ROOT/relative), expected)
        self.assertEqual(self.backend.horizon_seconds, 2280)
        self.assertEqual(self.backend.ad.INNER, 2100)

    def test_native_audit_stage_intake_boundary_retains_runtime(self):
        stage=b.module('audit_stage_boundary','tools/fit_audit_stage.py')
        stage.require_intake_open(b.END,b.END-timedelta(seconds=1))
        for stamp in (b.END,b.END+timedelta(seconds=1)):
            with self.assertRaisesRegex(ValueError,'intake cutoff'):
                stage.require_intake_open(b.END,stamp)
        with self.assertRaises(ValueError):
            stage.require_intake_open(b.END+timedelta(seconds=1),b.END-timedelta(seconds=1))
        self.assertEqual(self.backend.horizon_seconds,2280)
        self.assertEqual(self.backend.ad.INNER,2100)

    def test_canonical_raw_ready_selector_is_bounded_and_read_only(self):
        tcl=(ROOT/'synthesis/postfit_path_classes.tcl').read_text()
        self.assertIn('{canonical_raw_ready {*raw_ready*} {*image_banks*} 10}',tcl)
        self.assertIn('-npaths $path_limit',tcl)
        self.assertNotIn('set_false_path',tcl)
        self.assertNotIn('execute_module',tcl)
        self.assertIn('{fault_sinks {} {*controller_error* *fault_replicas*fault_q*} 100}',tcl)
        self.assertIn('if {$from_pattern ne ""} { lappend args -from $from_nodes }',tcl)
        self.assertIn('{canonical_raw_ready_data {*raw_ready*} {*image_banks*} 10 {*image_banks*|ram_block*|portadatain*}}',tcl)
        self.assertIn('if {$through_pattern ne ""} { lappend args -through $through_nodes }',tcl)
        self.assertIn('unsupported_get_pins',tcl)

    def test_exact_report_parser_failure_collects_as_failure_not_clock_result(self):
        c=b.module('current_collector','tools/collect_plain_fit_audit_signed_v1.py')
        unit='gfn16-parser-fixture.service'
        proof=dict(unit=unit,manager_elapsed_seconds=60,terminal_kind='failed',
            manager_terminal_message=unit+": Failed with result 'exit-code'.",
            manager_main_exit_messages=[unit+': Main process exited, code=exited, status=2/INVALIDARGUMENT'])
        result=dict(returncode=2,native_execution_complete=False,final_errors=[],status='failed_native_or_evidence',
                    reason='typed native STA-only result',timing_closes=False)
        receipt=dict(status='failed_native_or_evidence',native_execution_complete=False,timing_closes=False,
            original_unchanged=True,compiled_input_unchanged=True,final_verification_errors=[],fit_commands=0,
            error="ValueError('unknown setup relationship/nonfinite timing')",native_commands=[dict(returncode=0)])
        self.assertTrue(c.report_parser_failure(result,receipt));c.typed_terminal(proof,result,receipt)
        for field,value in [('original_unchanged',False),('compiled_input_unchanged',False),
                            ('fit_commands',1),('native_commands',[dict(returncode=1)]),('error','unrelated tool failure')]:
            changed=dict(receipt,**{field:value})
            with self.assertRaises(ValueError):c.typed_terminal(proof,result,changed)
        with self.assertRaises(ValueError):c.typed_terminal(dict(proof,terminal_kind='active'),result,receipt)

    def test_prepared_stage_recovers_exact_handle_without_prepare_or_launch_rpc(self):
        handle = dict(tools='/home/azureuser/gfn16-worker/audit-tools-fixture',
                      host=self.backend.ad.FIT, slot='c', remote_config='/remote/config.json',
                      config=dict(sha256='a'*64), package_sha256='b'*64)
        prepared = dict(config_sha256='a'*64, request_path='/remote/request.json',
                        request_sha256='c'*64, spec_sha256='d'*64)
        with patch.object(self.backend.q, 'regular', return_value=b'archive'), \
                patch.object(self.backend, 'remote', side_effect=[dict(staged=True, prepared=True), prepared]) as rpc:
            result = self.backend.stage(handle, self.root/'unused.tar.gz')
        self.assertEqual(rpc.call_count, 2)
        self.assertIn('prior start intent requires observation', rpc.call_args_list[0].args[1])
        self.assertEqual(result['request_sha256'], 'c'*64)
        self.assertEqual(result['remote_request'], '/remote/request.json')

    def test_recovered_preparation_config_drift_cannot_launch(self):
        handle = dict(tools='/home/azureuser/gfn16-worker/audit-tools-fixture',
                      host=self.backend.ad.FIT, slot='c', remote_config='/remote/config.json',
                      config=dict(sha256='a'*64), package_sha256='b'*64)
        with patch.object(self.backend.q, 'regular', return_value=b'archive'), \
                patch.object(self.backend, 'remote', side_effect=[dict(staged=True, prepared=True), dict(config_sha256='c'*64)]):
            with self.assertRaisesRegex(ValueError, 'native preparation config identity'):
                self.backend.stage(handle, self.root/'unused.tar.gz')

    def test_source_packet_contains_exact_config_budget_and_stage_closure(self):
        request = ROOT/'queue/fit-recovery-controller-azure75-v17/prepared/p8-whole-host-10000-f164-attempt0/fit-queue-tools-p8-whole-host-10000-f164/request.json'
        if not request.exists():
            self.skipTest('actual source package is not present')
        original = json.loads(request.read_text())
        parent, bundle = self.fixture()
        parent.update(request=dict(path=str(request), sha256=b.sha(request)),
                      request_sha256=b.sha(request), remote_request='/home/azureuser/gfn16-worker/fit-queue-tools-p8-whole-host-10000-f164/request.json')
        value = json.loads(Path(bundle['receipt']).read_text())
        value.update(source_request_sha256=parent['request_sha256'], project='/home/azureuser/gfn16-worker/'+original['project_name'])
        Path(bundle['receipt']).write_text(json.dumps(value))
        bundle['receipt_sha256'] = b.sha(bundle['receipt'])
        action = self.backend.next(parent, bundle, [])
        quote = json.loads((ROOT/'results/throughput-20260929/fit-recovery-azure-both-on-1753-v1.json').read_text())
        observed = datetime.fromisoformat(quote['observed_at_utc'])
        status=dict(schema='provider-hourly-cost-status-v1',provider='azure',status='PASS')
        with patch.object(self.backend.money,'hourly',return_value=status), patch.object(self.backend.ad,'meter',side_effect=AssertionError('per-launch arithmetic')):
            handle, helpers, archive = self.backend.prepare(action, self.root/'prepared', {}, observed)
        config = json.loads(Path(handle['config']['path']).read_text())
        self.assertEqual(config['original_request']['sha256'], b.sha(request))
        self.assertEqual(config['manifest_sha256'], original['project']['manifest_sha256'])
        self.assertIsNone(config['selected_period_ns'])
        self.assertEqual(helpers['fit_audit_stage.py'], b.PINS['tools/fit_audit_stage.py'])
        self.assertEqual(helpers['plain_fit_audit_signed_v1.py'], b.PINS['cloud/plain_fit_audit_signed_v1.py'])
        self.assertEqual(config['hourly_provider_status'],status)
        self.assertEqual(handle['package_sha256'], b.sha(archive))
        diagnostic=dict(action,id='p8-fixture-class-report',parent_id='p8-fixture-class-report',report_path_classes=True)
        with patch.object(self.backend.money,'hourly',return_value=status):
            handle,helpers,archive=self.backend.prepare(diagnostic,self.root/'class-prepared',{},observed)
        config=json.loads(Path(handle['config']['path']).read_text())
        tools=Path(handle['config']['path']).parent
        self.assertEqual(config['adapter']['sha256'],b.sha(tools/'plain_fit_audit_signed_v1.py'))
        self.assertIn(b.sha(tools/self.backend.ad.TCL),(tools/'plain_fit_audit_signed_v1.py').read_text())
        self.assertIn('report_path_classes $output $phase $index $name',(tools/self.backend.ad.TCL).read_text())
        self.assertNotIn('report_path_classes',(ROOT/'synthesis'/self.backend.ad.TCL).read_text())
        self.assertEqual(self.backend.horizon_seconds,2280)


if __name__ == '__main__':
    unittest.main()

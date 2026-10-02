"""Standing vertical slice and uncertain lifecycle fixtures, never cloud/native."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

FPGA = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


d = load('standing_dispatch_tests', FPGA/'tools/fit_dispatch.py')
s = load('standing_submit_tests', FPGA/'tools/fit_submit.py')
POLICY = d.reference(FPGA/'cloud/fit-policy-v1.json')
PROFILES = d.reference(FPGA/'cloud/fit-host-profiles-v1.json')
SOURCE = FPGA/'results/throughput-20260929/a10-field-physical-probe-v1/project-workers4'
NOW = datetime(2026, 10, 1, 19, tzinfo=timezone.utc)
HOST = 'gfn16-azure-f16'


class Backend:
    def __init__(self, first='a'*32):
        self.calls, self.first, self.active = [], first, True
        self.audits = None
        self.manifest_sha = None

    def preflight(self, host, slot, memory_bytes=None):
        self.calls.append(('preflight', host, slot))
        return {}

    def stage(self, handle, archive):
        self.calls.append(('stage', handle['id']))

    def launch(self, handle, helpers):
        self.calls.append(('launch', handle['id']))
        return dict(state=dict(MainPID='42', ActiveState='active'), invocation_id=self.first, request_sha256=handle['request_sha256'])

    def observe(self, handle):
        self.calls.append(('observe', handle['id']))
        return dict(state=dict(MainPID='42' if self.active else '0', ActiveState='active' if self.active else 'inactive'), invocation_id=handle.get('invocation_id', self.first), request_sha256=handle['request_sha256'])

    def collect(self, handle):
        self.calls.append(('collect', handle['id']))
        return dict(receipt='fixture-only', receipt_sha256='b'*64, evidence='fixture-only')

    def verify_terminal(self, handle, bundle):
        return 'native_fit_success'


def prepare(ticket, host, slot, directory, topology, now):
    directory.mkdir()
    path = directory/'request.json'
    d.save(path, dict(fixture_only=True))
    ref = d.reference(path)
    handle = dict(id=ticket['id'], host=host, slot=slot, kind='fit', unit='gfn16-'+ticket['id']+'.service', project_name=ticket['id'], scope=ticket['scope'],
                  request=ref, request_sha256=ref['sha256'], after_collection_action=ticket['after_collection_action'], track=ticket['track'])
    return handle, {}, path


class StandingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='standing-fit-test-', dir=FPGA/'artifacts')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.queue, self.state = self.root/'queue', self.root/'state'
        self.no_rpc = patch.object(d.subprocess, 'run', side_effect=AssertionError('cloud/native RPC forbidden'))
        self.no_rpc.start()
        self.addCleanup(self.no_rpc.stop)
        self.clock_patch=patch.object(d,'datetime',wraps=datetime)
        self.clock=self.clock_patch.start()
        self.clock.now.return_value=NOW
        self.addCleanup(self.clock_patch.stop)

    def submit(self, identifier='fixture', **kwargs):
        return s.submit(self.queue, identifier, SOURCE, '9.500', 2, {'azure4':['a']}, 'component_probe',
                        {'exemption':'component_sizing_probe'}, track='S', purpose='sizing', **kwargs)

    def controller(self, backend, **kwargs):
        return d.Controller(self.queue, self.state, POLICY, PROFILES, backend, prepare=prepare, **kwargs)

    def test_submit_is_idempotent_immutable_and_settings_only_generation(self):
        before = d.snapshot(SOURCE)
        ref = self.submit()
        self.assertEqual(self.submit(), ref)
        ticket = d.read(ref)
        generated = d.generate(ticket, self.root/'generated', 6)
        manifest = json.loads((generated/'manifest.json').read_text())
        self.assertEqual(manifest['source_sha256'], before['source_sha256'])
        self.assertEqual(manifest['compile_processors'], 6)
        self.assertEqual(manifest['clock_period_ns'], 9.5)
        self.assertEqual(manifest['seed'], 2)
        self.assertIn('NUM_PARALLEL_PROCESSORS 6', (generated/'probe.qsf').read_text())
        self.assertIn('SEED 2', (generated/'probe.qsf').read_text())
        self.assertIn('ENABLE_INTERMEDIATE_SNAPSHOTS on', (generated/'probe.qsf').read_text())
        self.assertEqual((generated/'run.tcl').read_text(), d.frozen_queue().module('fit_source', 'cloud/plain_fit_v5.py').FULL_TCL)
        self.assertEqual(d.snapshot(SOURCE), before)
        with self.assertRaisesRegex(ValueError, 'cannot replace'):
            s.submit(self.queue, 'fixture', SOURCE, '9.668', 2, {'azure4':['a']}, 'component_probe', {'exemption':'component_sizing_probe'})

    def test_performance_effort_is_explicit_settings_only(self):
        before=d.snapshot(SOURCE)
        ticket=d.read(self.submit(optimization_mode='High Performance Effort'))
        generated=d.generate(ticket,self.root/'high-effort',6)
        qsf=(generated/'probe.qsf').read_text()
        self.assertEqual(qsf.count('set_global_assignment -name OPTIMIZATION_MODE "High Performance Effort"'),1)
        self.assertEqual(json.loads((generated/'manifest.json').read_text())['source_sha256'],before['source_sha256'])
        self.assertEqual(d.snapshot(SOURCE),before)
        with self.assertRaisesRegex(ValueError,'optimization mode'):d.settings('9',1,6,'unqualified')

    def test_installed_aggressive_area_is_explicit_settings_only(self):
        before=d.snapshot(SOURCE)
        ticket=d.read(self.submit(optimization_mode='Aggressive Area'))
        generated=d.generate(ticket,self.root/'area-effort',4)
        self.assertEqual((generated/'probe.qsf').read_text().count('set_global_assignment -name OPTIMIZATION_MODE "Aggressive Area"'),1)
        self.assertEqual(json.loads((generated/'manifest.json').read_text())['source_sha256'],before['source_sha256'])
        self.assertEqual(d.snapshot(SOURCE),before)

    def test_known_vendor_suffix_normalization_preserves_source_and_records_removal(self):
        ticket=json.loads((FPGA/'queue/standing-fits/tickets/s4-root-outputreg-warm-p16-f0-v1.json').read_text())
        source=Path(ticket['snapshot']['path']);before=d.snapshot(source)
        generated=d.generate(ticket,self.root/'normalized-parent',4)
        manifest=json.loads((generated/'manifest.json').read_text());record=manifest['parent_control_normalization']
        self.assertEqual(record['original_sha256'],ticket['snapshot']['files']['probe.qsf'])
        raw=(source/'probe.qsf').read_bytes();clean=raw[:-len(record['removed_suffix'].encode())]
        self.assertEqual(record['normalized_sha256'],d.digest(clean))
        self.assertNotIn('LAST_QUARTUS_VERSION',(generated/'probe.qsf').read_text())
        self.assertEqual(manifest['source_sha256'],before['source_sha256'])
        self.assertEqual(d.snapshot(source),before)
        for bad in (raw+b'set_global_assignment -name SEED 99\n',raw+record['removed_suffix'].encode(),raw.replace(b'26.1.0',b'26.2.0')):
            with self.assertRaisesRegex(ValueError,'exact terminal'):d.normalize_parent_qsf(bad,d.digest(bad))
        with self.assertRaisesRegex(ValueError,'source identity'):
            d.normalize_parent_qsf(raw.replace(b'SEED 1',b'SEED 9'),record['original_sha256'])

    def test_superseded_unstarted_ticket_never_launches_after_prep_fix(self):
        self.submit('superseded');backend=Backend();controller=self.controller(backend)
        controller.money.policy['priorities']['superseded_unstarted_ids']=['superseded']
        with patch.object(controller.money,'recheck'):current=controller.tick(NOW)
        self.assertEqual(current['superseded']['phase'],'queued')
        self.assertEqual(backend.calls,[])

    def test_native_source_join_is_exact_and_path_representation_safe(self):
        self.assertEqual(d.join_native_sources({'leaf.sv':'a'*64},{'rtl/kernel/leaf.sv':'a'*64}),{'leaf.sv':'rtl/kernel/leaf.sv'})
        self.assertEqual(d.join_native_sources({'leaf.sv':'a'*64},{'rtl/leaf.sv':'a'*64}),{'leaf.sv':'rtl/leaf.sv'})
        for sources in ({'rtl/kernel/leaf.sv':'b'*64},{'rtl/other.sv':'a'*64},
                        {'reference/leaf.sv':'a'*64},{'rtl/../leaf.sv':'a'*64},
                        {'rtl/leaf.sv':'a'*64,'rtl/kernel/leaf.sv':'a'*64}):
            with self.assertRaisesRegex(ValueError,'unambiguous'):d.join_native_sources({'leaf.sv':'a'*64},sources)
        for key in ('s4-canonical-write-parent-p16-v1','s4-canonical-write-candidate-p16-v1'):
            ticket=json.loads((FPGA/'queue/standing-fits/tickets'/(key+'.json')).read_text())
            proof=d.native_source_gate(ticket)
            self.assertEqual(proof['source_sha256'],ticket['snapshot']['source_sha256'])
            self.assertTrue(all(path.startswith('rtl/kernel/') for path in proof['source_paths'].values()))

    def test_provisional_geometry_requires_exact_both_maps_and_captured_generator(self):
        root=self.root/'geometry-root';generator=root/'reference/combined.py'
        generator.parent.mkdir(parents=True);generator.write_text('# pure fixture\n')
        pin=d.digest(generator.read_bytes())
        small=dict(parameters=dict(AW=8,P=16,CONTEXTS=2),top='small',files={'small.sv':'a'*64},source_sha256={'reference/combined.py':pin})
        full=dict(parameters=dict(AW=16,P=16,CONTEXTS=2),top='full',files={'full.sv':'b'*64},source_sha256={'reference/combined.py':pin})
        proof=dict(schema='fit-provisional-aw8-geometry-v1',generator=d.reference(generator),kwargs=dict(p=16,contexts=2,allow_full_constants=True),native_n=256,fit_n=65536)
        proof_path=root/'proof.json';d.save(proof_path,proof)
        project=root/'project';d.save(project/'manifest.json',dict(top='full',core_parameters=full['parameters']))
        ticket=dict(provisional_geometry=d.reference(proof_path),snapshot=dict(path=str(project),source_sha256=full['files']))
        report=dict(sources={'lineage/reference/combined.py':pin,'rtl/small.sv':'a'*64})
        with patch.object(d,'FPGA',root),patch.object(d,'regenerate_geometries',return_value=[small,full]):
            result=d.provisional_geometry_join(ticket,report)
            self.assertFalse(result['full_size_native_pass']);self.assertFalse(result['promotion_allowed'])
            self.assertEqual(result['qualification_scope'],'provisional_AW8_normal_only_full_size_pending')
            for changed in ({'lineage/reference/combined.py':'c'*64,'rtl/small.sv':'a'*64},
                            {'lineage/reference/combined.py':pin,'rtl/small.sv':'c'*64},
                            {'rtl/small.sv':'a'*64}):
                with self.assertRaises(ValueError):d.provisional_geometry_join(ticket,dict(sources=changed))
            bad=deepcopy(ticket);bad['snapshot']['source_sha256']={'full.sv':'c'*64}
            with self.assertRaises(ValueError):d.provisional_geometry_join(bad,report)
            badfull=deepcopy(full);badfull['parameters']['P']=8
            with patch.object(d,'regenerate_geometries',return_value=[small,badfull]):
                with self.assertRaises(ValueError):d.provisional_geometry_join(ticket,report)
            generator.write_text('# changed source\n')
            with self.assertRaises(ValueError):d.provisional_geometry_join(ticket,report)

    def test_collected_native_audit_failure_releases_claim_without_retry(self):
        backend=Backend();backend.active=False
        backend.verify_terminal=lambda handle,bundle:'audit_native_failure'
        controller=self.controller(backend)
        handle=dict(id='failed-audit',kind='audit',scope='component_probe',host=HOST,slot='a',
                    unit='gfn16-failed-audit.service',request_sha256='c'*64,invocation_id='a'*32)
        controller.journal.append('adopt_intent','failed-audit',handle=handle)
        controller.journal.append('started','failed-audit')
        with patch.object(controller.money,'recheck'):current=controller.tick(NOW)
        self.assertEqual(current['failed-audit']['phase'],'terminal')
        self.assertEqual(current['failed-audit']['outcome'],'audit_native_failure')
        self.assertFalse(any(call[0] in ('launch','stage') for call in backend.calls))

    def test_postfit_summary_is_nonblocking_and_bounded_to_owned_state(self):
        controller=self.controller(Backend())
        directory=self.state/'terminal/fixture';directory.mkdir(parents=True)
        receipt=directory/'receipt.json';receipt.write_text('{}')
        controller.postfit_summary(dict(scope='whole_core',kind='fit'),dict(receipt=str(receipt),evidence=str(directory)))
        value=json.loads((directory/'setup-class-summary.json').read_text())
        self.assertEqual(value['status'],'diagnostic_unavailable')
        controller.postfit_summary(dict(scope='whole_core',kind='fit'),dict(receipt='relative-fixture',evidence='relative-fixture'))

    def test_new_tickets_join_same_journal_without_migration_or_duplicate_launch(self):
        self.submit('one')
        backend = Backend()
        controller = self.controller(backend)
        self.assertEqual(controller.tick(NOW)['one']['phase'], 'started')
        self.submit('two')
        controller = self.controller(backend)
        current = controller.tick(NOW)
        self.assertEqual(current['two']['phase'], 'queued')
        self.assertEqual(sum(c[0] == 'launch' for c in backend.calls), 1)
        backend.active = False
        current = controller.tick(NOW)
        self.assertEqual(current['one']['phase'], 'terminal')
        self.assertEqual(current['two']['phase'], 'started')
        self.assertEqual(sum(c[0] == 'launch' for c in backend.calls), 2)

    def test_pre_r66_journal_keeps_identity_and_chain_after_tool_edit(self):
        self.state.mkdir()
        identity=d.digest(d.canonical(dict(schema='standing-fit-journal-v1',queue=str(self.queue),code='51595d8cae4bb4f272208064629bc631384e8bc5f94ca59886c86e68915ee8a7')))
        row=dict(sequence=0,previous='0'*64,identity=identity,at_utc=NOW.isoformat(),event='blocked',job='fixture',reason='preserved')
        row['sha256']=d.digest(d.canonical(row))
        (self.state/'events.jsonl').write_bytes(d.canonical(row)+b'\n')
        journal=d.Journal(self.state,self.queue)
        journal.append('blocked','fixture',reason='next')
        self.assertEqual(journal.rows[-1]['identity'],identity)
        self.assertEqual(journal.rows[-1]['previous'],row['sha256'])
        with self.assertRaisesRegex(ValueError,'queue identity'):
            d.Journal(self.state,self.root/'wrong-queue')

    def test_critical_aws_first_and_unavailable_host_does_not_block_azure(self):
        for unavailable in (False,True):
            with self.subTest(unavailable=unavailable):
                key='routing-'+str(unavailable).lower()
                s.submit(self.queue,key,SOURCE,'10',1,{'azure4':['a'],'aws6':['a','b']},'component_probe',
                         {'exemption':'component_sizing_probe'},track='S',purpose='p16_diet')
                backend=Backend()
                original=backend.preflight
                def preflight(host,slot):
                    if unavailable and host=='gfn16-aws-m8i':
                        raise ValueError('TargetNotConnected')
                    return original(host,slot)
                backend.preflight=preflight
                controller=self.controller(backend)
                # Policy-data fixture only; production data is independently checked.
                controller.money.policy['priorities']['aws_first_ids']=[key]
                with patch.object(controller.money,'recheck'):
                    current=controller.tick(NOW)
                self.assertEqual(current[key]['phase'],'started')
                self.assertEqual(current[key]['handle']['host'],HOST if unavailable else 'gfn16-aws-m8i')

    def test_p16_priority_preserves_active_and_parks_extra_p8(self):
        self.submit('p8-allowed',priority=0);self.submit('p8-parked',priority=-1);self.submit('p16-ready',priority=99)
        backend=Backend();controller=self.controller(backend)
        controller.money.policy['priorities'].update(preferred_lanes=16,parked_lanes=[8],allowed_secondary_ids=['p8-allowed'])
        def lanes(record):return 16 if Path(record['ticket']['path']).stem=='p16-ready' else 8
        with patch.object(controller.money,'recheck'),patch.object(d,'design_lanes',side_effect=lanes):
            current=controller.tick(NOW)
            self.assertEqual(current['p16-ready']['phase'],'started')
            self.assertEqual(current['p8-allowed']['phase'],'queued')
            self.assertEqual(current['p8-parked']['phase'],'queued')
            current=controller.tick(NOW)
            self.assertEqual(sum(c[0]=='launch' for c in backend.calls),1)
            backend.active=False
            current=controller.tick(NOW)
            self.assertEqual(current['p8-allowed']['phase'],'started')
            self.assertEqual(current['p8-parked']['phase'],'queued')

    def test_ready_p16_resource_block_does_not_fill_with_secondary_p8(self):
        self.submit('p16-ready');self.submit('p8-allowed')
        backend=Backend();controller=self.controller(backend)
        controller.money.policy['priorities'].update(preferred_lanes=16,parked_lanes=[8],allowed_secondary_ids=['p8-allowed'])
        backend.preflight=lambda host,slot:(_ for _ in ()).throw(ValueError('actual P16 resource unavailable'))
        with patch.object(controller.money,'recheck'),patch.object(d,'design_lanes',side_effect=lambda r:16 if Path(r['ticket']['path']).stem=='p16-ready' else 8):
            current=controller.tick(NOW)
        self.assertEqual(len([r for r in controller.journal.rows if r['event']=='blocked']),1)
        self.assertEqual(current['p8-allowed']['phase'],'queued')

    def test_area_hold_parks_only_unstarted_whole_p16(self):
        self.submit('field-ready')
        original=json.loads((FPGA/'queue/standing-fits/tickets/s4-p16-timing-whole-9000-high-effort-v1.json').read_text())
        original.update(id='whole-held');d.save(self.queue/'tickets/whole-held.json',original)
        backend=Backend();controller=self.controller(backend)
        controller.money.policy['priorities'].update(preferred_lanes=16,hold_whole_lanes=[16],field_probes_first=True)
        with patch.object(controller.money,'recheck'),patch.object(d,'design_lanes',return_value=16),patch.object(d,'native_source_gate',return_value={'source_sha256':original['snapshot']['source_sha256']}):
            current=controller.tick(NOW)
        self.assertEqual(current['whole-held']['phase'],'queued')
        self.assertEqual(current['field-ready']['phase'],'started')
        self.assertEqual(sum(c[0]=='launch' for c in backend.calls),1)

    def test_collected_p16_callback_retains_layout_and_starts_requested_10ns(self):
        existing=d.Journal(FPGA/'queue/standing-fit-state',FPGA/'queue/standing-fits').current()
        key='s4-p16-diet-whole-9000-azure-clockprobe-v1';record=existing[key]
        backend=Backend();audit_module=load('p16_callback_fixture',FPGA/'tools/fit_audit_backend.py');backend.audits=audit_module.AuditBackend(self.state)
        controller=self.controller(backend)
        handle=dict(record['handle'],after_collection_action=None)
        controller.journal.append('adopt_intent',key,handle=handle)
        controller.journal.append('terminal',key,outcome='native_fit_success',bundle=record['bundle'])
        action=controller.configure_collected_audit(key,'10.000')
        self.assertEqual(action['selected_period_ns'],'10.000')
        self.assertEqual(action['parent_handle']['invocation_id'],handle['invocation_id'])
        self.assertEqual(action['host'],handle['host'])
        self.assertEqual(controller.journal.current()[key]['handle']['after_collection_action'],dict(kind='timing_audit_search',max_selected=8))
        with self.assertRaises(ValueError):controller.configure_collected_audit(key,'10.000')

    def test_area_route_hold_does_not_block_genuine_whole_synthesis(self):
        project=FPGA/'artifacts/s4-p16-diet-whole-syn-screen-v1/project'
        s.submit(self.queue,'syn-held-fixture',project,'10',1,{'aws6':['a']},'whole_core',
            {'exemption':'synthesis_only_resource_screen'},track='S',purpose='whole',mode='synthesis_only',native_source_gate='native-fixture')
        backend=Backend();controller=self.controller(backend)
        controller.money.policy['priorities'].update(hold_whole_lanes=[16],whole_p16_blocked_hosts=['gfn16-aws-m8i'])
        def syn_prepare(*args):
            handle,helpers,archive=prepare(*args)
            handle.update(kind='synthesis',scope='whole_core')
            return handle,helpers,archive
        controller.prepare=syn_prepare
        with patch.object(controller.money,'recheck'),patch.object(d,'design_lanes',return_value=16),patch.object(d,'native_source_gate',return_value={'fixture':True}):
            current=controller.tick(NOW)
        self.assertEqual(current['syn-held-fixture']['phase'],'started')
        self.assertEqual(current['syn-held-fixture']['handle']['kind'],'synthesis')
        self.assertEqual(sum(c[0]=='launch' for c in backend.calls),1)

    def test_audit_reuses_parent_slot_or_another_free_same_host_slot(self):
        self.submit('occupant')
        backend=Backend();controller=self.controller(backend)
        controller.tick(NOW)
        class Audits:
            def prepare(self,action,directory,topology,now):
                ticket=dict(id=action['id'],scope='whole_core',after_collection_action=None,track='S')
                handle,helpers,archive=prepare(ticket,action['host'],action['slot'],directory,topology,now)
                handle.update(kind='audit',parent_id='completed-parent')
                return handle,helpers,archive
        backend.audits=Audits()
        action=dict(kind='audit',id='audit-fixture',host=HOST,slot='a',parent_id='completed-parent',parent_handle=dict(host=HOST,slot='a'))
        controller.journal.append('action',action['id'],action=action)
        current=controller.tick(NOW)
        self.assertEqual(current['audit-fixture']['handle']['host'],HOST)
        self.assertEqual(current['audit-fixture']['handle']['slot'],'b')

    def test_unknown_start_claim_retained_and_restart_never_retries(self):
        for unknown in (None, False, 123, {}, '', 'BAD'):
            with self.subTest(unknown=unknown), tempfile.TemporaryDirectory(dir=self.root) as directory:
                state = Path(directory).resolve()
                self.submit()
                backend = Backend(unknown)
                controller = d.Controller(self.queue, state, POLICY, PROFILES, backend, prepare=prepare)
                self.assertEqual(controller.tick(NOW)['fixture']['phase'], 'launch_attempt')
                controller = d.Controller(self.queue, state, POLICY, PROFILES, backend, prepare=prepare)
                self.assertEqual(controller.tick(NOW)['fixture']['phase'], 'launch_attempt')
                self.assertEqual(sum(c[0] == 'launch' for c in backend.calls), 1)
                self.assertFalse(any(c[0] == 'collect' for c in backend.calls))

    def test_typed_native_requirements_and_pause_block_start_not_observation(self):
        gate = self.root/'gate.json'
        d.save(gate, {'passed':1})
        ref = d.reference(gate)
        self.submit(requires=[dict(ref, fields={'passed':True})])
        backend = Backend()
        controller = self.controller(backend)
        self.assertEqual(controller.tick(NOW)['fixture']['phase'], 'queued')
        self.assertFalse(backend.calls)
        self.submit('valid')
        with patch.object(d, 'paused', return_value=True):
            controller.tick(NOW)
        self.assertFalse(backend.calls)
        controller.tick(NOW)
        with patch.object(d, 'paused', return_value=True):
            controller.tick(NOW)
        self.assertTrue(any(c == ('observe', 'valid') for c in backend.calls))

    def test_slot_and_resource_preflight_failure_never_launches(self):
        self.submit()
        backend = Backend()
        backend.preflight = lambda *args: (_ for _ in ()).throw(ValueError('RAM/scratch/lock/deadline floor'))
        current = self.controller(backend).tick(NOW)
        self.assertEqual(current['fixture']['phase'], 'queued')
        self.assertFalse(any(c[0] == 'launch' for c in backend.calls))

    def test_unsupported_terminal_keeps_exact_claim(self):
        self.submit()
        backend = Backend()
        controller = self.controller(backend)
        controller.tick(NOW)
        backend.active = False
        backend.verify_terminal = lambda *args:'unproven_zero_exit'
        self.assertNotEqual(controller.tick(NOW)['fixture']['phase'], 'terminal')
        self.assertEqual(sum(c[0] == 'launch' for c in backend.calls), 1)

    def test_settings_shape_scope_and_runtime_selectors_reject(self):
        for period,seed,workers in (('nan',1,'auto'), ('0',1,'auto'), ('9.5001',1,'auto'), ('10',True,'auto'), ('10',1,8), ('10',1,True)):
            with self.assertRaises(ValueError):
                d.settings(period, seed, workers)
        with self.assertRaisesRegex(ValueError, 'reserved physical'):
            self.submit(workers=6)
        with self.assertRaisesRegex(ValueError, 'field exemption never whole'):
            s.submit(self.queue, 'whole', SOURCE, '10', 1, {'azure4':['a']}, 'whole_core', {'exemption':'component_sizing_probe'})
        with self.assertRaisesRegex(ValueError, 'allowed slot shapes'):
            s.submit(self.queue, 'gcp', SOURCE, '10', 1, {'gcp4':['a']}, 'component_probe', {'exemption':'component_sizing_probe'})

    def test_actual_aws_source_prepare_stages_policy_native_entry_and_field_contract(self):
        ref = self.submit()
        controller = self.controller(Backend())
        ticket = d.read(ref)
        ticket['slot_shapes'] = {'aws6':['b']}
        topology = {
            'hostname':'gfn16-aws-m8i', 'observed_at':'2026-10-01T19:00:00Z', 'cpus':[], 'slots':d.frozen_queue().HOSTS['gfn16-aws-m8i']['slots']}
        status=dict(schema='provider-hourly-cost-status-v1',provider='aws',status='PASS')
        with patch.object(controller.money,'hourly',return_value=status):
            handle, helpers, archive = controller.prepare_fit(ticket, 'gfn16-aws-m8i', 'b', self.root/'actual-preparation', topology, NOW)
        request = d.read(handle['request'])
        self.assertEqual(request['runtime_contract'], d.FIELD)
        self.assertEqual(request['scope'], 'component_probe')
        self.assertEqual(request['hourly_provider_status'],status)
        self.assertEqual(handle['horizon_seconds'], 7260)
        self.assertEqual(helpers['fit_dispatch.py'], d.digest(d.regular(FPGA/'tools/fit_dispatch.py')))
        self.assertIn('fpga/cloud/fit_budget_policy.py', helpers)
        self.assertEqual(request['budget_policy']['path'], 'cloud/fit-policy-v1.json')
        self.assertEqual(d.digest(d.regular(archive)), handle['package_sha256'])
        self.assertEqual(request['project']['source_sha256'], ticket['snapshot']['source_sha256'])

    def test_actual_whole_p16_synthesis_only_packet_never_rewrites_to_full_fit(self):
        project=FPGA/'artifacts/s4-p16-diet-whole-syn-screen-v1/project'
        ref=s.submit(self.queue,'syn-fixture',project,'10',1,{'aws6':['a']},'whole_core',
            {'exemption':'synthesis_only_resource_screen'},track='S',purpose='whole',mode='synthesis_only',native_source_gate='native-fixture')
        ticket=d.read(ref); controller=self.controller(Backend())
        self.assertEqual(controller.tick(NOW)['syn-fixture']['phase'],'queued')
        self.assertEqual(controller.backend.calls,[])
        topology=dict(hostname='gfn16-aws-m8i',observed_at='2026-10-01T19:00:00Z',cpus=[],slots=d.frozen_queue().HOSTS['gfn16-aws-m8i']['slots'])
        evidence=dict(source_sha256=ticket['snapshot']['source_sha256'],fixture_only=True)
        with patch.object(controller.money,'hourly',return_value=dict(schema='provider-hourly-cost-status-v1',provider='aws',status='PASS')), \
             patch.object(d,'native_source_gate',return_value=evidence):
            handle,helpers,archive=controller.prepare_fit(ticket,'gfn16-aws-m8i','a',self.root/'syn-packet',topology,NOW)
        request=d.read(handle['request']);generated=self.root/'syn-packet/generated'
        self.assertEqual(request['mode'],'synthesis_only')
        self.assertEqual(handle['kind'],'synthesis')
        self.assertEqual(handle['horizon_seconds'],7260)
        self.assertEqual(request['runtime_contract'],d.SYNTHESIS)
        self.assertNotEqual(request['runtime_contract'],d.FIELD)
        self.assertEqual((generated/'run.tcl').read_text(),d.SYN_TCL)
        self.assertNotIn('execute_module -tool fit',d.SYN_TCL)
        self.assertNotIn('execute_module -tool sta',d.SYN_TCL)
        self.assertEqual(json.loads((generated/'manifest.json').read_text())['allowed_stages'],['syn'])
        self.assertEqual(request['project']['source_sha256'],ticket['snapshot']['source_sha256'])
        self.assertEqual(len(request['project']['source_sha256']),58)
        self.assertEqual(helpers['aws_syn_v1.py'],d.SYN_HELPER_SHA)
        changed=deepcopy(ticket);changed['mode']='full'
        with self.assertRaisesRegex(ValueError,'stage agreement'):d.validate_ticket(changed,PROFILES)
        changed=deepcopy(ticket);changed['source_contract']={'exemption':'component_sizing_probe'}
        with self.assertRaises(ValueError):d.validate_ticket(changed,PROFILES)

    def test_actual_place_only_packets_preserve_frozen_sources_and_stop_before_route(self):
        sources=[('c1','results/throughput-20260929/trackS-p16-area-timing-whole-v1/synthesis-v1/project','s4-aw16-p16-area-timing-host-normal-q1-v1',67),
                 ('c2','results/throughput-20260929/trackS-p16-stage-tagcompact-v1/syn-source-v1/project','s4-p16-c2-tagcompact-full-normal-q1-v1',53)]
        for key,path,gate,count in sources:
            project=FPGA/path;before=d.snapshot(project)
            ref=s.submit(self.queue,'place-'+key,project,'10',1,{'azure4':['a','d']},'whole_core',
                {'exemption':'place_only_resource_probe'},workers=4,track='S',purpose='p16_diet',mode='place_only',native_source_gate=gate,memory_gib=32)
            ticket=d.read(ref);self.assertEqual(d.runtime_contract(ticket),d.PLACEMENT)
            proof=d.native_source_gate(ticket);self.assertEqual(len(proof['source_sha256']),count)
            controller=self.controller(Backend())
            topology=dict(hostname=HOST,observed_at='2026-10-01T19:00:00Z',cpus=[],slots=d.frozen_queue().HOSTS[HOST]['slots'])
            with patch.object(controller.money,'hourly',return_value=dict(schema='provider-hourly-cost-status-v1',provider='azure',status='PASS')):
                handle,helpers,archive=controller.prepare_fit(ticket,HOST,'a',self.root/('packet-'+key),topology,NOW)
            request=d.read(handle['request']);generated=self.root/('packet-'+key)/'generated'
            self.assertEqual(request['mode'],'place_only');self.assertEqual(handle['kind'],'placement')
            self.assertEqual(request['runtime_contract'],d.PLACEMENT);self.assertEqual(request['memory_bytes'],32<<30)
            self.assertEqual(request['native_gate_evidence']['source_sha256'],before['source_sha256'])
            manifest=json.loads((generated/'manifest.json').read_text())
            self.assertEqual(manifest['allowed_stages'],['syn','plan','place']);self.assertEqual(manifest['native_normal_id'],gate)
            tcl=(generated/'run.tcl').read_text();self.assertEqual(tcl,d.PLACE_TCL)
            self.assertEqual(tcl.count('execute_module -tool fit -args "--plan"'),1)
            self.assertEqual(tcl.count('execute_module -tool fit -args "--place"'),1)
            for command in ('--route','--finalize','execute_module -tool sta'):self.assertNotIn(command,tcl)
            self.assertEqual(helpers['staged_fit.py'],d.PLACE_HELPER_SHA);self.assertEqual(d.snapshot(project),before)
            changed=deepcopy(ticket);changed['mode']='full'
            with self.assertRaises(ValueError):d.validate_ticket(changed,PROFILES)

    def test_place_resource_summary_is_not_routed_success_and_rejects_route_output(self):
        import shutil
        source=FPGA/'queue/standing-fit-state/terminal/s4-p16-diet-whole-full-four-hour-v1-retry1/evidence/project/output_files'
        project=self.root/'place-fixture';output=project/'output_files';output.mkdir(parents=True)
        for name in ('probe.syn.summary','probe.fit.place.rpt'):shutil.copyfile(source/name,output/name)
        result=d.placement_resources(project)
        self.assertTrue(result['placement_success']);self.assertFalse(result['routed']);self.assertFalse(result['timing_closure'])
        self.assertEqual(result['metrics']['alms_needed_packing_adjusted'],314651)
        self.assertEqual(result['metrics']['labs_used'],42065)
        (output/'probe.fit.route.rpt').write_text('route evidence is forbidden')
        with self.assertRaisesRegex(ValueError,'forbids route'):d.placement_resources(project)

    def test_placement32_with_two_live24_fields_launches_one_then_waits(self):
        project=FPGA/'results/throughput-20260929/trackS-p16-area-timing-whole-v1/synthesis-v1/project'
        for key in ('place-a','place-b'):
            s.submit(self.queue,key,project,'10',1,{'azure4':['a','d']},'whole_core',
                {'exemption':'place_only_resource_probe'},workers=4,track='S',purpose='p16_diet',mode='place_only',
                native_source_gate='s4-aw16-p16-area-timing-host-normal-q1-v1',memory_gib=32)
        backend=Backend();controller=self.controller(backend)
        controller.money.policy['priorities']['hold_whole_lanes']=[16]
        for slot in ('b','c'):
            handle=dict(id='live-'+slot,host=HOST,slot=slot,memory_bytes=24<<30,invocation_id='a'*32,request_sha256='b'*64)
            controller.journal.append('adopt_intent',handle['id'],handle=handle)
            controller.journal.append('started',handle['id'])
        def place_prepare(*args):
            handle,helpers,archive=prepare(*args);handle.update(kind='placement',scope='whole_core',memory_bytes=32<<30)
            return handle,helpers,archive
        controller.prepare=place_prepare
        with patch.object(controller.money,'recheck'):current=controller.tick(NOW)
        self.assertEqual(current['place-a']['phase'],'started');self.assertEqual(current['place-b']['phase'],'queued')
        self.assertEqual(sum(c[0]=='launch' for c in backend.calls),1)
        self.assertEqual(sum(r['handle']['memory_bytes'] for r in current.values() if r['phase']=='started'),80<<30)
        self.assertEqual(current['live-b']['handle']['memory_bytes'],24<<30)

    def test_p8_full_three_hour_packet_preserves_full_flow_and_source_gate(self):
        parent=json.loads((FPGA/'queue/standing-fits/tickets/s4-p8-canonical-pipe-whole-10000-v1.json').read_text())
        project=Path(parent['snapshot']['path'])
        ref=s.submit(self.queue,'p8-three-hour',project,'10',1,{'aws6':['a']},'whole_core',
            parent['source_contract'],track='S',purpose='clock_push',native_source_gate='native-fixture',runtime_profile=d.P8_FULL['kind'])
        ticket=d.read(ref);controller=self.controller(Backend())
        self.assertEqual(controller.tick(NOW)['p8-three-hour']['phase'],'queued')
        self.assertEqual(controller.backend.calls,[])
        topology=dict(hostname='gfn16-aws-m8i',observed_at='2026-10-01T19:00:00Z',cpus=[],slots=d.frozen_queue().HOSTS['gfn16-aws-m8i']['slots'])
        evidence=dict(source_sha256=ticket['snapshot']['source_sha256'],fixture_only=True)
        with patch.object(controller.money,'hourly',return_value=dict(schema='provider-hourly-cost-status-v1',provider='aws',status='PASS')),patch.object(d,'native_source_gate',return_value=evidence):
            handle,helpers,archive=controller.prepare_fit(ticket,'gfn16-aws-m8i','a',self.root/'p8-packet',topology,NOW)
        request=d.read(handle['request']);generated=self.root/'p8-packet/generated'
        self.assertEqual(request['mode'],'full')
        self.assertEqual(request['runtime_contract'],d.P8_FULL)
        self.assertEqual(handle['horizon_seconds'],10980)
        self.assertEqual(request['project']['qsf_parameters']['P'],8)
        self.assertIn('structural_spec',request)
        self.assertEqual((generated/'run.tcl').read_bytes(),(project/'run.tcl').read_bytes())
        self.assertEqual(json.loads((generated/'manifest.json').read_text())['allowed_stages'],['syn','fit','sta'])
        self.assertEqual(request['native_gate_evidence'],evidence)
        self.assertIsNone(d.runtime_contract(parent))
        for key,value in [('scope','component_probe'),('mode','synthesis_only'),('track','A'),('native_source_gate',None),('source_contract',{'exemption':'constraint_seed_only'})]:
            changed=deepcopy(ticket);changed[key]=value
            with self.assertRaises(ValueError):d.runtime_contract(changed)
        p16=deepcopy(ticket);p16['snapshot']['path']=str(FPGA/'artifacts/s4-p16-diet-whole-syn-screen-v1/project')
        with self.assertRaises(ValueError):d.runtime_contract(p16)
        with patch.object(d,'native_source_gate',return_value=evidence):
            current=controller.tick(d.END)
        self.assertEqual(current['p8-three-hour']['phase'],'queued')
        self.assertFalse(any(call[0]=='launch' for call in controller.backend.calls))

    def test_synthesis_resource_contract_preserves_estimate_labels_and_forbids_fit(self):
        project=self.root/'summary-project';out=project/'output_files';out.mkdir(parents=True)
        (out/'probe.syn.summary').write_text('Synthesis Status : Successful\nLogic utilization estimate (in ALMs) : 300,001\nTotal registers : 410000\nEstimated DSP Blocks Post-Merging : 1350\n')
        helper=d.load(FPGA/'cloud/aws_syn_v1.py',d.SYN_HELPER_SHA)
        value=helper.summarize_synthesis(project)
        self.assertEqual(value['metrics']['synthesis_alms_estimate'],300001)
        self.assertIsNone(value['alms_needed']);self.assertIsNone(value['alms_placed']);self.assertIsNone(value['setup_slack_ns'])
        (out/'probe.fit.rpt').write_text('forbidden fitter artifact')
        with self.assertRaisesRegex(ValueError,'forbidden fit/STA'):helper.summarize_synthesis(project)

    def test_p16_full_four_hour_is_distinct_and_cutoff_bounded(self):
        actual=json.loads((FPGA/'queue/standing-fits/tickets/s4-p16-diet-whole-full-four-hour-v1.json').read_text())
        controller=self.controller(Backend())
        topology=dict(hostname='gfn16-aws-m8i',observed_at='2026-10-01T19:00:00Z',cpus=[],slots=d.frozen_queue().HOSTS['gfn16-aws-m8i']['slots'])
        with patch.object(controller.money,'hourly',return_value=dict(schema='provider-hourly-cost-status-v1',provider='aws',status='PASS')):
            handle,helpers,archive=controller.prepare_fit(actual,'gfn16-aws-m8i','b',self.root/'actual-p16',topology,NOW)
        request=d.read(handle['request'])
        self.assertEqual(request['runtime_contract'],d.P16_FULL)
        self.assertEqual(request['project']['qsf_parameters']['P'],16)
        self.assertEqual(request['native_gate_evidence']['source_sha256'],request['project']['source_sha256'])
        self.assertEqual(handle['horizon_seconds'],14580)
        project=self.root/'p16-contract';project.mkdir()
        manifest=dict(scope='whole_core',core_parameters=dict(P=16,AW=16),allowed_stages=['syn','fit','sta'])
        (project/'manifest.json').write_text(json.dumps(manifest))
        ticket=dict(runtime_profile=d.P16_FULL['kind'],mode='full',scope='whole_core',track='S',
                    snapshot=dict(path=str(project)),source_contract=dict(structural_spec={}),native_source_gate='real-normal')
        self.assertEqual(d.runtime_contract(ticket),d.P16_FULL)
        self.assertEqual(d.P16_FULL['native_timeout_seconds'],14400)
        self.assertEqual(d.P16_FULL['outer_runtime_seconds'],14520)
        self.assertEqual(d.P16_FULL['host_hours_horizon_seconds'],14580)
        self.assertEqual(d.END.strftime('%Y-%m-%dT%H:%M'),'2026-10-02T16:00')
        ticket['runtime_profile']=d.P8_FULL['kind']
        with self.assertRaises(ValueError):d.runtime_contract(ticket)
        ticket['runtime_profile']=d.P16_FULL['kind'];ticket['mode']='synthesis_only'
        with self.assertRaises(ValueError):d.runtime_contract(ticket)
        ticket['mode']='full';ticket['source_contract']={'exemption':'synthesis_only_resource_screen'}
        with self.assertRaises(ValueError):d.runtime_contract(ticket)

    def test_actual_pre_native_failure_is_not_generic_missing_context_waiver(self):
        destination=FPGA/'queue/standing-fit-state/terminal/s4-p16-diet-whole-full-four-hour-v1'
        root=destination/'evidence';request=json.loads((root/'request.json').read_text());receipt=json.loads((destination/'receipt.json').read_text())
        proof=receipt['native_journal_proof']
        self.assertTrue(d.pre_native_rejection(root,request,proof,receipt))
        changed=deepcopy(request);changed['runtime_contract']=d.P16_FULL
        self.assertFalse(d.pre_native_rejection(root,changed,proof,receipt))
        self.assertFalse(d.pre_native_rejection(root,request,dict(proof,terminal_kind='deactivated_successfully'),receipt))
        self.assertFalse(d.pre_native_rejection(root,request,dict(proof,manager_elapsed_seconds=100),receipt))
        self.assertFalse(d.pre_native_rejection(root,request,proof,dict(receipt,findings=['missing_execution-context.json'])))
        changed=deepcopy(request);changed['project']['source_sha256'][next(iter(changed['project']['source_sha256']))]='0'*64
        with self.assertRaisesRegex(ValueError,'SHA drift'):d.pre_native_rejection(root,changed,proof,receipt)
        self.state.mkdir();journal=d.Journal(self.state,self.queue)
        journal.append('ticket','job',ticket={'path':'fixture','sha256':'0'*64})
        journal.append('intent','job',handle={'id':'job'})
        journal.append('terminal','job',outcome='native_prelaunch_failure',bundle={'receipt':'preserved'})
        journal.append('operator_retry_pre_native','job',execution_id='job-retry1')
        state=journal.current()['job']
        self.assertEqual(state['phase'],'queued');self.assertEqual(state['execution_id'],'job-retry1');self.assertNotIn('handle',state)

    def test_actual_oom_is_typed_failure_not_missing_source_waiver(self):
        dest=FPGA/'queue/standing-fit-state/terminal/s4-p16-diet-whole-full-four-hour-v1-retry1'
        root=dest/'evidence';request=json.loads((root/'request.json').read_text());receipt=json.loads((dest/'receipt.json').read_text());proof=receipt['native_journal_proof']
        self.assertEqual(d.interrupted_terminal(root,request,proof,receipt),'native_fit_failure')
        changed=dict(proof,manager_terminal_message=request['unit']+": Failed with result 'exit-code'.")
        self.assertIsNone(d.interrupted_terminal(root,request,changed,receipt))
        self.assertIsNone(d.interrupted_terminal(root,request,proof,dict(receipt,findings=receipt['findings']+['source_drift_rtl/top.sv'])))

    def test_pending_p16_resource_amendment_preserves_original_and_32g_packet(self):
        original=json.loads((FPGA/'queue/standing-fits/tickets/s4-p16-timing-whole-9000-high-effort-v1.json').read_text())
        path=self.queue/'tickets'/('p16-amendment.json');original['id']='p16-amendment';d.save(path,original)
        before=d.regular(path);controller=self.controller(Backend());controller.journal.append('ticket',original['id'],ticket=d.reference(path))
        basis=d.reference(FPGA/'results/throughput-20260929/trackS-p16-timing-v1/resource-basis.json')
        ref=controller.amend_pending(original['id'],dict(slot_shapes={'azure4':['c']},memory_gib=32,resource_basis=basis))
        self.assertEqual(d.regular(path),before);ticket=d.read(ref)
        with patch.object(d,'native_source_gate',return_value=None):controller.tick(NOW)
        self.assertFalse(any(r['event']=='blocked' for r in controller.journal.rows))
        self.assertEqual(ticket['snapshot'],original['snapshot']);self.assertEqual(ticket['settings'],original['settings'])
        topology=dict(hostname=HOST,observed_at='2026-10-01T19:00:00Z',cpus=[],slots=d.frozen_queue().HOSTS[HOST]['slots'])
        with patch.object(controller.money,'hourly',return_value=dict(schema='provider-hourly-cost-status-v1',provider='azure',status='PASS')),patch.object(d,'native_source_gate',return_value={'source_sha256':ticket['snapshot']['source_sha256']}):
            handle,helpers,archive=controller.prepare_fit(ticket,HOST,'c',self.root/'azure32',topology,NOW)
        request=d.read(handle['request']);self.assertEqual(request['memory_bytes'],32<<30);self.assertEqual(handle['memory_bytes'],32<<30)
        self.assertEqual(request['resource_basis_evidence']['reference'],basis)
        self.assertEqual(request['project']['qsf_parameters']['P'],16)
        changed=deepcopy(ticket);changed['slot_shapes']={'aws6':['a']}
        d.validate_ticket(changed,PROFILES)
        topology=dict(hostname='gfn16-aws-m8i',observed_at='2026-10-02T07:00:00Z',cpus=[],slots=d.frozen_queue().HOSTS['gfn16-aws-m8i']['slots'])
        with patch.object(controller.money,'hourly',return_value=dict(schema='provider-hourly-cost-status-v1',provider='aws',status='PASS')),patch.object(d,'native_source_gate',return_value={'source_sha256':ticket['snapshot']['source_sha256']}):
            handle,helpers,archive=controller.prepare_fit(changed,'gfn16-aws-m8i','a',self.root/'aws32',topology,NOW)
        request=d.read(handle['request'])
        self.assertEqual(request['memory_bytes'],32<<30)
        self.assertEqual(handle['memory_bytes'],32<<30)
        self.assertEqual(request['runtime_contract'],d.P16_FULL)
        self.assertEqual(request['project']['source_sha256'],ticket['snapshot']['source_sha256'])
        changed['memory_gib']=40
        with self.assertRaises(ValueError):d.validate_ticket(changed,PROFILES)
        changed['settings']['workers']=12
        d.validate_ticket(changed,PROFILES)
        topology['slots']=d.aws12_config(d.frozen_queue().HOSTS['gfn16-aws-m8i'])['slots']
        with patch.object(controller.money,'hourly',return_value=dict(schema='provider-hourly-cost-status-v1',provider='aws',status='PASS')),patch.object(d,'native_source_gate',return_value={'source_sha256':ticket['snapshot']['source_sha256']}):
            handle,helpers,archive=controller.prepare_fit(changed,'gfn16-aws-m8i','a',self.root/'aws40',topology,NOW)
        request=d.read(handle['request'])
        self.assertEqual(request['memory_bytes'],40<<30)
        self.assertEqual(request['project']['source_sha256'],ticket['snapshot']['source_sha256'])
        generated=self.root/'aws40/generated'
        self.assertEqual(json.loads((generated/'manifest.json').read_text())['compile_processors'],12)
        self.assertIn('NUM_PARALLEL_PROCESSORS 12',(generated/'probe.qsf').read_text())
        for invalid in ({'aws6':['b']},{'azure4':['a']}):
            bad=deepcopy(changed);bad['slot_shapes']=invalid
            with self.assertRaises(ValueError):d.validate_ticket(bad,PROFILES)

    def test_32g_waits_for_aggregate_headroom_and_preserves_live_24g(self):
        original=json.loads((FPGA/'queue/standing-fits/tickets/s4-p16-timing-whole-9000-high-effort-v1.json').read_text())
        original.update(id='p16-memory-fixture',slot_shapes={'azure4':['d']},memory_gib=32)
        path=self.queue/'tickets/p16-memory-fixture.json';d.save(path,original)
        backend=Backend();controller=self.controller(backend)
        for slot in ('a','b','c'):
            handle=dict(id='live-'+slot,host=HOST,slot=slot,memory_bytes=24<<30,invocation_id='a'*32,request_sha256='b'*64)
            controller.journal.append('adopt_intent',handle['id'],handle=handle)
            controller.journal.append('started',handle['id'],handle_delta={})
        with patch.object(d,'native_source_gate',return_value={'source_sha256':original['snapshot']['source_sha256']}):
            current=controller.tick(NOW)
        self.assertEqual(current['p16-memory-fixture']['phase'],'queued')
        self.assertFalse(any(c[0]=='launch' for c in backend.calls))
        self.assertEqual(current['live-a']['handle']['memory_bytes'],24<<30)

    def test_aws32_respects40g_aggregate_and_disjoint_physical_slot(self):
        for other,slot,expected in ((20,'b','queued'),(32,'b','queued'),(8,'b','started'),(8,'a','queued')):
            with self.subTest(other_gib=other,slot=slot):
                base=self.root/f'aws-{other}-{slot}';self.queue=base/'queue';self.state=base/'state'
                original=json.loads((FPGA/'queue/standing-fits/tickets/s4-p16-diet-whole-full-four-hour-v1.json').read_text())
                original.update(id='aws-memory-fixture',slot_shapes={'aws6':['a']},memory_gib=32,after=[],requires=[])
                d.save(self.queue/'tickets/aws-memory-fixture.json',original)
                backend=Backend();controller=self.controller(backend)
                controller.money.policy['priorities'].update(hold_whole_lanes=[16],allowed_whole_ids=['aws-memory-fixture'],whole_p16_blocked_hosts=['gfn16-aws-m8i'])
                handle=dict(id='live',host='gfn16-aws-m8i',slot=slot,memory_bytes=other<<30,invocation_id='a'*32,request_sha256='b'*64)
                controller.journal.append('adopt_intent','live',handle=handle)
                controller.journal.append('started','live',handle_delta={})
                with patch.object(controller.money,'recheck'),patch.object(d,'native_source_gate',return_value={'source_sha256':original['snapshot']['source_sha256']}):
                    current=controller.tick(NOW)
                self.assertEqual(current['aws-memory-fixture']['phase'],expected,controller.journal.rows[-1])
                self.assertEqual(current['live']['handle']['memory_bytes'],other<<30)

    def test_aws40_reserves_entire_existing_host(self):
        original=json.loads((FPGA/'queue/standing-fits/tickets/s4-p16-diet-whole-full-four-hour-v1.json').read_text())
        original.update(id='aws40-fixture',slot_shapes={'aws6':['a']},memory_gib=40,after=[],requires=[])
        original['settings']['workers']=12
        d.save(self.queue/'tickets/aws40-fixture.json',original)
        backend=Backend();controller=self.controller(backend)
        controller.money.policy['priorities'].update(hold_whole_lanes=[16],allowed_whole_ids=['aws40-fixture'])
        handle=dict(id='live',host='gfn16-aws-m8i',slot='b',memory_bytes=1<<30,invocation_id='a'*32,request_sha256='b'*64)
        controller.journal.append('adopt_intent','live',handle=handle);controller.journal.append('started','live',handle_delta={})
        with patch.object(controller.money,'recheck'),patch.object(d,'native_source_gate',return_value={'source_sha256':original['snapshot']['source_sha256']}):
            current=controller.tick(NOW)
            self.assertEqual(current['aws40-fixture']['phase'],'queued')
            controller.journal.append('terminal','live',outcome='native_fit_success',bundle={})
            current=controller.tick(NOW)
            self.assertEqual(current['aws40-fixture']['phase'],'started')

    def test_explicit_pre_native_retry_has_fresh_namespace_across_restart(self):
        self.submit('retry-fixture')
        backend=Backend();backend.q=d.frozen_queue();controller=self.controller(backend)
        first=controller.tick(NOW)['retry-fixture']['handle']
        controller.journal.append('terminal','retry-fixture',outcome='native_prelaunch_failure',bundle={'receipt':'original-preserved'})
        backend.verify_terminal=lambda handle,bundle:'native_prelaunch_failure'
        controller.retry_pre_native('retry-fixture')
        restarted=self.controller(backend)
        current=restarted.tick(NOW)['retry-fixture']
        self.assertEqual(current['phase'],'started')
        self.assertEqual(current['handle']['id'],'retry-fixture-retry1')
        self.assertNotEqual(current['handle']['unit'],first['unit'])
        self.assertTrue((self.state/'prepared/retry-fixture-attempt0/request.json').exists())
        self.assertTrue((self.state/'prepared/retry-fixture-retry1-attempt0/request.json').exists())
        self.controller(backend).tick(NOW)
        self.assertEqual(sum(call[0]=='launch' for call in backend.calls),2)

    def test_actual_legacy_adopt_proof_retains_unknown_claim_no_launch(self):
        q = d.frozen_queue()
        legacy_queue = {'schema':'plain-fit-queue-v1', 'fixture_only':True}
        queue_path = self.root/'legacy-queue.json'
        d.save(queue_path, legacy_queue)
        journal_dir = self.root/'legacy'; journal_dir.mkdir()
        old = q.Journal(journal_dir, d.digest(d.canonical(legacy_queue)))
        request_path = self.root/'legacy-request.json'
        request = dict(host=HOST, slot='a', unit='gfn16-existing.service', project_name='existing')
        d.save(request_path, request)
        ref = d.reference(request_path)
        handle = dict(request, id='existing', scope='whole_core', request=ref, request_sha256=ref['sha256'], invocation_id='a'*32)
        old.append('adopt', 'existing', handle=handle)
        backend = Backend(None)
        backend.observe = lambda handle:dict(state={}, invocation_id=None, request_sha256=handle['request_sha256'])
        controller = self.controller(backend)
        controller.adopt(d.reference(queue_path), d.reference(old.path), d.reference(FPGA/'tools/plain_fit_queue_v6.py'))
        self.assertEqual(controller.journal.current()['existing']['phase'], 'adopt_intent')
        self.submit('waiting')
        controller.tick(NOW)
        self.assertFalse(any(c[0] == 'launch' for c in backend.calls))
        backend.observe = lambda handle:dict(state=dict(MainPID='42', ActiveState='active'), invocation_id='a'*32, request_sha256=handle['request_sha256'])
        controller.adopt(d.reference(queue_path), d.reference(old.path), d.reference(FPGA/'tools/plain_fit_queue_v6.py'))
        controller.tick(NOW)
        self.assertEqual(len([r for r in controller.journal.rows if r['event'] == 'adopt_intent']), 1)
        self.assertFalse(any(c[0] == 'launch' for c in backend.calls))

    def test_cutoff_and_new_A_work_do_not_start(self):
        self.submit()
        backend = Backend()
        self.controller(backend).tick(d.END)
        self.assertFalse(backend.calls)
        s.submit(self.queue, 'parked-a', SOURCE, '9.500', 2, {'azure4':['b']}, 'component_probe', {'exemption':'component_sizing_probe'}, track='A', purpose='a10_pending')
        self.controller(backend).tick(d.END)
        self.assertFalse(backend.calls)

    def test_finite_job_may_finish_after_intake_cutoff(self):
        self.submit('last-minute-field')
        backend=Backend();controller=self.controller(backend)
        controller.end=d.END  # This fixture explicitly exercises the newly approved cutoff.
        with patch.object(controller.money,'recheck'):
            current=controller.tick(d.END-timedelta(seconds=1))
        self.assertEqual(current['last-minute-field']['phase'],'started')
        self.assertEqual(current['last-minute-field']['handle']['horizon_seconds'],7260)
        handle=current['last-minute-field']['handle']
        with patch.object(d,'datetime') as clock:
            clock.now.return_value=d.END
            with self.assertRaisesRegex(ValueError,'intake cutoff'):
                controller.launch_ready('last-minute-field',handle,{},d.END)

    def test_real_audit_backend_baseline_stage_delta_typed_violation_then_next(self):
        import test_audit_period_search as timing
        audit_module = load('real_audit_callback_fixture', FPGA/'tools/fit_audit_backend.py')
        real = audit_module.AuditBackend(self.root)
        parent = dict(id='p8-fixture', host=HOST, slot='c', kind='fit', unit='gfn16-p8-fixture.service', invocation_id='a'*32,
                      request_sha256='b'*64, after_collection_action=dict(kind='timing_audit_search', max_selected=8))
        parent_receipt = dict(project='/home/azureuser/gfn16-worker/p8-fixture', native_job_succeeded=True, terminal_proven=True,
                              host=HOST, unit=parent['unit'], invocation_id=parent['invocation_id'], source_request_sha256=parent['request_sha256'])
        path = self.root/'parent-terminal.json'; d.save(path, parent_receipt)
        bundle = dict(receipt=str(path), receipt_sha256=d.digest(d.regular(path)))
        calls = []
        class AuditFixture:
            active = True
            def next(self, *args): return real.next(*args)
            def prepare(self, action, directory, topology, now):
                directory.mkdir()
                config = directory/'config.json'; d.save(config, dict(fixture_only=True))
                handle = dict(id=action['id'], kind='audit', scope='whole_core', host=HOST, slot='c', unit='gfn16-'+action['id']+'.service',
                              parent_id=action['parent_id'], original_invocation=parent['invocation_id'], spec_sha256='d'*64,
                              selected_period_ns=action['selected_period_ns'])
                calls.append(('prepare', action['selected_period_ns']))
                return handle, {}, config
            def stage(self, handle, archive):
                calls.append(('stage', handle['id']))
                return dict(handle, remote_request='/fixture/request.json', request_sha256='c'*64)
            def launch(self, handle, helpers):
                calls.append(('launch', handle['request_sha256']))
                return dict(state=dict(MainPID='42', ActiveState='active'), invocation_id='e'*32, request_sha256=handle['request_sha256'])
            def observe(self, handle):
                return dict(state=dict(MainPID='42' if self.active else '0', ActiveState='active' if self.active else 'inactive'), invocation_id='e'*32, request_sha256=handle['request_sha256'])
            def collect(self, handle):
                receipt = timing.receipt()
                receipt.update(parent_receipt)
                receipt.update(schema='plain-fit-audit-terminal-collection-v1', scope='whole_core', unit=handle['unit'],
                               collector_sha256=audit_module.PINS['tools/collect_plain_fit_audit_signed_v1.py'], invocation_id='e'*32,
                               original_invocation=parent['invocation_id'], request_sha256=handle['request_sha256'], spec_sha256='d'*64,
                               status='native_timing_violation', timing_closes=False)
                p = self_root/('audit-terminal-'+handle['id']+'.json'); d.save(p, receipt)
                return dict(receipt=str(p), receipt_sha256=d.digest(d.regular(p)))
            def verify_terminal(self, *args): return real.verify_terminal(*args)
        self_root = self.root
        bridge = AuditFixture()
        backend = Backend(); backend.audits = bridge
        backend.stage = bridge.stage; backend.launch = bridge.launch
        backend.observe = bridge.observe; backend.collect = bridge.collect; backend.verify_terminal = bridge.verify_terminal
        controller = self.controller(backend)
        controller.journal.append('adopt_intent', parent['id'], handle=parent)
        controller.journal.append('terminal', parent['id'], outcome='native_fit_success', bundle=bundle)
        current = controller.tick(NOW)
        self.assertEqual(current['p8-fixture-audit0']['phase'], 'started')
        self.assertEqual(calls[:3], [('prepare', None), ('stage', 'p8-fixture-audit0'), ('launch', 'c'*64)])
        events = [r for r in controller.journal.rows if r['job'] == 'p8-fixture-audit0']
        stage = next(r for r in events if r['event'] == 'stage_complete')
        self.assertEqual(stage['handle_delta']['request_sha256'], 'c'*64)
        self.assertLess(events.index(stage), next(i for i,r in enumerate(events) if r['event'] == 'launch_attempt'))
        controller = self.controller(backend)
        controller.tick(NOW)
        self.assertEqual(sum(c[0] == 'launch' for c in calls), 1)
        bridge.active = False
        current = controller.tick(NOW)
        self.assertEqual(current['p8-fixture-audit0']['outcome'], 'audit_timing_violation')
        self.assertEqual(current['p8-fixture-audit1']['phase'], 'started')
        self.assertEqual(calls[-3], ('prepare', '11.166'))

    def test_bad_callback_does_not_kill_other_slots(self):
        class BadAudit:
            def next(self, *args): raise ValueError('corrupt audit evidence')
        self.submit('other-slot')
        backend = Backend(); backend.audits = BadAudit()
        controller = self.controller(backend)
        parent = dict(id='parent', host=HOST, slot='c', kind='fit', after_collection_action=dict(kind='timing_audit_search', max_selected=8))
        controller.journal.append('adopt_intent', 'parent', handle=parent)
        controller.journal.append('terminal', 'parent', outcome='native_fit_success', bundle={})
        current = controller.tick(NOW)
        self.assertEqual(current['other-slot']['phase'], 'started')
        self.assertTrue(any(r['event'] == 'unresolved' and r['job'] == 'parent' for r in controller.journal.rows))


if __name__ == '__main__':
    unittest.main()

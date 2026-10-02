"""Submit-time lane preparation; pure saved packets and temporary registries only."""
import copy
import json
from pathlib import Path
import tempfile
import tarfile
import types
import unittest
from unittest.mock import patch

from fpga.tools import global_queue_v1 as q
from fpga.tools import native_auto_variants_v4 as auto

INPUT=q.FPGA/'results/throughput-20260929/anext-point-base-fuzz-batch-v1/aw5-ticket.json'
SAVED=q.FPGA/'queue/variant-preparation/anext-point-base-fuzz-aw5-p3-v1/intake-1790879352370191000/variants/ticket.json'


class AllLaneTests(unittest.TestCase):
    def test_aethia_uses_existing_user_manager_not_privileged_system_manager(self):
        host=q.load_host(q.QUEUE/'hosts/aethia-light-q1.json')
        with patch.object(q,'command',return_value={}) as command:
            q.ssh(host,'systemctl show example.service',Path('/tmp'),'fixture')
            self.assertEqual(command.call_args.args[0][-1],'systemctl --user show example.service')
            q.ssh(host,'journalctl --unit=example.service',Path('/tmp'),'fixture')
            self.assertEqual(command.call_args.args[0][-1],'journalctl --user --unit=example.service')
        with tempfile.TemporaryDirectory() as temporary,patch.object(q,'QUEUE',Path(temporary)):
            (q.QUEUE/'running').mkdir()
            ticket=dict(id='fixture-aethia',resources=dict(ram_gib=4),package=dict(native_root='/worker/fixture',max_seconds=3700),dispatch=dict(unit='fixture.service'))
            with patch.object(q,'ssh',return_value={}) as remote:
                q.start_worker(ticket,host,host['lanes'][0],q.QUEUE,['/bin/true'],'/worker/fixture')
            argv=remote.call_args.args[1]
            self.assertTrue(argv.startswith('systemd-run --user '))
            self.assertNotIn('sudo',argv)
            self.assertNotIn('--property=User=',argv)
            self.assertIn('--property=AllowedCPUs=0,2',argv)
            self.assertIn('--property=MemoryMax=4294967296',argv)

    def test_wrap_end_preserves_finite_job_and_collection_margin(self):
        ticket={'packages':[{'max_seconds':10800}]}
        ready,reason=q.eligible(ticket,{}, {},now=q.WRAP_END_EPOCH-10800-15-599)
        self.assertFalse(ready)
        self.assertIn('wrap end',reason)

    def test_current_automatic_dependency_closure_matches_consumer_checker(self):
        from fpga.tools import native_azure_variant_refresh_v5 as refresh
        module=auto.module()
        for relative,pin in module.PINS.items():
            self.assertEqual(q.sha(q.FPGA/relative),pin,relative)
        self.assertEqual(module.PINS['tools/native_profile_variants_v14.py'],
                         q.CONSUMER_CONTRACT['functional_checker_sha256'])
        self.assertEqual(q.sha(Path(auto.__file__)),q.CONSUMER_CONTRACT['automatic_variants_sha256'])
        # The nested re-packager must resolve the same checker, not merely
        # accept the outer adapter's updated digest.
        nested=refresh.module()
        self.assertEqual(nested.VARIANTS_SHA,q.CONSUMER_CONTRACT['functional_checker_sha256'])
        nested.load('native_profile_variants_v14.py',nested.VARIANTS_SHA)

    def setUp(self):
        self.original=json.loads(INPUT.read_text())
        self.enriched=json.loads(SAVED.read_text())

    def test_actual_ten_closed_variants_keep_minimum_and_role(self):
        # Historical packets retain their captured tools; in-place maintained
        # staging tools cannot re-execute the old packet as a new job.
        with self.assertRaisesRegex(ValueError,'package/stager drift'):
            q.validate(self.enriched)
        self.assertEqual(q.expected_identity(self.original),q.expected_identity(self.enriched))
        self.assertEqual(len(q.packages(self.enriched)),10)
        azure=[p for p in q.packages(self.enriched) if p['profile'].startswith('azure-')]
        self.assertEqual(len(azure),8)
        self.assertEqual(len({p['profile'] for p in azure}),8)
        self.assertTrue(all(p['resources']['ram_gib']==8 for p in azure))
        self.assertTrue(all(p['runner']==q.CONSUMER_CONTRACT['azure75_runner'] for p in azure))

    def test_real_public_submit_emits_even_while_predecessor_waits(self):
        known=q.registry()
        parent=self.original['after'][0]
        predecessor=copy.deepcopy(known[parent if isinstance(parent,str) else parent['id']])
        predecessor.pop('result',None);predecessor.pop('dependency_gate',None)
        known[predecessor['id']]=predecessor
        with tempfile.TemporaryDirectory() as temporary,patch.object(q,'QUEUE',Path(temporary)):
            for state in ('pending','running','done'):(q.QUEUE/state).mkdir()
            q.atomic(q.QUEUE/'loop-state.json',dict(status='running',consumer_contract=q.CONSUMER_CONTRACT))
            with patch.object(q,'registry',return_value=known),patch.object(q,'emit_all_admitted_variants',return_value=self.enriched) as emit:
                result=q.submit(INPUT)
                self.assertEqual(result['status'],'pending');emit.assert_called_once()
                recorded=json.loads((q.QUEUE/'pending'/(result['id']+'.json')).read_text())
                self.assertEqual(len(q.packages(recorded)),10)
                self.assertEqual(recorded['after'],self.enriched['after'])
                with self.assertRaisesRegex(ValueError,'unique queue id'):q.submit(INPUT)
                self.assertEqual(emit.call_count,1)
            self.assertEqual(q.dependency_state(recorded,known)[0],False)

    def test_special_policy_and_old_consumer_cannot_be_silently_converted(self):
        special=copy.deepcopy(self.original)
        special['packages'][0]['runner']='tools/native_ordinal_package_v1.py'
        with patch.object(q,'load_host',side_effect=AssertionError('special policy must not expand')):
            self.assertEqual(q.emit_all_admitted_variants(special),special)
        with tempfile.TemporaryDirectory() as temporary,patch.object(q,'QUEUE',Path(temporary)):
            contract=dict(q.CONSUMER_CONTRACT);contract.pop('automatic_variants_sha256')
            q.atomic(q.QUEUE/'loop-state.json',dict(status='running',consumer_contract=contract))
            with self.assertRaisesRegex(ValueError,'actual running consumer registry adoption'):
                q.require_consumer_adoption(self.enriched)

    def test_smaller_existing_alias_never_bypasses_declared_minimum(self):
        module=auto.module();ticket=copy.deepcopy(self.original)
        ticket['packages'].append(dict(ticket['packages'][0],profile='azure-burst16-static01-v1',
            resources=dict(cores=2,threads=1,ram_gib=4,scratch_gib=4)))
        host=q.load_host(q.FPGA/'queue/hosts/azure-f32-q2.json')
        host['enabled']=True;host['lanes']=host['lanes'][:1]
        calls=[];loader=module.load
        def load(name):
            if name=='tools/native_azure_variant_refresh_v5.py':
                def prepare(*args):
                    calls.append(args[1]);raise ValueError('fixture stops before package generation')
                return types.SimpleNamespace(repackage_variant=prepare)
            return loader(name)
        with tempfile.TemporaryDirectory() as temporary,patch.object(module,'load',side_effect=load):
            result,receipt=module.expand_variants(ticket,[host],Path(temporary).resolve()/'variants',
                dict(path=str(INPUT),sha256=q.sha(INPUT)))
        self.assertEqual(calls,['azure-burst16-static8g01-v1'])
        self.assertEqual(result['packages'],ticket['packages'])
        self.assertEqual(len(receipt['notes']),1)

    def test_normal_ready_stamp_is_actual_acceptance_not_role_inference(self):
        known=q.registry()
        for role in ('normal','deliberate_fault',None):
            with self.subTest(role=role),tempfile.TemporaryDirectory() as temporary,patch.object(q,'QUEUE',Path(temporary)):
                for state in ('pending','running','done'):(q.QUEUE/state).mkdir()
                ticket=copy.deepcopy(self.original)
                if role:ticket['test_role']=role
                path=q.QUEUE/'input.json';q.atomic(path,ticket)
                accepted='2026-10-01T18:46:00Z'
                with patch.object(q,'registry',return_value=known),patch.object(q,'emit_all_admitted_variants',side_effect=lambda row:row),patch.object(q,'stamp',return_value=accepted):
                    result=q.submit(path)
                observed=json.loads((q.QUEUE/'pending'/(ticket['id']+'.json')).read_text())
                if role=='normal':
                    self.assertEqual(observed['normal_test_submitted_at_utc'],accepted)
                    self.assertEqual(result['normal_test_submitted_at_utc'],accepted)
                else:self.assertNotIn('normal_test_submitted_at_utc',observed)

    def test_owner_cannot_backfill_ready_event_or_change_accepted_role(self):
        with tempfile.TemporaryDirectory() as temporary,patch.object(q,'QUEUE',Path(temporary)):
            ticket=copy.deepcopy(self.original)
            ticket.update(test_role='normal',normal_test_submitted_at_utc='2026-10-01T18:00:00Z')
            path=q.QUEUE/'input.json';q.atomic(path,ticket)
            with self.assertRaisesRegex(ValueError,'never backfilled'):q.submit(path)
            self.assertFalse((q.QUEUE/'pending').exists())
            q.atomic(q.QUEUE/'pending'/(ticket['id']+'.json'),ticket)
            changed=copy.deepcopy(ticket);changed['normal_test_submitted_at_utc']='2026-10-01T18:01:00Z'
            q.atomic(path,changed)
            with self.assertRaisesRegex(ValueError,'actual accepted normal submission event'):q.update_pending(path)

    def test_readiness_snapshot_is_bound_to_actual_closed_role_not_prefix(self):
        ticket=json.loads((q.FPGA/'queue/done/anext-coldleg-normal-aw5-q1-v1.json').read_text())
        q.validate(ticket)
        with tarfile.open(q.packages(ticket)[0]['archive'],'r:gz') as archive:
            manifest=json.loads(archive.extractfile('manifest.json').read())
        for change in ('digest','source','future'):
            row=copy.deepcopy(ticket)
            if change=='digest':row['rtl_readiness']['candidate_source_sha256']='0'*64
            elif change=='source':
                name=next(iter(row['rtl_readiness']['source_snapshot']))
                row['rtl_readiness']['source_snapshot'][name]='0'*64
            else:row['rtl_readiness']['rtl_ready_at_utc']='2099-10-01T18:00:00Z'
            with self.assertRaises(ValueError):q.validate_rtl_readiness(row,manifest)

    def test_metrics_retire_prefix_groups_and_preserve_unknown_legacy_identity(self):
        legacy=[dict(id='a10-prefix-only',dispatch={}),dict(id='a10-other-design',dispatch={})]
        with tempfile.TemporaryDirectory() as temporary,patch.object(q,'QUEUE',Path(temporary)):
            with patch.object(q,'rows',side_effect=lambda state:legacy if state=='done' else []):
                result=q.metrics('2026-10-01T18:00:00Z','2026-10-01T18:30:00Z')
        self.assertEqual(result['schema'],'global-queue-transition-metrics-v2')
        self.assertIsNone(result['same_candidate_gaps'])
        self.assertIsNone(result['median_same_candidate_terminal_to_next_start_seconds'])
        self.assertEqual(result['preparation']['samples']['same_candidate_edges'],0)
        self.assertIn('prefix-based statistic retired',result['candidate_identity_basis'])

    def test_status_labels_samples_and_terminal_collection_without_freeing_claim(self):
        observed='2026-10-01T19:10:00Z';now='2026-10-01T19:11:00Z'
        host=dict(name='fixture',lanes=[dict(id='pair',cpus=[0,1])])
        ticket=dict(id='example',dispatch=dict(host='fixture',lane='pair',phase='observed',
            invocation='original',reserved=observed,observed_at=observed,
            properties=dict(MainPID='123',SubState='running')))
        for pid in ('123','0'):
            ticket['dispatch']['properties']['MainPID']=pid
            with tempfile.TemporaryDirectory() as temporary,patch.object(q,'QUEUE',Path(temporary)):
                with patch.object(q,'rows',side_effect=lambda state:[ticket] if state=='running' else []),patch.object(q.time,'time',return_value=q.epoch(now)),patch.object(q,'stamp',return_value=now):
                    q.status([host],{},[],0)
                report=(q.QUEUE/'STATUS.md').read_text()
            self.assertIn('not instantaneous CPU utilization',report)
            self.assertIn(observed+' / 60s',report)
            self.assertIn('last observed running' if pid=='123' else 'collection pending',report)
            self.assertEqual(ticket['dispatch']['invocation'],'original')

    def test_hourly_cache_replaces_per_launch_cost_calls_but_blocks_unknown(self):
        host=q.load_host(q.FPGA/'queue/hosts/gcp-c4d-q1.json')
        with patch.object(q,'cached_provider_cost',return_value=dict(status='PASS',checked_at_utc='2026-10-01T20:00:00Z')) as cache,patch.object(q,'hourly_provider',side_effect=AssertionError('no launch-time refresh')),patch.object(q,'command',side_effect=AssertionError('no per-launch provider arithmetic')):
            result=q.budget(host,10815,Path('/tmp'))
            self.assertEqual(result['outer_runtime_plus_stop_seconds'],10815)
            cache.assert_called_once_with('gcp')
        with patch.object(q,'cached_provider_cost',return_value=dict(status='UNRESOLVED',reason='unknown provider')):
            with self.assertRaisesRegex(ValueError,'hourly cost UNRESOLVED'):
                q.budget(host,3715,Path('/tmp'))


if __name__=='__main__':unittest.main()

"""Finite queue rejection and archive collection tests; never run HDL/native ELF."""
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from fpga.tools import native_test_queue_v1 as queue
from fpga.tools import native_test_queue_prepare_v1 as prepare
from fpga.tools import native_source_gate_v1 as policy
from fpga.tools import build_identity_v1 as identity

ROOT = Path(__file__).resolve().parents[1]


class NativeTestQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.stage = Path(cls.temporary.name)/'stage'
        with redirect_stdout(io.StringIO()): prepare.prepare(cls.stage, ROOT)
        cls.bundle = cls.stage/'bundle'
        cls.ticket = json.loads((cls.bundle/'queue.json').read_text())

    @classmethod
    def tearDownClass(cls): cls.temporary.cleanup()

    def test_known_qualified_component_has_runnable_bounded_ticket(self):
        profile, jobs = queue.validate_plan(self.ticket, self.bundle, policy, identity)
        self.assertEqual(profile['cpus'], [0, 1]); self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0][0]['handler'], 'qualified-executable-v1')
        self.assertEqual(jobs[0][0]['build_key'], identity.build_identity(jobs[0][1], profile)['build_key'])
        self.assertFalse(self.ticket['promotion_allowed'])

    def test_rejects_unbounded_host_handler_or_resource_expansion(self):
        changes = (
            lambda t: t.update(host='aws'), lambda t: t.update(max_seconds=14401),
            lambda t: t.update(failure_policy='continue'), lambda t: t.update(promotion_allowed=True),
            lambda t: t.update(jobs=[]), lambda t: t.update(jobs=t['jobs']*17),
            lambda t: t['resources'].update(max_active_jobs=2), lambda t: t['resources'].update(memory_bytes=8*queue.GIB),
            lambda t: t['jobs'][0].update(handler='shell'), lambda t: t['jobs'][0].update(command='rm -rf /'),
            lambda t: t['jobs'][0].update(max_seconds=100000), lambda t: t['jobs'][0].update(output='../existing'),
        )
        for change in changes:
            ticket = copy.deepcopy(self.ticket); change(ticket)
            with self.assertRaises((ValueError, KeyError)): queue.validate_plan(ticket, self.bundle, policy, identity)

    def test_dependency_cycles_forward_edges_and_implicit_promotion_rejected(self):
        for dependency in (
            dict(job_id='missing', required_status='needs_independent_review', layer='execution_and_collection'),
            dict(job_id=self.ticket['jobs'][0]['id'], required_status='needs_independent_review', layer='execution_and_collection'),
            dict(job_id='missing', required_status='passed', layer='independent_review'),
        ):
            ticket = copy.deepcopy(self.ticket); ticket['jobs'][0]['dependencies'] = [dependency]
            with self.assertRaisesRegex(ValueError, 'ordered acyclic'): queue.validate_plan(ticket, self.bundle, policy, identity)

    def test_typed_field_stderr_requires_exact_class_and_numeric_context(self):
        for kind in ('FIELD_PHYSICAL_DATA_MISMATCH', 'FIELD_SLOT_MISMATCH'):
            contract = dict(name='corpus', argv=['{exe}', '{root}/vectors.txt', '--expect-negative', kind], expected_returncode=0,
                            expected_stdout='FIELD_SQUARE_NEGATIVE_PASS kind='+kind+'\n')
            self.assertTrue(queue.stderr_matches(contract, kind+' tick=123 port=7\n'))
            self.assertTrue(queue.stderr_matches(contract, kind+' tick=0 port=0'))
            for text in ('', kind+' tick=x port=7\n', kind+' tick=123\n', 'OTHER tick=123 port=7\n',
                         kind+' tick=123 port=7\nextra\n', 'prefix '+kind+' tick=123 port=7\n'):
                self.assertFalse(queue.stderr_matches(contract, text))
            wrong = dict(contract, expected_stdout='PASS\n')
            self.assertFalse(queue.stderr_matches(wrong, kind+' tick=123 port=7\n'))

    def test_missing_independent_review_and_foreign_cache_identity_rejected(self):
        for change in (
            lambda j: j.update(review_required=False), lambda j: j.update(review_gates=[]),
            lambda j: j.update(build_key='0'*64), lambda j: j.update(run_key='0'*64),
            lambda j: j['reuse'].update(report_sha256='0'*64),
            lambda j: j['review_gates'][0].update(expected_status='PASS_anything'),
            lambda j: j['review_gates'][0]['bindings'].update(executable_sha256='0'*64),
        ):
            ticket = copy.deepcopy(self.ticket); change(ticket['jobs'][0])
            with self.assertRaises(ValueError): queue.validate_plan(ticket, self.bundle, policy, identity)

    def test_persistent_atomic_claim_never_retries_or_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); key = 'a'*64
            path = queue.claim(root, key, {'status':'claimed', 'output':'one'})
            before = path.read_bytes()
            with self.assertRaises(FileExistsError): queue.claim(root, key, {'status':'new', 'output':'two'})
            self.assertEqual(path.read_bytes(), before)
            path.write_text('{"status":"failed_or_incomplete"}')
            with self.assertRaises(FileExistsError): queue.claim(root, key, {'status':'retry'})

    def test_real_worker_archive_is_collected_hash_verified_and_unpromoted(self):
        directory = ROOT/prepare.DONOR
        manifest = json.loads((directory/'approved-manifest.json').read_text())
        profile = policy.PROFILES[manifest['host']]
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder).resolve()/'collected'
            result = queue.collect_evidence(directory, out, manifest, queue.sha(directory/'approved-manifest.json'), profile, 'source-gate-v1')
            self.assertEqual(result['status'], 'needs_independent_review'); self.assertFalse(result['promotion_allowed'])
            self.assertEqual(len(result['files']), 15)
            self.assertTrue(all(queue.sha(out/name) == digest for name,digest in result['files'].items()))
            with self.assertRaisesRegex(ValueError, 'fresh collection'):
                queue.collect_evidence(directory, out, manifest, queue.sha(directory/'approved-manifest.json'), profile, 'source-gate-v1')

    def test_failed_or_forged_command_evidence_cannot_collect(self):
        directory = ROOT/prepare.DONOR; raw = (directory/'report.json').read_text(); report = json.loads(raw)
        manifest = json.loads((directory/'approved-manifest.json').read_text()); parse = json.loads
        for change in (
            lambda d: d.update(status='failed_native_commands'), lambda d: d['steps'][-1]['command'].append('--different'),
            lambda d: d['steps'][2].update(returncode=1), lambda d: d.update(executable_sha256='0'*64),
            lambda d: d['tool_sha256'].update({'/evil/tool':'a'*64}),
        ):
            altered = copy.deepcopy(report); change(altered)
            with patch.object(queue.json, 'loads', side_effect=lambda x,*a,**kw: copy.deepcopy(altered) if x == raw else parse(x,*a,**kw)):
                with self.assertRaises(ValueError):
                    queue.verify_worker(directory, manifest, queue.sha(directory/'approved-manifest.json'), policy.PROFILES[manifest['host']], 'source-gate-v1')

    def test_off_host_never_starts_any_process_or_writes_native_output(self):
        path = self.bundle/'queue.json'
        with patch.object(queue.socket, 'gethostname', return_value='mac'), patch.object(queue.subprocess, 'Popen', side_effect=AssertionError('must not execute')):
            with self.assertRaisesRegex(ValueError, 'native approved host'): queue.execute(path, queue.sha(path))

    def test_pause_is_remote_explicit_and_does_not_claim_mac_visibility(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); ticket = {'pause_policy':{'remote_flag':str(root/'PAUSE'), 'host_flag':str(root/'HOST-PAUSE')}}
            queue.pause_check(ticket)
            for name in ('PAUSE', 'HOST-PAUSE'):
                path = root/name; path.write_text('pause')
                with self.assertRaises(queue.QueuePaused): queue.pause_check(ticket)
                path.unlink()
        self.assertEqual(self.ticket['pause_policy']['local_gate_owner'], 'main_dispatcher_before_dispatch')

    def test_failed_artifact_collection_preserves_raw_logs_and_cannot_promote(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); worker = root/'worker'; worker.mkdir(); launch = root/'launch'; launch.mkdir()
            (worker/'build.log').write_text('failed build\n'); (launch/'launcher.stderr.log').write_text('native failure\n')
            report = dict(status='failed_native_commands', artifacts={'build.log':queue.sha(worker/'build.log'), '../escape':'0'*64})
            (worker/'report.json').write_text(json.dumps(report))
            result = queue.collect_failed_evidence(worker, root/'collected', launch)
            self.assertEqual(result['status'], 'failed_or_incomplete'); self.assertFalse(result['promotion_allowed'])
            self.assertEqual(set(result['files']), {'report.json', 'worker/build.log', 'launcher.stderr.log'})
            self.assertEqual(len(result['collection_errors']), 1)
            self.assertTrue((worker/'build.log').exists())

    def test_bounded_process_records_logs_and_terminates_on_guard_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            step, error = queue.checked_process([sys.executable, '-B', '-c', 'print("queue-helper-ok")'],
                root, dict(os.environ), root, 'normal', 10, lambda:None)
            self.assertIsNone(error); self.assertEqual(step['returncode'], 0)
            self.assertEqual((root/'normal.log').read_text(), 'queue-helper-ok\n')
            def stop(): raise ValueError('deliberate bounded guard failure')
            step, error = queue.checked_process([sys.executable, '-B', '-c', 'import time; time.sleep(10)'],
                root, dict(os.environ), root, 'stopped', 10, stop)
            self.assertIsInstance(error, ValueError); self.assertNotEqual(step['returncode'], 0)

    def test_redirected_parent_paths_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); outside = root/'outside'; outside.mkdir()
            for name in ('results', 'collected', 'failed-collected', 'launch-job'):
                redirected = root/name; redirected.symlink_to(outside, target_is_directory=True)
                with self.assertRaisesRegex(ValueError, 'canonical'): queue.fresh_path(redirected/'new-output')
                with self.assertRaisesRegex(ValueError, 'canonical'): queue.canonical_path(redirected)
            self.assertEqual(list(outside.iterdir()), [])
            queue.fresh_path(root/'uncreated-parent'/'new-output')
            source = ROOT/prepare.DONOR; manifest = json.loads((source/'approved-manifest.json').read_text())
            with self.assertRaisesRegex(ValueError, 'canonical'):
                queue.collect_evidence(source, root/'collected'/'new-output', manifest, queue.sha(source/'approved-manifest.json'),
                                       policy.PROFILES[manifest['host']], 'source-gate-v1')
            self.assertEqual(list(outside.iterdir()), [])

    def test_frozen_policy_is_unchanged_and_no_remote_or_shell_escape(self):
        self.assertEqual(queue.sha(ROOT/'tools/native_source_gate_v1.py'), queue.POLICY_SHA)
        source = (ROOT/'tools/native_test_queue_v1.py').read_text()
        for forbidden in ('shell=True', 'subprocess.run(', 'os.system(', 'eval(', 'rmtree(', "['ssh'", "['sudo'", "['systemctl'"):
            self.assertNotIn(forbidden, source)
        self.assertIn('os.O_EXCL', source); self.assertIn("report['status'] = 'needs_independent_review'", source)


if __name__ == '__main__': unittest.main()

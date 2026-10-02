"""Independent dependency checks with real retained native outputs, no dispatch."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fpga.tools import global_queue_v1 as q


class Dependencies(unittest.TestCase):
    def setUp(self):
        self.original_queue = q.QUEUE
        self.parent = json.loads((q.QUEUE / 'done/a10-aw5-form-batch-v1.json').read_text())
        self.parent.pop('dependency_gate', None)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.queue = Path(tmp.name).resolve()
        switch = patch.object(q, 'QUEUE', self.queue)
        switch.start()
        self.addCleanup(switch.stop)
        self.child = dict(id='independent-next', after=[self.parent['id']])
        self.known = {self.parent['id']: self.parent}
        q.bind_dependencies(self.child, self.known)

    def test_actual_expected_nonzero_releases_without_owner_receipt(self):
        self.assertFalse(q.dependency_state(self.child, self.known)[0])
        q.gate_result(self.parent)
        receipt = json.loads(Path(self.parent['dependency_gate']['path']).read_text())
        self.assertEqual([s['actual_returncode'] for s in receipt['steps']], [1])
        self.assertFalse(receipt['promotion_allowed'])
        self.assertEqual(q.dependency_state(self.child, self.known), (True, 'eligible'))

    def test_repeat_gate_is_identical_and_does_not_need_review(self):
        q.gate_result(self.parent)
        first = copy.deepcopy(self.parent['dependency_gate'])
        q.gate_result(self.parent)
        self.assertEqual(self.parent['dependency_gate'], first)
        self.assertEqual(self.parent['result']['status'], 'needs_independent_review')
        self.assertTrue(q.dependency_state(self.child, self.known)[0])

    def test_missing_and_unknown_observation_do_not_release(self):
        self.assertIn('missing dependency:', q.dependency_state(self.child, {})[1])
        self.parent.pop('result')
        ready, reason = q.dependency_state(self.child, self.known)
        self.assertFalse(ready)
        self.assertIn('waiting native contract PASS:', reason)

    def test_failed_parent_blocks_child_not_independent_work(self):
        self.parent['result'] = dict(status='terminal_failure')
        self.assertIn('failed dependency:', q.dependency_state(self.child, self.known)[1])
        self.assertEqual(q.dependency_state(dict(id='unrelated'), self.known), (True, 'eligible'))

    def test_source_mismatch_and_receipt_tampering_do_not_release(self):
        q.gate_result(self.parent)
        original = self.child['after'][0]['functional_sha256']
        self.child['after'][0]['functional_sha256'] = '0' * 64
        self.assertIn('invalid dependency evidence:', q.dependency_state(self.child, self.known)[1])
        self.child['after'][0]['functional_sha256'] = original
        Path(self.parent['dependency_gate']['path']).write_text('{}\n')
        self.assertIn('invalid dependency evidence:', q.dependency_state(self.child, self.known)[1])

    def test_missing_self_duplicate_and_cycle_bindings_reject(self):
        for after in (['missing'], ['independent-next'], [self.parent['id']] * 2):
            with self.assertRaises(ValueError):
                q.bind_dependencies(dict(id='independent-next', after=after), self.known)
        with self.assertRaisesRegex(ValueError, 'cyclic'):
            q.validate_graph({'a': dict(after=['b']), 'b': dict(after=['a'])})
        with self.assertRaisesRegex(ValueError, 'missing'):
            q.validate_graph({'a': dict(after=['missing'])})

    def test_failure_propagates_without_cancelling_running_or_independent_jobs(self):
        self.parent['result'] = dict(status='terminal_failure')
        child = dict(id='z-child', packages=self.parent['packages'], after=[self.parent['id']])
        q.bind_dependencies(child, self.known)
        known = dict(self.known, **{child['id']: child})
        grandchild = dict(id='a-grandchild', packages=self.parent['packages'], after=[child['id']])
        q.bind_dependencies(grandchild, known)
        q.atomic(self.queue / 'done' / (self.parent['id'] + '.json'), self.parent)
        for ticket in (child, grandchild, dict(id='independent')):
            q.atomic(self.queue / 'pending' / (ticket['id'] + '.json'), ticket)
        running = dict(child, id='already-running', dispatch=dict(invocation='retained'))
        q.atomic(self.queue / 'running/already-running.json', running)
        errors = []
        q.reconcile_dependencies(errors)
        for name in ('z-child', 'a-grandchild'):
            terminal = json.loads((self.queue / 'done' / (name + '.json')).read_text())
            self.assertEqual(terminal['result']['status'], 'cancelled_unstarted_dependency_failure')
            self.assertTrue(terminal['result']['evidence_preserved'])
            self.assertFalse((self.queue / 'pending' / (name + '.json')).exists())
        self.assertTrue((self.queue / 'pending/independent.json').exists())
        self.assertEqual(json.loads((self.queue / 'running/already-running.json').read_text()), running)

    def test_all_prerequisites_must_pass_before_release(self):
        q.gate_result(self.parent)
        unknown = dict(self.parent, id='unknown-observation')
        unknown.pop('result')
        unknown.pop('dependency_gate')
        known = dict(self.known, **{unknown['id']: unknown})
        child = dict(id='two-inputs', after=[self.parent['id'], unknown['id']])
        q.bind_dependencies(child, known)
        ready, reason = q.dependency_state(child, known)
        self.assertFalse(ready)
        self.assertIn('waiting native contract PASS: unknown-observation', reason)


if __name__ == '__main__':
    unittest.main()

"""Real public wide-chain intake in an isolated queue, never a native claim."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]


def exercise(input_suffix='q3-v1'):
    source = ROOT / 'tools/global_queue_v1.py'
    q = types.ModuleType('_wide_public_intake')
    q.__file__ = str(source)
    exec(compile(source.read_text(), str(source), 'exec'), q.__dict__)
    inputs = [ROOT / f'queue/inputs/t5b-wide-threads{n}-{input_suffix}.json' for n in (2, 4, 8)]
    input_values = [json.loads(p.read_text()) for p in inputs]
    ids = {value['id'] for value in input_values}
    preserved_predecessors = {value['supersedes_unstarted'] for value in input_values
                             if value.get('supersedes_unstarted')}
    results = []
    with tempfile.TemporaryDirectory() as temporary:
        q.QUEUE = Path(temporary)
        # Simulate the independently required adopted live consumer only in
        # this isolated queue. Never publish a live loop-state or claim.
        (q.QUEUE / 'loop-state.json').write_text(json.dumps(dict(
            status='running', consumer_contract=q.CONSUMER_CONTRACT)))
        for state in ('pending', 'running', 'done'):
            (q.QUEUE / state).mkdir()
            for path in (ROOT / 'queue' / state).glob('*.json'):
                if path.stem in ids:
                    continue  # Replay original unclaimed intake, not a live retry.
                value = json.loads(path.read_text())
                # Later legitimate recovery rows have the same source/config
                # as this historical replay. Exclude that family, except exact
                # cancelled ancestors needed by supersedes_unstarted checks.
                if (any(p.get('runner') == q.CONSUMER_CONTRACT['fixed_wide_runner']
                        for p in q.packages(value))
                        and value['id'] not in preserved_predecessors):
                    continue
                gate = value.get('dependency_gate', {})
                if gate.get('path'):
                    old = Path(gate['path'])
                    new = q.QUEUE / 'evidence' / value['id'] / old.name
                    new.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(old, new)
                    gate['path'] = str(new)  # Exact receipt bytes and hash unchanged.
                (q.QUEUE / state / path.name).write_text(json.dumps(value))
        for index, path in enumerate(inputs):
            result = q.submit(path)
            ticket = json.loads((q.QUEUE / 'pending' / (result['id'] + '.json')).read_text())
            state = q.dependency_state(ticket)
            if index == 0:
                if state != (True, 'eligible'):
                    raise AssertionError(state)
            elif state != (False, 'waiting native contract PASS: ' + results[-1]['id']):
                raise AssertionError(state)
            try:
                q.submit(path)
            except ValueError as error:
                if 'unique queue id' not in str(error):
                    raise
            else:
                raise AssertionError('duplicate accepted')
            results.append(dict(id=result['id'], input_sha256=q.sha(path),
                result=result, dependency=list(state),
                functional_sha256=q.functional_identity(ticket['package']),
                placement=ticket['package']['placement']))
    return dict(status='PASS_actual_public_wide_chain_intake_metadata_only',
        queue_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        results=results, live_queue_unchanged=True, native_launch=False,
        isolated_receipt_relocations_preserved_hashes=True)


class WidePublicIntakeTests(unittest.TestCase):
    def test_actual_chain_submit_dependencies_and_duplicate_refusal(self):
        self.assertEqual(len(exercise()['results']), 3)

    def test_accounting_only_fresh_chain_uses_same_public_contract(self):
        self.assertEqual(len(exercise('q3-fresh-v1')['results']), 3)

    def test_public_submit_refuses_missing_stale_or_stopped_consumer_before_write(self):
        source = ROOT / 'tools/global_queue_v1.py'
        q = types.ModuleType('_wide_stale_public_intake')
        q.__file__ = str(source)
        exec(compile(source.read_text(), str(source), 'exec'), q.__dict__)
        path = ROOT / 'queue/inputs/t5b-wide-threads2-q3-fresh-v1.json'
        for state in (None, dict(status='running', consumer_contract={}),
                      dict(status='stopped_control_or_bound', consumer_contract=q.CONSUMER_CONTRACT)):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as temporary:
                q.QUEUE = Path(temporary)
                if state is not None:
                    (q.QUEUE / 'loop-state.json').write_text(json.dumps(state))
                with self.assertRaisesRegex(ValueError, 'actual running consumer registry adoption'):
                    q.submit(path)
                self.assertFalse((q.QUEUE / 'pending').exists())


if __name__ == '__main__':
    unittest.main()

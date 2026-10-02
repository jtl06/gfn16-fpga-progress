"""Real ordinal public intake, isolated registry only; no transport/native run."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch

FPGA = Path(__file__).resolve().parents[1]
INPUTS = FPGA / 'results/throughput-20260929/s4-ordinal-complete-batch-v1'
IDS = ('s4-aw5-p16-ordinal-positive-q1-v1', 's4-aw5-p16-ordinal-negative-q1-v1',
       's4-aw5-p8-ordinal-negative-q1-v1')


def module():
    source = FPGA / 'tools/global_queue_v1.py'
    value = types.ModuleType('_ordinal_public_queue')
    value.__file__ = str(source)
    exec(compile(source.read_text(), str(source), 'exec'), value.__dict__)
    return value


class OrdinalQueueTests(unittest.TestCase):
    def test_actual_batch_public_intake_binds_current_machine_dependencies(self):
        q = module()
        with tempfile.TemporaryDirectory() as directory:
            q.QUEUE = Path(directory)
            for state in ('pending', 'running', 'done'):
                (q.QUEUE / state).mkdir()
                for source_path in (FPGA / 'queue' / state).glob('*.json'):
                    value=json.loads(source_path.read_text())
                    if any(p.get('runner')=='tools/native_ordinal_package_v1.py' for p in q.packages(value)):
                        continue  # Replay original unclaimed intake, not later outcomes.
                    gate=value.get('dependency_gate',{})
                    if gate.get('path'):
                        old=Path(gate['path'])
                        new=q.QUEUE/'evidence'/value['id']/old.name
                        new.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copyfile(old,new)
                        self.assertEqual(q.sha(new),gate['sha256'])
                        gate['path']=str(new)
                    q.atomic(q.QUEUE/state/source_path.name,value)
            q.atomic(q.QUEUE / 'loop-state.json', dict(status='running', consumer_contract=q.CONSUMER_CONTRACT))
            for index, identifier in enumerate(IDS):
                path = INPUTS / (identifier + '.json')
                result = q.submit(path)
                self.assertEqual(result['id'], identifier)
                ticket = json.loads((q.QUEUE / 'pending' / (identifier + '.json')).read_text())
                state = q.dependency_state(ticket)
                if index == 1:
                    self.assertEqual(state, (False, 'waiting native contract PASS: ' + IDS[0]))
                    self.assertEqual(ticket['after'][0]['functional_sha256'], q.expected_identity(
                        json.loads((q.QUEUE / 'pending' / (IDS[0] + '.json')).read_text())))
                else:
                    self.assertEqual(state, (True, 'eligible'))
                with self.assertRaisesRegex(ValueError, 'unique queue id'):
                    q.submit(path)

    def test_new_family_requires_actual_adopted_consumer_before_public_write(self):
        q = module()
        path = INPUTS / (IDS[0] + '.json')
        for state in (None, dict(status='running', consumer_contract={}),
                      dict(status='stopped_control_or_bound', consumer_contract=q.CONSUMER_CONTRACT)):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as directory:
                q.QUEUE = Path(directory)
                if state:
                    q.atomic(q.QUEUE / 'loop-state.json', state)
                with self.assertRaisesRegex(ValueError, 'actual running consumer registry adoption'):
                    q.submit(path)
                self.assertFalse((q.QUEUE / 'pending').exists())

    def test_exact_global_resource_and_outer_contract(self):
        q = module()
        ticket = json.loads((INPUTS / (IDS[0] + '.json')).read_text())
        q.validate(ticket)
        for key, value in [('cores', 4), ('threads', 2), ('ram_gib', 4)]:
            changed = copy.deepcopy(ticket)
            changed['resources'][key] = value
            with self.assertRaises(ValueError):
                q.validate(changed)
        changed = copy.deepcopy(ticket)
        for package in q.packages(changed):
            package['max_seconds'] = 10800
        with self.assertRaises(ValueError):
            q.validate(changed)

    def test_no_generic_serial_auto_conversion(self):
        q = module()
        ticket = json.loads((INPUTS / (IDS[0] + '.json')).read_text())
        with tempfile.TemporaryDirectory() as directory:
            q.QUEUE = Path(directory)
            q.atomic(q.QUEUE / 'pending' / (ticket['id'] + '.json'), ticket)
            errors = []
            with patch.object(q, 'automatic_gcp_accounting'), patch.object(q, 'dependency_state', return_value=(True, 'eligible')):
                with patch.object(q, 'role_host_compatible', side_effect=AssertionError('must skip generic serial auto')):
                    q.automatic_variants([], errors)
            self.assertEqual(errors, [])
            self.assertEqual(json.loads((q.QUEUE / 'pending' / (ticket['id'] + '.json')).read_text()), ticket)


if __name__ == '__main__':
    unittest.main()

"""Infrastructure disposition metadata only; no native or numeric execution."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('_soak_infra', ROOT / 'tools/prepare_core27_t5b_infra_successors_v1.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def ticket():
    return dict(id='soak-t5b-aw16-chunk-03-q3-v1', owner='soak-chunks',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        dispatch=dict(host='gfn16-azure-sim-f32', invocation='abc'),
        source_host_inadmission=dict(host='gfn16-azure-sim-f32', invocation='abc', promotion_allowed=False),
        result=dict(status='terminal_infrastructure_failure',
            classification='verified_source_host_inadmission_cancelled_not_arithmetic',
            one_fresh_original_host_successor_permitted=True, automatic_resource_retry=False,
            properties=dict(MainPID='0', ControlGroup='', InvocationID='abc', ExecMainExitTimestamp='terminal')))


class InfrastructureSuccessors(unittest.TestCase):
    def test_explicit_terminal_host_failure(self):
        MODULE.validate_original(ticket(), 3)

    def test_never_retry_math_failure_or_uncertain_process(self):
        for key, value in [('status', 'failed_arithmetic'), ('classification', 'arithmetic_failure'),
                           ('one_fresh_original_host_successor_permitted', False), ('automatic_resource_retry', True)]:
            altered = ticket()
            altered['result'][key] = value
            with self.assertRaises(ValueError):
                MODULE.validate_original(altered, 3)
        for key, value in [('MainPID', '12'), ('ControlGroup', '/live'), ('InvocationID', 'other'),
                           ('ExecMainExitTimestamp', '')]:
            altered = ticket()
            altered['result']['properties'][key] = value
            with self.assertRaises(ValueError):
                MODULE.validate_original(altered, 3)

    def test_identity_and_single_successor(self):
        for key, value in [('id', 'soak-t5b-aw16-chunk-02-q3-v1'), ('owner', 'other'),
                           ('tool_identity', 'other'), ('infra_retry_of', 'old')]:
            altered = ticket()
            altered[key] = value
            with self.assertRaises(ValueError):
                MODULE.validate_original(altered, 3)
        for index in [0, 2, 8, 9, True]:
            with self.assertRaises(ValueError):
                MODULE.validate_original(ticket(), index)

    def test_wrong_host_evidence_must_match(self):
        for key, value in [('host', 'gfn16-pilot-c4d'), ('invocation', 'other'), ('promotion_allowed', True)]:
            altered = deepcopy(ticket())
            altered['source_host_inadmission'][key] = value
            with self.assertRaises(ValueError):
                MODULE.validate_original(altered, 3)


if __name__ == '__main__':
    unittest.main()

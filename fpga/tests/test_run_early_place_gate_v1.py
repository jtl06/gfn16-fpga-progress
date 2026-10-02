"""Source-level stage ancestry/immutability controls, not native qualification."""
import importlib.util
from pathlib import Path
import unittest

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('early_gate', FPGA/'tools/run_early_place_gate_v1.py')
gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
base = gate.load('qualified_base', FPGA/'tools/quartus_prefit_native_v3.py')


def stage_log():
    rows = ['Info: Version 26.1.0 Build 110 SC Pro Edition']
    for stage in gate.STAGES[:-1]:
        rows += ['PLACEMENT_STAGE\tSTART\t'+stage, 'PLACEMENT_STAGE\tCOMPLETE\t'+stage]
    rows += ['PLACEMENT_STAGE\tCOMPLETE\tstopped_before_route']
    return '\n'.join(rows)+'\n'


class StageTests(unittest.TestCase):
    def test_exact_native_stage_log_shape(self):
        gate.validate_stage_log(base, stage_log(), 0)

    def test_missing_reordered_routing_error_or_timeout_blocks(self):
        log = stage_log()
        cases = [(log.replace('PLACEMENT_STAGE\tCOMPLETE\tplanned\n', ''), 0),
            (log.replace('START\tplanned', 'START\tplaced'), 0),
            (log+'PLACEMENT_STAGE\tCOMPLETE\trouted\n', 0),
            (log+'Error (1): native error\n', 0), (log, 124),
            (log.replace('Version 26.1.0', 'Version 25.3.0'), 0)]
        for bad, rc in cases:
            with self.subTest(rc=rc, tail=bad[-80:]), self.assertRaises(ValueError):
                gate.validate_stage_log(base, bad, rc)

    def test_frozen_helper_closure_and_no_unsupported_stage(self):
        for name, pin in gate.PINS.items():
            directory = 'synthesis' if name.endswith('.tcl') else 'tools'
            self.assertEqual(base.sha((FPGA/directory/name).read_bytes()), pin)
        script = (FPGA/'synthesis/staged_placement_qualification_v1.tcl').read_text()
        self.assertIn('execute_module -tool fit -args "--plan"', script)
        self.assertIn('execute_module -tool fit -args "--place"', script)
        self.assertNotIn('--route', script)
        self.assertNotIn('--early_place', script)
        self.assertNotIn('execute_flow -compile', script)
        self.assertIn('catch {project_close}', script)


if __name__ == '__main__':
    unittest.main()

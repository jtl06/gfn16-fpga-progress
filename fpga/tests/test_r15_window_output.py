import copy
import json
import unittest

from fpga.host.r15_window_output import validate
from fpga.host.r15_window_recipe import recipe


class WindowOutput(unittest.TestCase):
    def fixture(self):
        return dict(schema='r15-software-canonical-window-normal-v1',
            status='software_windows_pass', tests=23,
            cases=[dict(base=b, n=256, global_operations=(b**256).bit_length(),
                jobs=37, raw_cold_words=10656, canonical_words=9472,
                host_GL_checks=10, independent_pow_equal=True,
                global_ordinal_equal=True, no_padded_descriptors=True) for b in (599, 600)],
            runtime=dict(engine='gmpy2', version='fixture', gmp='fixture'), platform='Linux',
            sample_plan=dict(operations=1911814, width=65536, jobs=30, last=11270,
                             generations_below_256=True, integer_only=True),
            controls=dict(chosen_engine_corrupt_A_GL_rejected=True,
                two_rollback_checkpoints_preserved=True, common_reset_drain_fullreload_required=True,
                global_ordinals_rewound=True), elapsed_seconds=1.0,
            scope=dict(software_GMP_windows=True, software_endpoint_model=True, actual_core=False,
                actual_transport=False, arbitrary_in_job_checkpoints=False, full_N_numeric=False,
                measured_full_PRP=False, board=False, inherited_compute_timing=False, promotion=False))

    def line(self, value):
        return 'R15_WINDOW_RESULT ' + json.dumps(value)

    def test_output_case_scope_control_and_global_count_mutations(self):
        good = self.fixture()
        self.assertEqual(validate(self.line(good)), good)
        bads = []
        for key in ('actual_core', 'actual_transport', 'board', 'full_N_numeric', 'promotion'):
            bad = copy.deepcopy(good);bad['scope'][key] = True;bads.append(bad)
        bad = copy.deepcopy(good);bad['sample_plan']['generations_below_256'] = 1;bads.append(bad)
        bad = copy.deepcopy(good);bad['cases'][0]['global_operations'] -= 1;bads.append(bad)
        bad = copy.deepcopy(good);bad['controls']['global_ordinals_rewound'] = False;bads.append(bad)
        bad = copy.deepcopy(good);bad['elapsed_seconds'] = 105;bads.append(bad)
        for bad in bads:
            with self.assertRaises(ValueError):
                validate(self.line(bad))
        with self.assertRaises(ValueError):
            validate(self.line(good)+'\n'+self.line(good))

    def test_closure_and_integer_only_plan(self):
        value = recipe()
        self.assertEqual(len(value['source_sha256']), 27)
        self.assertFalse(value['scope']['HDL'])
        self.assertFalse(value['scope']['full_N_numeric'])
        self.assertEqual(value['max_command_seconds'], 105)


if __name__ == '__main__':
    unittest.main()

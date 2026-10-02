"""Artifact/log rejection tests only; no oracle arithmetic, GMP or native run."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('_serial1000_consumer', ROOT/'tools/consume_core27_t5b_serial1000_v1.py')
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


class Serial1000Consumption(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ticket_file = ROOT/'results/throughput-20260929/core27-t5b-soak-serial1000-native-v1/terminal-queue.json'
        cls.ticket = json.loads(cls.ticket_file.read_text())
        cls.report = json.loads((Path(cls.ticket['result']['evidence'])/'output/native/report.json').read_text())
        manifest = json.loads((Path(cls.ticket['package']['archive']).parent/'manifest.json').read_text())
        source = Path(cls.ticket['package']['archive']).parent/'capture/source/fpga'
        cls.oracle = json.loads((source/manifest['steps'][0]['validator']['assets']['oracle']).read_text())
        cls.stdout = (Path(cls.ticket['result']['evidence'])/'output/native/soak-normal.log').read_text()
        cls.lines = cls.stdout.splitlines()
        cls.rows = [(line.split(' ', 1)[0], json.loads(line.split(' ', 1)[1])) for line in cls.lines]
        cls.steps = [row for name, row in cls.rows if name == 'SOAK_STEP']
        cls.parser = staticmethod(C.frozen_log_parser())
        cls.parsed = cls.parser(cls.stdout, '', 0, {'negative': 'none'}, cls.oracle)

    def test_actual_retained_artifact_consumption(self):
        result = C.consume(self.ticket_file)
        self.assertEqual(result['replay']['model_steps'], 1000)
        self.assertEqual(result['replay']['total_readback_words'], 720896)
        self.assertEqual(result['replay']['total_cycles'], 28838848)
        self.assertEqual(result['replay']['warm_cache_hits'], 999)
        self.assertTrue(result['both_chunked_and_serial_uninterrupted_native_gates_passed'])
        self.assertFalse(result['promotion_allowed'])
        self.assertFalse(result['metrics']['isolated_model_peak_rss_measured'])
        self.assertTrue(result['separate_threaded_result_not_consumed'])

    def test_terminal_cap_and_invocation_negatives(self):
        props = self.ticket['result']['properties']
        for key, value in dict(Result='failed', ExecMainStatus='1', MainPID='9', ControlGroup='/live',
            InvocationID='wrong', AllowedCPUs='2-3', CPUQuotaPerSecUSec='1s', MemoryMax='4294967296',
            MemorySwapMax='1', RuntimeMaxUSec='1h', TimeoutStopUSec='16s', ExecMainExitTimestamp='').items():
            with self.subTest(key=key), self.assertRaises(ValueError):
                C.verify_terminal({**props, key: value}, self.report)

    def test_worker_shape_negatives(self):
        props = self.ticket['result']['properties']
        cases = [('host', 'wrong')]
        for key, value in dict(affinity=[2, 3], physical_cores=[[0, 0], [0, 0]],
            cpu_max=['100000', '100000'], memory_max_bytes=4294967296, swap_max_bytes=1).items():
            cases.append(('limits.'+key, value))
        for key in ('command_seconds', 'ancillary_command_seconds', 'overall_seconds', 'outer_seconds',
                    'stop_grace_seconds', 'lock_wait_seconds', 'memory_bytes'):
            cases.append(('bounds.'+key, self.report['bounds'][key]+1))
        cases.append(('bounds.outer_seconds', True))
        for key, value in cases:
            changed = copy.deepcopy(self.report)
            target = changed
            parts = key.split('.')
            for part in parts[:-1]:
                target = target[part]
            target[parts[-1]] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                C.verify_terminal(props, changed)

    def test_native_validation_binding_negatives(self):
        original = self.report['validations']['soak-normal']
        cases = dict(case_id='wrong', segment='chunk-00', operations=999, doubles=487,
            readbacks=10, cycles=28838847, evidence_class='checkpoint_chunk_arithmetic_coverage',
            continuous_chain_log_contract=False, checkpoint_residue_sha256={}, lineage='promoted-crtmont',
            oracle_sha256='0'*64, parent_manifest_sha256='0'*64,
            uninterrupted_1000_square_rtl=False, independent_gmpy2_boundary_replay=False,
            native_qualification_allowed=False)
        for key, value in cases.items():
            with self.subTest(key=key), self.assertRaises(ValueError):
                C.verify_worker_validation({**original, key: value}, self.parsed, original['oracle_sha256'])
        for key, value in dict(status='unknown', files=20, package_version='2.2.1',
                              runtime_manifest_sha256='0'*64, python_sha256='0'*64).items():
            changed = copy.deepcopy(original)
            changed['auxiliary_reference_runtime'][key] = value
            with self.subTest(runtime=key), self.assertRaises(ValueError):
                C.verify_worker_validation(changed, self.parsed, original['oracle_sha256'])

    def test_phase_cache_and_type_negatives(self):
        for index, key, value in [(0, 'cycles', 28826), (99, 'cycles', 41674),
            (1, 'profile_loads', 1), (1, 'profile_hits', 0), (500, 'crt', 4112),
            (998, 'step', 1000), (0, 'profile_loads', True)]:
            changed = copy.deepcopy(self.steps)
            changed[index][key] = value
            with self.subTest(index=index, key=key), self.assertRaises(ValueError):
                C.verify_phases(changed)
        with self.assertRaises(ValueError):
            C.verify_phases(self.steps[:-1])

    def rejected_log(self, lines):
        with self.assertRaises(ValueError):
            self.parser('\n'.join(lines)+'\n', '', 0, {'negative': 'none'}, self.oracle)

    def test_actual_readback_boundary_negatives(self):
        indices = [i for i, (name, _) in enumerate(self.rows) if name == 'SOAK_CHECK']
        for index in indices:
            lines = list(self.lines)
            row = copy.deepcopy(self.rows[index][1])
            row['digits'][0] += 1
            lines[index] = 'SOAK_CHECK '+json.dumps(row, separators=(',', ':'))
            with self.subTest(step=row['step']):
                self.rejected_log(lines)

    def test_missing_extra_reloaded_and_wrong_bit_logs(self):
        self.rejected_log(self.lines[1:])
        self.rejected_log(self.lines+[self.lines[-1]])
        step_index = next(i for i, (name, _) in enumerate(self.rows) if name == 'SOAK_STEP')
        row = copy.deepcopy(self.rows[step_index][1])
        row['bit'] = 1-row['bit']
        lines = list(self.lines)
        lines[step_index] = 'SOAK_STEP '+json.dumps(row)
        self.rejected_log(lines)
        for key, value in dict(resets=2, loaded_digits=131072, cold=2, warm=998, operations=999).items():
            row = {**self.rows[-1][1], key: value}
            with self.subTest(footer=key):
                self.rejected_log(self.lines[:-1]+['SOAK_PASS '+json.dumps(row)])

    def test_no_gmp_or_reference_engine_import(self):
        C.no_gmp()
        self.assertNotIn('gmpy2', sys.modules)
        self.assertFalse(any(name.startswith('gmpy2.') for name in sys.modules))


if __name__ == '__main__':
    unittest.main()

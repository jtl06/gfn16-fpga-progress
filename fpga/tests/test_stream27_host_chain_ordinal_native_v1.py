import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from fpga.reference import stream27_host_chain_ordinal_native_v1 as candidate


class CompleteOrdinalSource(unittest.TestCase):
    def test_negative_delta_preserves_entire_complete_loop(self):
        # Compare against the actual generated v4 source, including its cold
        # completion qualification. These are source checks, never execution.
        path = candidate.ROOT / 'results/throughput-20260929/s4-aw5-p16-ordinal-host-native-v4/inputs/fpga/rtl/tb/stream27_host_chain_v1.cpp'
        original = path.read_text()
        changed = candidate.negative_source(original)
        begin = 'if(ordinal){reset(d);Program p{};'
        end = '        std::cout<<ORDINAL_LABEL'
        old_loop = original.split(begin, 1)[1].split(end, 1)[0]
        new_loop = changed.split(begin, 1)[1].split('        need(context.threads()', 1)[0]
        self.assertEqual(old_loop, new_loop)
        self.assertIn('p.bits.resize(65540)', new_loop)
        self.assertIn('chain_run(d,p,false,c);long_compare(d,p,c);', new_loop)

    def test_one_complete_step_per_role_and_exact_RTL_reuse(self):
        with tempfile.TemporaryDirectory(prefix='s4-ordinal-source-') as folder:
            roots = {}
            for negative in (False, True):
                root = Path(folder) / ('negative' if negative else 'positive')
                result = candidate.prepare(root, p=16, negative=negative)
                m = json.loads((root / 'manifest.json').read_text())
                self.assertEqual(len(m['steps']), 1)
                self.assertEqual(result['complete_operation_count'], 65540)
                self.assertFalse(result['runner_policy_changed'])
                self.assertFalse(result['queued'])
                roots[negative] = m
            rtl = lambda m: {path: pin for path, pin in m['sources'].items() if path.startswith('rtl/') and path.endswith('.sv')}
            self.assertEqual(rtl(roots[False]), rtl(roots[True]))
            self.assertEqual(roots[True]['steps'][0]['expected_returncode'], 1)
            self.assertEqual(roots[True]['steps'][0]['expected_stderr'],
                'S4_LONG_ORDINAL_TYPED expected=65541 actual=65540\n')

    def test_positive_cpp_is_byte_identical_to_retained_failure(self):
        with tempfile.TemporaryDirectory(prefix='s4-ordinal-positive-') as folder:
            root = Path(folder) / 'positive'
            result = candidate.prepare(root, p=16)
            old = candidate.ROOT / 'results/throughput-20260929/s4-aw5-p16-ordinal-host-native-v4/inputs/fpga/rtl/tb/stream27_host_chain_v1.cpp'
            self.assertEqual(result['cpp_sha256'], hashlib.sha256(old.read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()

"""Small/reference/source/typed-only tests: no HDL/ELF/full-N arithmetic."""
import unittest
from fpga.reference import stream27_host_chain_full_native_v1 as native


class FullHostTests(unittest.TestCase):
    def test_small_independent_ntt_crt_integer(self):
        proof = native.small_proof()
        self.assertEqual(proof['cases'], 12)
        self.assertEqual(proof['serial_whole_checks'], 36)
        self.assertFalse(proof['full_N_numeric_locally_performed'])

    def test_terminal_carry_sign_wrap_special(self):
        for n in (32, 256):
            for base in (2, 1000000000):
                a = 2*n*(base-1)**2
                for value in (-a, -a//3, 0, a//3, a):
                    values = [value]*n
                    self.assertEqual(native.small_serial(values, base), native.small_whole(values, base))
                for values in ([-1]+[0]*(n-1), [0]*(n-1)+[base]):
                    self.assertEqual(native.small_serial(values, base), [-1]+[0]*(n-1))

    def test_full_numeric_guard(self):
        class FullSize:
            def __len__(self): return 65536
            def __iter__(self): raise AssertionError('Full-N iteration forbidden')
        for call in (native.small_coefficients, lambda v: native.small_serial(v, 2),
                     lambda v: native.small_whole(v, 2)):
            with self.assertRaisesRegex(ValueError, 'SMALL_REFERENCE_ONLY'): call(FullSize())

    def test_source_contract_and_counts(self):
        native.verify()
        self.assertEqual(native.counts(), dict(jobs=2, operations=9, feed_descriptors=7,
            true_final_rows=16384, paired_reads=131072, copied_words=131072, partial_reads=1,
            canonical_cycles=786432, image_copy_cycles=131078, candidate_cycles=1083886,
            fifo_peak=4, full_exchanges=3, backpressure_edges=49955))
        cpp = (native.ROOT/native.CPP).read_text(); header = (native.ROOT/native.REFERENCE).read_text()
        for text in ('s4_full_reference::self_check()', 'word(d.t5b_read_data)',
                     'S4_FULL_HOST_DENSE_ORDINARY_CASE', 'S4_FULL_HOST_COLD_QUALIFIED_COMPLETION',
                     'S4_FULL_HOST_TRUE_LAST_ONLY', 'S4_FULL_HOST_FINALIZATION_EDGE_COST'):
            self.assertIn(text, cpp)
        self.assertLess(cpp.index('actual==expected[address]&&old==expected[address]'),
                        cpp.index('int32_t wrong=expected[address]^1'))
        self.assertEqual(header.count('#include "stream27_shared_reference_ntt_v1.h"'), 3)
        self.assertIn('c.size()<=256', header)
        self.assertNotIn('boost', header.lower().replace('no boost', ''))

    def test_strict_typed_positive_and_negative(self):
        config = dict(aw=16, p=8, mode='normal')
        footer = native.footer_prefix()+'260000\n'
        result = native.validate(footer, '', 0, config, {})
        self.assertEqual(result['measured_t5b_wait_edges'], 260000)
        for key, value in native.counts().items():
            with self.assertRaises(ValueError):
                native.validate(footer.replace(f'{key}={value}', f'{key}={value+1}', 1), '', 0, config, {})
        mutants = [footer+'extra\n', '\n'+footer, footer.replace('p=8', 'p=16'),
                   footer.replace('aw=16', 'aw=8'), footer.replace('260000', '0260000'),
                   footer.replace('260000', '0'), footer.replace('260000', str(9*(20*native.N+100000)+1)),
                   footer.rstrip('\n'), footer.replace('\n', '\r\n')]
        for stdout in mutants:
            with self.assertRaises(ValueError): native.validate(stdout, '', 0, config, {})
        for stderr, rc in [('incidental\n', 0), ('', 1), ('', True)]:
            with self.assertRaises(ValueError): native.validate(footer, stderr, rc, config, {})
        config['mode'] = 'oracle'; native.validate('', native.NEGATIVE, 1, config, {})
        for stdout, stderr, rc in [(footer, native.NEGATIVE, 1), ('', native.NEGATIVE, 0),
                                   ('', native.NEGATIVE.replace('P8', 'P16'), 1), ('', native.NEGATIVE+'extra\n', 1)]:
            with self.assertRaises(ValueError): native.validate(stdout, stderr, rc, config, {})
        for bad in [dict(config, aw=8), dict(config, p=16), dict(config, aw=True), dict(config, unexpected=1)]:
            with self.assertRaises(ValueError): native.validate('', native.NEGATIVE, 1, bad, {})


if __name__ == '__main__': unittest.main()

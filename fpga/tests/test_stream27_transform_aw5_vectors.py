"""Source-only independent polynomial oracle and calendar preparation checks."""
import unittest

from fpga.reference.stream27_transform_aw5_vectors import (
    prepare, polynomial_oracle, input_rows, pattern, Calendar, FIRST_OUTPUT,
)
from fpga.reference.stream_ntt_schedule import transform
from fpga.reference.stream_ntt_model import bit_reverse


class TinyTransformPreparation(unittest.TestCase):
    def test_direct_polynomial_oracle_against_frozen_small_math(self):
        for inverse in (False, True):
            for serial in range(8):
                words = pattern(serial)
                reference = transform(32, 8, inverse=inverse, values=words)['output_values']
                if inverse:
                    reference = [value * 32 % 104857601 for value in reference]
                    expected = [tuple(reference[bit_reverse(lane, 3) * 4 + row] for lane in range(8))
                                for row in range(4)]
                else:
                    expected = [tuple(reference[row * 8 + lane] for lane in range(8)) for row in range(4)]
                self.assertEqual(polynomial_oracle(words, inverse), expected)
                self.assertEqual(len(input_rows(words, inverse)), 4)

    def test_normal_calendar_exact_output_and_terminal_edges(self):
        for inverse in (False, True):
            calendar = Calendar(inverse).segment((0, 4))
            rows = [list(map(int, line.split())) for line in calendar.text().splitlines()[1:]]
            # First row is reset, shifting observer list index by one.
            self.assertEqual([i - 1 for i, row in enumerate(rows) if row[15]],
                             list(range(FIRST_OUTPUT, FIRST_OUTPUT + 8)))
            self.assertEqual([i - 1 for i, row in enumerate(rows) if row[28]],
                             list(range(FIRST_OUTPUT + 1, FIRST_OUTPUT + 9)))
            self.assertEqual([i - 1 for i, row in enumerate(rows) if row[16]], [34, 38])

    def test_live_generation_and_enabled_cancel_between_output_and_commit(self):
        for kwargs in ({'cancel': 35}, {'disable': 35}):
            rows = [list(map(int, line.split())) for line in Calendar(False).segment((0,), **kwargs).text().splitlines()[1:]]
            self.assertEqual(rows[35][15:19], [1, 1, 1, 0])  # physical tick34
            self.assertEqual(rows[36][15:19], [1, 0, 0, 0])  # physical tick35 remains occupied
            self.assertFalse(rows[36][28])  # no stale tick34 commit

    def test_case_shapes_and_explicit_completion_exclusion(self):
        result = prepare()
        self.assertEqual(result['gate_class'], 'tiny_complete_transform_only_not_complete_field')
        self.assertFalse(result['native_run_performed'] or result['full_N_numeric_NTT_run_performed'])
        for direction, (text, metadata) in result['vectors'].items():
            rows = text.splitlines()[1:]
            self.assertEqual(metadata['events'], 4248)
            self.assertEqual(metadata['before_checks'], 2 * len(rows))
            self.assertTrue(all(len(row.split()) == 39 for row in rows))
            self.assertEqual(text.splitlines()[0], f'TRAW5 {direction} 4248')


if __name__ == '__main__':
    unittest.main()

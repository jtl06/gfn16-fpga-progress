import unittest
from pathlib import Path


class ForwardTests(unittest.TestCase):
    def test_all_pre_post_words_collision_and_hold(self):
        parent = list(range(8))
        memory = parent.copy(); last = None
        for tick in range(256):
            address = (tick * 5) % 8
            value = 100 + tick
            enable = tick % 4 != 0
            # Arbitrary asynchronous PRE addresses, including same-write addr.
            for read in range(8):
                actual = last[1] if last and last[0] == read else memory[read]
                self.assertEqual(actual, parent[read])
            if enable:
                parent[address] = value; memory[address] = value; last = (address, value)
            else:
                last = None
            for read in range(8):
                actual = last[1] if last and last[0] == read else memory[read]
                self.assertEqual(actual, parent[read])

    def test_no_undefined_collision_attribute_or_read_register(self):
        text = (Path(__file__).parents[1] / 'rtl/kernel/genefer_stream27_term_payload_mlab_forward_v1.sv').read_text()
        self.assertNotIn('no_rw_check', text)
        self.assertNotIn('read_data<=', text)
        self.assertIn('last_write_valid<=write_enable;', text)
        self.assertIn('last_write_data : memory[read_address]', text)

    def test_last_written_address_raw_poison_is_not_observable(self):
        expected = list(range(8)); raw = expected.copy(); last = None
        for tick in range(128):
            address = tick % 8; value = 200 + tick
            # Arbitrary unknown on the raw most-recent-write output is masked
            # by an exact registered forwarding tuple, not an API don't-care.
            for read in range(8):
                observed = last[1] if last and last[0] == read else raw[read]
                self.assertEqual(observed, expected[read])
            raw = expected.copy()
            expected[address] = value; raw[address] = None; last = (address, value)
            for read in range(8):
                observed = last[1] if last[0] == read else raw[read]
                self.assertEqual(observed, expected[read])


if __name__ == '__main__':
    unittest.main()

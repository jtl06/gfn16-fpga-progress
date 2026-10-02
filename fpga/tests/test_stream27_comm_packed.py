import random
import unittest
from collections import deque
from reference import stream27_comm_packed_bind as candidate
from reference import stream27_shared_field_flags as fields
from reference import stream27_comm_packed_native as native


class PackedTests(unittest.TestCase):
    def test_controller_byte_identity(self):
        old = (candidate.ROOT / candidate.PARENT).read_text()
        new = (candidate.ROOT / candidate.LEAF).read_text()
        self.assertEqual(candidate.control_projection(old), candidate.control_projection(new))

    def test_bind_zero_and_inverse(self):
        parent = fields.prepare(256, 16, 0, mode='warm', corr_serial_bfs=2,
                                comm_stage_shared_mlab=1, mont_factored=1)
        self.assertEqual(candidate.bind(parent, enabled=0), parent)
        bound = candidate.bind(parent)
        self.assertEqual(bound['geometry'], parent['geometry'])
        self.assertEqual(bound['parameters'], parent['parameters'])
        self.assertNotIn(candidate.OLD + '.sv', bound['files'])
        for name, text in parent['files'].items():
            if name != candidate.OLD + '.sv':
                self.assertEqual(bound['files'][name].replace(candidate.NEW, candidate.OLD), text)
        self.assertEqual(bound['comm_delay_packed']['identifier_occurrences'], 8)

    def test_wide_vs_independent_rings(self):
        rng = random.Random(0x27D16)
        for pairs in (4, 8):
            for value_w, tag_w in ((29, 10), (31, 27), (28, 9)):
                for depth in (1, 2, 4, 8, 16, 32, 64):
                    mask = (1 << value_w) - 1
                    words = deque([0] * depth)
                    lanes = [deque([0] * depth) for _ in range(pairs)]
                    tags = deque([0] * depth)
                    for edge in range(700):
                        tag = rng.getrandbits(tag_w)
                        data = [rng.getrandbits(value_w) for _ in range(pairs)]
                        packed = tag << (pairs * value_w)
                        for lane, value in enumerate(data):
                            packed |= value << (lane * value_w)
                        head = words[0]
                        self.assertEqual(head >> (pairs * value_w), tags[0])
                        for lane in range(pairs):
                            self.assertEqual((head >> (lane * value_w)) & mask, lanes[lane][0])
                        if edge % 113 == 0:
                            words = deque([0] * depth)
                            lanes = [deque([0] * depth) for _ in range(pairs)]
                            tags = deque([0] * depth)
                        elif rng.randrange(5):
                            words.popleft(); words.append(packed)
                            tags.popleft(); tags.append(tag)
                            for lane in range(pairs):
                                lanes[lane].popleft(); lanes[lane].append(data[lane])

    def test_normal_wrapper_exact_parent_and_candidate(self):
        top = native.top_source()
        self.assertEqual(top.count(candidate.NEW + ' #('), 16)
        self.assertEqual(top.count(candidate.OLD + ' #('), 16)
        self.assertIn('module ' + native.TOP + ' (', top)
        self.assertNotIn('always', top)
        self.assertNotIn('genefer_stream27_mdc_commutator_sm1_registered_v1', top)

    def test_fault_normal_include_closed(self):
        cpp = native.fault_source()
        self.assertIn('#include "comm_packed_normal.cpp"', cpp)
        self.assertNotIn('shared_comm_normal_v1.cpp', cpp)
        self.assertIn('COMM_PACKED_FAULT_PASS', cpp)


if __name__ == '__main__':
    unittest.main()

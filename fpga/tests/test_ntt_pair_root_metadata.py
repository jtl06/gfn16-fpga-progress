from pathlib import Path
import hashlib
import unittest

from reference.ntt_pair_root_metadata import direct_metadata, root_event, schedule_source


class RootMetadataTests(unittest.TestCase):
    def test_explicit_events_match_direct_metadata(self):
        for width in (1, 4, 8, 16):
            limit = 1 << width
            counts = {1, limit, *range(2, min(limit, 16) + 1)}
            counts.update(g for g in (31, 127, 128, 511, 512, 513, 4095) if g <= limit)
            for groups in sorted(counts):
                observed = []
                for tick in range(2 * groups + 13):
                    expected = root_event(tick, groups)
                    if expected is not None:
                        self.assertEqual(direct_metadata(tick, width), expected)
                        observed.append(expected)
                self.assertEqual(len(observed), 2 * groups)
                self.assertEqual(set(observed), {(g, k) for g in range(groups) for k in (0, 1)})

    def test_invalid_metadata_is_not_an_event(self):
        self.assertIsNone(root_event(1, 1))
        self.assertEqual(direct_metadata(1, 4), (13, 1))
        self.assertIsNone(root_event(7, 1, busy=False))
        self.assertEqual(root_event(7, 1), (0, 1))

    def test_wrong_offset_or_parity_has_a_witness(self):
        for wrong in (lambda t: (((t - 5) >> 1) & 15, t & 1),
                      lambda t: direct_metadata(t, 4)[::-1]):
            self.assertTrue(any(wrong(t) != root_event(t, 8)
                                for t in range(29) if root_event(t, 8) is not None))

    def test_delta_preserves_all_nonmetadata_statements(self):
        path = Path(__file__).resolve().parents[1] / 'rtl/kernel/genefer_ntt_pair_schedule.sv'
        original = path.read_text()
        candidate = schedule_source(original)
        self.assertEqual(candidate, path.with_name('genefer_ntt_pair_schedule_metadata.sv').read_text())
        self.assertIn('root_read=read_a || read_b;', candidate)
        self.assertEqual(candidate.split('        issue=issue_a || issue_b;', 1)[1],
                         original.split('        issue=issue_a || issue_b;', 1)[1])
        self.assertNotIn('root_second=read_b;', candidate)
        self.assertIn('root_second=tick[0];', candidate)
        with self.assertRaises(ValueError):
            schedule_source(original.replace("TW'(7)", "TW'(5)", 1))

    def test_bench_is_only_a_module_rename(self):
        root = Path(__file__).resolve().parents[1] / 'rtl/tb'
        original = (root / 'ntt_pair_schedule.cpp').read_text()
        self.assertEqual(hashlib.sha256(original.encode()).hexdigest(),
                         'c3c9668400b19135a398cfe0786d14036aa14c0b095ee6506db16abb0e7e0a84')
        self.assertEqual(original.replace('Vgenefer_ntt_pair_schedule', 'Vgenefer_ntt_pair_schedule_metadata'),
                         (root / 'ntt_pair_schedule_metadata.cpp').read_text())


if __name__ == '__main__':
    unittest.main()

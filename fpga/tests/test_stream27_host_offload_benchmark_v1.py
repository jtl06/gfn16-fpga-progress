"""Pure safety/metadata checks. Never run the full benchmark locally."""
from unittest import mock
import unittest

from reference import stream27_host_offload_benchmark_v1 as bench


class BenchmarkEnvelopeTests(unittest.TestCase):
    def test_no_coordinator_or_other_host_execution(self):
        for platform, host in (('darwin', 'aethia'), ('linux', 'wrong'), ('linux', 'gfn16-pilot-c4d')):
            with mock.patch.object(bench.sys, 'platform', platform), mock.patch.object(bench.socket, 'gethostname', return_value=host):
                with self.assertRaisesRegex(ValueError, 'AETHIA_ONLY'):
                    bench.run()

    def test_nonfinite_repetition_selection_refused_before_image(self):
        with mock.patch.object(bench.sys, 'platform', 'linux'), mock.patch.object(bench.socket, 'gethostname', return_value='aethia'):
            for count in (0, 6, True, 1.0, '3'):
                with self.assertRaisesRegex(ValueError, 'REPETITIONS'):
                    bench.run(repetitions=count)

    def test_report_spread_not_single_time_assumption(self):
        self.assertEqual(bench.summarize([0.3, 0.1, 0.2]),
                         dict(samples_seconds=[0.3, 0.1, 0.2], minimum_seconds=0.1,
                              median_seconds=0.2, maximum_seconds=0.3))
        self.assertTrue(all((bench.ROOT / source).is_file() for source in bench.SOURCES))


if __name__ == '__main__':
    unittest.main()

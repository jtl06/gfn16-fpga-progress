"""Pure diagnostic fixtures; synthetic numbers are never measured results."""
import copy
import json
import unittest

from reference import stream27_host_offload_benchmark_output_v1 as output


def fixture():
    pins = {'reference/file' + str(i) + '.py': str(i) * 64 for i in range(7)}
    r = dict(status='PASS_host_conversion_measurement_only', host='aethia', platform='linux',
             sources=pins, n=65536, p=16, base=604832956, repetitions=3,
             input_residue_words=196608, final_digit_words=65536, final_boundary_words=32,
             max_self_rss_kib=1024, output_sha256='a' * 64,
             native_core_equivalence=False, promotion_allowed=False,
             measured_backend_seconds=None, transport_seconds=None, prp_wall_seconds=None)
    for key in output.PHASES:
        r[key] = dict(samples_seconds=[0.1, 0.2, 0.3], minimum_seconds=0.1,
                      median_seconds=0.2, maximum_seconds=0.3)
    return r, dict(repetitions=3, source_sha256=pins)


class TimingOutputTests(unittest.TestCase):
    def test_exact_fixture(self):
        r, c = fixture()
        self.assertEqual(output.validate(json.dumps(r), '', 0, c, {})['status'], 'PASS_expected_contracts')

    def test_false_scope_and_pin_claims_refused(self):
        for key, value in [('native_core_equivalence', True), ('promotion_allowed', True),
                           ('measured_backend_seconds', 0.4), ('transport_seconds', 0),
                           ('host', 'wrong'), ('n', True), ('sources', {})]:
            r, c = fixture(); r[key] = value
            with self.assertRaises(ValueError):
                output.validate(json.dumps(r), '', 0, c, {})

    def test_bad_times_wrong_sample_count_and_nonzero_refused(self):
        for value in (float('nan'), float('inf'), -1, True, 61):
            r, c = fixture(); r['cold_conversion_wall']['samples_seconds'][0] = value
            with self.assertRaises(ValueError):
                output.validate(json.dumps(r), '', 0, c, {})
        r, c = fixture(); r['profile_wall']['median_seconds'] = 0.4
        with self.assertRaises(ValueError):
            output.validate(json.dumps(r), '', 0, c, {})
        with self.assertRaises(ValueError):
            output.validate(json.dumps(fixture()[0]), '', 1, fixture()[1], {})


if __name__ == '__main__':
    unittest.main()

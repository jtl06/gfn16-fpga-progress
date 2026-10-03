import copy
import json
import unittest
from fpga.reference import stream27_context_storage_combo_registerederror_native as normal
from fpga.reference import stream27_context_storage_combo_registerederror_long_native as pilot
from fpga.reference import stream27_context_storage_combo_registerederror_continuous as long


class RegisteredErrorLongTests(unittest.TestCase):
    def test_owned_source_and_runtime_configuration(self):
        manifest, files = pilot.role(100, 1)
        donor = json.loads((pilot.DONOR_BASE / 'full-normal/manifest.json').read_bytes())
        self.assertEqual(manifest['build']['sv_sources'], donor['build']['sv_sources'])
        for name in manifest['build']['sv_sources']:
            self.assertEqual(manifest['sources'][name], donor['sources'][name])
        normal.runtime_before_model(files[pilot.CPP].decode())
        self.assertIn('image_copy_cycles,ctx)==N+4', files[pilot.CPP].decode())
        self.assertEqual(pilot.config(100, 1)['publication_fence_edges'], 1)

    def test_count_header_only_compiled_delta(self):
        manifest, files = pilot.role(100, 1)
        header = long.header(files[pilot.HEADER])
        self.assertIn('COUNT=1000,INTERVAL=8459', header.decode())
        self.assertEqual([row[:100] for row in long.bits()], pilot.bits(100))
        self.assertEqual(long.config(), pilot.config(1000, 1))

    def test_strict_new_publication_validator(self):
        launches = [[204 + k*8459 for k in range(100)], [4433 + k*8459 for k in range(100)]]
        warm = [row[-1]+12558 for row in launches]
        done = normal.publication(warm, 4096, 65536, 1)
        value = dict(aw=16, p=16, contexts=2, bases=pilot.BASES, count_per_context=100,
                     squares=200, descriptors=198, doubles=pilot.config()['doubles'], reads=262144,
                     signed96=True, independent_reference=True, initial_resets=1,
                     initial_load_words=131072, interval=8459, peer_live_reads=65536, model_threads=1,
                     launches=launches, joint_cycles=done[-1]+65536, overlap_edges=1,
                     done_edges=done, warm_edges=warm, setup_edges=[99,199],
                     reference_seconds=2.0, model_seconds=8.0, seconds=10.0)
        self.assertEqual(pilot.validate('R84_C2_THREAD100_PASS '+json.dumps(value)+'\n', '', 0,
                                      pilot.config(), {})['status'], 'PASS_expected_contracts')
        stale = copy.deepcopy(value)
        stale['done_edges'] = normal.publication(warm, 4096, 65536, 0)
        stale['joint_cycles'] = stale['done_edges'][-1]+65536
        with self.assertRaises(ValueError):
            pilot.validate('R84_C2_THREAD100_PASS '+json.dumps(stale)+'\n', '', 0, pilot.config(), {})


if __name__ == '__main__':
    unittest.main()

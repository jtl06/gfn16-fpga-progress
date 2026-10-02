"""Source-only two-thread role tests, without GMP/model/numeric execution."""
import copy
import json
from pathlib import Path
import unittest

from fpga.reference import core27_t5b_soak_thread_pilot_v1 as p
from fpga.tools import native_threaded_class_v1 as runner


class SoakThreadRoleTests(unittest.TestCase):
    def value(self):
        return json.loads((p.ROOT/p.ROLE/'cross-runtime-manifest.json').read_text())

    def test_only_macro_runtime_probe_and_nonexecuting_metadata_change(self):
        serial = self.value()
        original = copy.deepcopy(serial)
        two = p.successor(serial)
        self.assertEqual(serial, original)
        self.assertEqual(two['sources'], serial['sources'])
        self.assertEqual(two['steps'], serial['steps'])
        self.assertEqual(two['build']['sv_sources'], serial['build']['sv_sources'])
        self.assertEqual(two['build']['cpp_source'], serial['build']['cpp_source'])
        self.assertEqual(two['build']['cflags'], serial['build']['cflags']+['-DGFN16_RUNTIME_THREADS=2'])
        self.assertEqual(runner.validate_threaded(two), 2)
        self.assertEqual(two['thread_pilot']['operations'], 100)
        self.assertFalse(two['thread_pilot']['long1000_admission'])

    def test_changed_core_bench_validator_or_geometry_refused(self):
        serial = self.value()
        for key in (p.CORE, p.BENCH, p.HEADER):
            bad = copy.deepcopy(serial)
            bad['sources'][key] = '0'*64
            with self.assertRaises(ValueError): p.successor(bad)
        bad = copy.deepcopy(serial)
        bad['steps'][0]['validator']['source']='reference/unreviewed.py'
        with self.assertRaises(ValueError): p.successor(bad)
        bad = copy.deepcopy(serial)
        bad['build']['parameters']['AW']=5
        with self.assertRaises(ValueError): p.successor(bad)

    def test_runtime_override_and_untyped_probe_refused(self):
        serial = self.value()
        serial['build']['cflags'].append('-DGFN16_RUNTIME_THREADS=8')
        with self.assertRaisesRegex(ValueError, 'override'): p.successor(serial)
        serial = self.value()
        serial['probe']['expected_json']['expected_threads']=True
        with self.assertRaisesRegex(ValueError, 'typed'): p.successor(serial)


if __name__ == '__main__':
    unittest.main()

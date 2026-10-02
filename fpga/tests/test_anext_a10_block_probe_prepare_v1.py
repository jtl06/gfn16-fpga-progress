import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fpga.reference import anext_a10_block_probe_prepare_v1 as prep


class BlockProbePreparationTests(unittest.TestCase):
    def test_exact_source_and_real_consumer(self):
        pins = prep.source_guard()
        self.assertEqual(pins[prep.source.TARGET], '2d5f4ce2259b689535aa26dffbd9398512bda2ec588a68f76d83e5da30a17c1f')
        sv = (prep.ROOT / prep.SV).read_text()
        self.assertIn('consumed_valid<=block_read_valid;', sv)
        self.assertIn('consumed_words<=block_read_words;', sv)
        self.assertIn('.LANES(64)', sv)
        cpp = (prep.ROOT / prep.CPP).read_text()
        for fault in ('A10_BLOCK_E1_METADATA', 'A10_BLOCK_ATOMIC_ERROR',
                      'A10_BLOCK_FLAT_READ', 'A10_BLOCK_HEADER_CONFLICT',
                      'A10_BLOCK_PENDING_READ_START', 'A10_BLOCK_BUSY_SUPPRESSION',
                      'A10_BLOCK_UNCHANGED_WORK_CYCLES', 'A10_BLOCK_RESET'):
            self.assertIn(fault, cpp)
        self.assertIn('AW==5 || AW==8', cpp)

    def test_all_fields_and_small_geometry_contract(self):
        for aw in (5, 8):
            for field in range(3):
                m, files = prep.role(aw, field)
                self.assertEqual(m['build']['parameters'], dict(AW=aw,
                    P=prep.batch.old.math.FIELDS[field].p, Q=prep.batch.old.math.FIELDS[field].q))
                self.assertEqual(m['build']['top'], prep.TOP)
                self.assertEqual(m['build']['cpp_source'], prep.CPP)
                self.assertIn(prep.source.ROUTE, m['build']['sv_sources'])
                self.assertIn(prep.source.TARGET, m['build']['sv_sources'])
                self.assertNotIn(prep.batch.repair.ENGINE_V2, m['build']['sv_sources'])
                self.assertFalse(any('host16' in n for n in m['build']['sv_sources']))
                self.assertEqual(files[prep.source.TARGET], (prep.ROOT/prep.source.TARGET).read_bytes())
                self.assertEqual(m['block_probe']['source_only_forward_cycles'], 50 if aw == 5 else 88)
                self.assertEqual(m['steps'][0]['expected_stderr'], '')
                self.assertIn(f'offsets={1 << (aw-4)}', m['steps'][0]['expected_stdout'])
                self.assertEqual(m['sources'], {n: prep.batch.sha(raw) for n,raw in files.items()})

    def test_invalid_geometry_field_and_drift_fail_closed(self):
        for aw, field in ((16,0),(4,0),(5,3),(True,0),(5,True)):
            with self.assertRaises(ValueError): prep.role(aw, field)
        broken = dict(prep.PINS, **{prep.CPP:'0'*64})
        with patch.object(prep,'PINS',broken):
            with self.assertRaisesRegex(ValueError,'SOURCE_DRIFT'): prep.source_guard()

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory(prefix='anext-block-probe-') as directory:
            with self.assertRaisesRegex(ValueError,'FRESH_OUTPUT'):
                prep.prepare(Path(directory), 5, 0, Path('unused-budget.json'))


if __name__ == '__main__': unittest.main()

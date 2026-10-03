import itertools
import unittest
from reference import stream27_r15_all_bind as bind


class Integration(unittest.TestCase):
    def test_all_off_literal(self):
        for n in (256,65536):
            parent=bind.fixed.capture(n)
            self.assertEqual(bind.prepare(n),parent)
            self.assertIsNot(bind.bind(parent),parent)

    def test_all_compute_modes(self):
        for n in (256,65536):
            parent=bind.fixed.capture(n)
            for fixed,lean,watch,storage in itertools.product((0,1),repeat=4):
                if not (fixed or lean or watch or storage):continue
                out=bind.prepare(n,fixed_schedule=fixed,lean_build=lean,
                                 progress_watchdog=watch,storage_to_ram=storage)
                self.assertEqual(out['geometry'],parent['geometry'])
                self.assertEqual(len(out['files']),58+watch+storage)
                self.assertEqual(out['parameters']['FIXED_SCHEDULE'],fixed)
                self.assertEqual(out['parameters']['STORAGE_TO_RAM'],storage)
                self.assertEqual(out['parameters']['DIRECT_COLD'],0)
                self.assertEqual(out['parameters']['PCIE_SHELL'],0)
                warm=next(text for name,text in out['files'].items() if name.startswith('genefer_stream27_warm_contexts_'))
                self.assertIn('cold_request_bad',warm)
                self.assertIn('queued_command_bad',warm)
                if fixed:
                    self.assertIn('r15_calendar_bad',warm)
                    self.assertIn('cold_request_bad || r15_calendar_bad)local_error<=1;',warm)
                self.assertFalse(out['r15_all']['native_qualification_inherited'])

    def test_no_parent_mutation(self):
        before=bind.fixed.capture(256)
        snapshot=bind.fixed.capture(256)
        bind.bind(before,fixed_schedule=1,lean_build=1,progress_watchdog=1,storage_to_ram=1)
        self.assertEqual(before,snapshot)


if __name__=='__main__':unittest.main()

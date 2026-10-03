import importlib.util
import unittest
from fpga.reference import stream27_r15_alloff_native as own
from fpga.reference import stream27_r15_fixed_schedule_native as donor


class R15AllOffNativeTests(unittest.TestCase):
    def test_literal_parent_and_fresh_execution_scope(self):
        for stage in ('aw8','full'):
            original,oldfiles,parent=donor.capture(stage)
            manifest,files,bundle=own.role(stage)
            self.assertEqual(bundle,parent)
            self.assertEqual(manifest['build'],original['build'])
            for name in original['build']['sv_sources']:self.assertEqual(files[name],oldfiles[name])
            self.assertTrue(manifest['r15_all_off']['prior_record_execution_or_clock_not_inherited'])
        spec=importlib.util.spec_from_file_location('_native_result_validator',own.ROOT/own.SELF)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertTrue(callable(module.validate))


if __name__=='__main__':unittest.main()

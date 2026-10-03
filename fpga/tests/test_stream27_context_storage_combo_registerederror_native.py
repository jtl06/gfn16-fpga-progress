import unittest
from fpga.reference import stream27_context_storage_combo_registerederror_native as normal


class RegisteredErrorNativeTests(unittest.TestCase):
    def test_captured_normal_sources_and_runtime(self):
        for stage in ('aw8', 'full'):
            manifest, files, bundle = normal.capture(stage)
            self.assertEqual(len(bundle['files']), 55)
            normal.runtime_before_model(files[manifest['build']['cpp_source']].decode())

    def test_runtime_must_precede_each_model(self):
        valid = ('gfn16_runtime::configure(context,argc,argv);DUT d{&context};'
                 'gfn16_runtime::matches(context,d);')
        normal.runtime_before_model(valid)
        for broken in (
            'DUT d{&context};' + valid,
            'DUT d{&context};gfn16_runtime::configure(context,argc,argv);'
            'gfn16_runtime::matches(context,d);',
            valid.replace('gfn16_runtime::configure(context,argc,argv);', ''),
        ):
            with self.assertRaises(ValueError):
                normal.runtime_before_model(broken)

    def test_production_not_admitted_before_freeze(self):
        if normal.READY == 'SOURCE_NOT_FROZEN':
            with self.assertRaisesRegex(ValueError, 'EXACT_PRODUCER_FREEZE_REQUIRED'):
                normal.require_freeze()
        else:
            normal.require_freeze()


if __name__ == '__main__':
    unittest.main()

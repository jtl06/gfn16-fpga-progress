import unittest
from fpga.reference import stream27_r15_fixed_schedule_native as own


class R15FixedNativeTests(unittest.TestCase):
    def test_own_graph_runtime_and_unchanged_calendar(self):
        for stage in ('aw8','full'):
            with self.subTest(stage=stage):
                original,oldfiles,parent=own.capture(stage)
                manifest,files,bundle=own.role(stage)
                self.assertEqual(len(bundle['files']),58)
                self.assertEqual(len(manifest['build']['sv_sources']),58+(stage=='full'))
                self.assertEqual(manifest['build']['parameters'],dict(original['build']['parameters'],FIXED_SCHEDULE=1))
                self.assertEqual(bundle['geometry'],parent['geometry'])
                self.assertEqual(files[manifest['build']['cpp_source']],oldfiles[original['build']['cpp_source']])
                self.assertTrue(manifest['r15_fixed_schedule']['donor_results_not_inherited'])
                self.assertEqual(manifest['sources'],{n:own.sha(b) for n,b in files.items()})
                if stage=='full':
                    self.assertIn('.FIXED_SCHEDULE(FIXED_SCHEDULE)',files['rtl/'+manifest['build']['top']+'.sv'].decode())
                    self.assertEqual(files['rtl/tb/s4_p16_two_context_full_config.h'],oldfiles['rtl/tb/s4_p16_two_context_full_config.h'])
                else:
                    self.assertEqual(manifest['steps'],original['steps'])

    def test_invalid_stage(self):
        with self.assertRaises(ValueError):own.role('aw5')


if __name__=='__main__':unittest.main()

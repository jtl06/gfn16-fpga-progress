import unittest
from fpga.reference import stream27_r15_compute_native as own


class R15ComputeNativeTests(unittest.TestCase):
    def test_source_own_zero_edge_graph_all_flags(self):
        for stage in ('aw8','full'):
            with self.subTest(stage=stage):
                original,oldfiles,parent=own.donor.capture(stage)
                manifest,files,bundle=own.role(stage)
                self.assertEqual(len(bundle['files']),60)
                self.assertEqual(len(manifest['build']['sv_sources']),60+(stage=='full'))
                self.assertEqual(bundle['geometry'],parent['geometry'])
                self.assertEqual(manifest['build']['parameters'],dict(original['build']['parameters'],**own.FLAGS))
                self.assertEqual(files[manifest['build']['cpp_source']],oldfiles[original['build']['cpp_source']])
                self.assertFalse(manifest['r15_compute']['host_GL_implemented'])
                self.assertTrue(manifest['r15_compute']['donor_results_not_inherited'])
                if stage=='full':
                    observer=files['rtl/'+manifest['build']['top']+'.sv'].decode()
                    for flag in own.FLAGS:self.assertIn('.'+flag+'('+flag+')',observer)
                    self.assertEqual(files['rtl/tb/s4_p16_two_context_full_config.h'],oldfiles['rtl/tb/s4_p16_two_context_full_config.h'])
                self.assertEqual(manifest['sources'],{n:own.sha(raw) for n,raw in files.items()})


if __name__=='__main__':unittest.main()

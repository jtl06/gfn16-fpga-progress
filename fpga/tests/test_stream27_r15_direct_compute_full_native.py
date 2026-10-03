import unittest
from fpga.reference import stream27_r15_direct_compute_full_native as p


class DirectFull(unittest.TestCase):
    def test_source_driver_and_observer_only(self):
        m,f,b=p.role()
        self.assertEqual(len(b['files']),65)
        self.assertEqual(len(m['build']['sv_sources']),66)
        self.assertEqual(m['build']['parameters']['DIRECT_COLD'],1)
        cpp=f[p.CPP].decode()
        self.assertNotIn('d.load_we=d.read_en=1',cpp)
        self.assertIn('bool accepted=d.dc_word_ready',cpp)
        self.assertIn('d.dc_lease=d.dc_next_lease',cpp)
        self.assertIn('R15_DIRECT_COMMIT_LOADED_AUTHORITY',cpp)
        self.assertIn('R84_FULL_CONTEXT_ALONE_BIT_IDENTITY',cpp)
        self.assertIn('image_copy_cycles,ctx)==N+4',cpp)
        obs=f['rtl/'+m['build']['top']+'.sv'].decode()
        self.assertIn('input logic dc_link_drained',obs)
        self.assertIn('candidate.direct_cold.candidate.engine.arithmetic.field_fast',obs)
        self.assertNotIn('=candidate.engine.',obs)
        self.assertNotIn('{candidate.engine.',obs)
        self.assertNotIn(',candidate.engine.',obs)


if __name__=='__main__':unittest.main()

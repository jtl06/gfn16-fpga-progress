import unittest
from fpga.reference import stream27_r15_direct_driver_adapter_v2 as own


class R15PackedDriverAdapterTests(unittest.TestCase):
    def test_packed_word_only_change_exact_reverse_all_three_roles(self):
        for mode in own.ROLES:
            with self.subTest(mode=mode):
                manifest,files,bundle,r=own.role(mode)
                cpp=files[manifest['build']['cpp_source']].decode()
                self.assertNotIn(r['before'],cpp)
                self.assertEqual(cpp.count(r['after']),r['count'])
                self.assertTrue(manifest['r15_packed_driver_adapter_v2']['cpp_literal_reverse'])
                for n,t in bundle['files'].items():self.assertEqual(files['rtl/'+n],t.encode())
                self.assertEqual(manifest['sources'],{n:own.sha(v) for n,v in files.items()})


if __name__=='__main__':unittest.main()

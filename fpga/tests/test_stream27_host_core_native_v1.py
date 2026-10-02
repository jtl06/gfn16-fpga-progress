import unittest
from fpga.reference import stream27_host_core_native_v1 as native


class HostNativeCorpus(unittest.TestCase):
    def test_small_corpus_independent_whole_integer_and_special(self):
        for n in (32,256):
            cases=native.cases(n)
            self.assertEqual(len(cases),5)
            self.assertEqual(sum(job['count'] for case in cases for job in case['jobs']),19)
            self.assertEqual(cases[4]['jobs'][0]['expected'],[-1]+[0]*(n-1))
            self.assertEqual(cases[4]['jobs'][1]['expected'],[1]+[0]*(n-1))
            self.assertEqual(cases[2]['jobs'][1]['changes'],[(7,-1)])
            self.assertNotEqual(cases[3]['jobs'][0]['base'],cases[3]['jobs'][1]['base'])
            self.assertEqual(len(native.corpus_text(n,cases).split()),2+sum(2+n+sum(6+2*len(job['changes'])+n for job in case['jobs']) for case in cases))

    def test_source_reads_actual_words_and_counts_completion(self):
        text=(native.ROOT/native.BENCH).read_text()
        self.assertIn('actual=word(d.read_data),old=word(d.t5b_read_data)',text)
        self.assertIn('d.cycles==last',text)
        self.assertIn('d.image_copy_cycles==N+3',text)
        self.assertIn('S4_HOST_BUSY_READ_QUARANTINE',text)
        self.assertIn('S4_HOST_IDLE_SIGNED_STORE_NOT_START_VALIDATION',text)
        self.assertNotIn('boost',text)

    def test_no_full_numeric_mac_path(self):
        with self.assertRaisesRegex(ValueError,'SMALL_ONLY'):native.cases(65536)
        with self.assertRaisesRegex(ValueError,'SMALL_ONLY'):native.ordinary_image([0]*65536,1000,1,0,0)


if __name__=='__main__':unittest.main()

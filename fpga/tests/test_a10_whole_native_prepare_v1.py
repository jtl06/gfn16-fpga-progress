import copy
import unittest
from fpga.reference import a10_whole_native_prepare_v1 as prep


class WholeNativePrepareTests(unittest.TestCase):
    def test_matched_cold_warm_and_order(self):
        m, files = prep.role()
        self.assertEqual(m['build']['parameters'], {'AW':16, 'NTT_LANES':64})
        self.assertEqual(m['build']['cpp_source'], prep.whole.BENCH)
        self.assertEqual(len(m['steps']), 2)
        self.assertFalse(m['batch_role']['numeric_full_N_locally_performed'])
        self.assertEqual(sum(s['metadata']['operations'] for s in m['batch_role']['segments']), 12)
        self.assertEqual(sum(s['metadata']['readbacks'] for s in m['batch_role']['segments']), 10)
        for step in m['steps']:
            self.assertEqual(step['expected_returncode'], 0)
            self.assertIn('cycles=30080 conversion=4102 roots=9 ntt=17709 crt=4113 carry=4147', step['expected_stdout'])
            self.assertIn('cycles=30071 conversion=4102 roots=0 ntt=17709 crt=4113 carry=4147', step['expected_stdout'])
            self.assertNotIn('seed_setup=815', step['expected_stdout'])
        self.assertEqual(prep.batch.sha(files['segment0.txt']), prep.whole.VECTOR_PINS['segment0.txt'])

    def test_parent_counter_order_and_geometry_negatives(self):
        path=prep.ROOT/prep.whole.VECTORS
        text=(path/'test-segment0.log').read_text()
        metadata=prep.whole.corpus_metadata((path/'segment0.txt').read_text())
        for fault in [text.replace('carry=4147','carry=4148',1),
                      text.replace('seed_setup=815','seed_setup=0',1),
                      text.replace('roots=8743','roots=9',1),
                      text.replace('ntt=20558','ntt=17709',1),
                      text.replace('squares=5','squares=4'), text+'EXTRA\n']:
            with self.assertRaises(ValueError): prep.prediction(fault,metadata)
        wrong=copy.deepcopy(metadata);wrong['runs'][0]['label']='wrong-order'
        with self.assertRaises(ValueError): prep.prediction(text,wrong)


if __name__=='__main__': unittest.main()

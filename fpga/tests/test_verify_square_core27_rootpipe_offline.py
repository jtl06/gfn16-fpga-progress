import unittest
from fpga.reference.verify_square_core27_rootpipe_offline import audit_vectors,radix_integer

VECTOR='2\nLOAD seed 9\n1 0\nRUN square 0\n1 0\nRUN double 1\n2 0\n'
LOG=('square cycles=222 conversion=10 roots=16 ntt=62 crt=82 carry=52 passes=2 base=9 cache_before=0 root_loads=4 root_hits=0 readback=1\n'
     'double cycles=222 conversion=10 roots=0 ntt=62 crt=98 carry=52 passes=2 base=9 cache_before=15 root_loads=0 root_hits=4 readback=1\n'
     'PASS n=2 squares=2 readbacks=2 aborts=0\n')


class RootpipeOfflineTests(unittest.TestCase):
    def test_integer_block_packing(self):
        words=[(i*971)%1000 for i in range(257)]
        self.assertEqual(radix_integer(words,1000),sum(x*1000**i for i,x in enumerate(words)))

    def test_cold_warm_and_direct_math(self):
        rows,receipt=audit_vectors(VECTOR,LOG,1)
        self.assertEqual(len(rows),2)
        self.assertEqual((receipt['cold_runs'],receipt['warm_runs']),(1,1))

    def test_corrupt_expected_integer(self):
        with self.assertRaisesRegex(ValueError,'independent integer oracle'):
            audit_vectors(VECTOR.replace('2 0\n','3 0\n'),LOG,1)

    def test_wrong_phase_cycle_readback_or_cache(self):
        for old,new,reason in (('cycles=222','cycles=223','phase accounting'),
            ('readback=1','readback=0','readback coverage'),
            ('cache_before=15','cache_before=0','transaction/cache order'),
            ('root_hits=4','root_hits=3','cache counters')):
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):
                audit_vectors(VECTOR,LOG.replace(old,new),1)

    def test_noncanonical_equivalent_integer_rejected(self):
        with self.assertRaisesRegex(ValueError,'noncanonical expected digits'):
            audit_vectors(VECTOR.replace('2 0\n','11 -1\n'),LOG,1)

    def test_missing_footer_or_duplicate_case_rejected(self):
        with self.assertRaisesRegex(ValueError,'terminal coverage footer'):
            audit_vectors(VECTOR,LOG.rsplit('PASS',1)[0],1)
        with self.assertRaisesRegex(ValueError,'case/bit identity'):
            audit_vectors(VECTOR.replace('RUN double','RUN square'),LOG,1)


if __name__=='__main__':unittest.main()

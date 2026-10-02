from pathlib import Path
import tempfile
import unittest

from reference.square_core27_rootpipe_regression import (
    check_sources, validate_output, write_vectors, segments, ntt_cycles, NAMES, TOP)

ROOT = Path(__file__).resolve().parents[1]


class RootpipeGate(unittest.TestCase):
    def output(self, aw=1):
        ntt=ntt_cycles(aw)
        return (f'x cycles={ntt+10} conversion=2 roots=0 ntt={ntt} crt=3 carry=5 '
                'passes=2 base=1000 cache_before=15 root_loads=0 root_hits=4 readback=1\n'
                f'PASS n={1<<aw} squares=1 readbacks=1 aborts=0\n')

    def test_source_closure(self):
        sources=check_sources(ROOT)
        self.assertEqual(len(sources),15)
        self.assertEqual(NAMES[-1],TOP)
        self.assertNotIn('genefer_square_core27_stream',NAMES)
        self.assertIn('genefer_ntt_banked27_engine',NAMES) # shared butterfly definition

    def test_exact_valid_output(self):
        rows=validate_output(self.output(),'2\nRUN x 0\n0 0\n',1)
        self.assertEqual(rows[0]['ntt'],62)

    def test_reject_missing_extra_reordered_cases(self):
        for vector in ('2\nRUN y 0\n0 0\n','2\nRUN x 0\n0 0\nRUN z 1\n0 0\n',
                       '2\nRUN x 0\n0 0\nRUN x 0\n0 0\n'):
            with self.assertRaises(ValueError):validate_output(self.output(),vector,1)

    def test_reject_weakened_readback(self):
        with self.assertRaises(ValueError):
            validate_output(self.output(),'2\nRUN_NOREAD x 0\n0 0\n',1)

    def test_reject_counter_cache_and_footer_corruption(self):
        output=self.output(); vector='2\nRUN x 0\n0 0\n'
        for old,new in [('cycles=72','cycles=73'),('ntt=62','ntt=61'),
                        ('root_hits=4','root_hits=3'),('cache_before=15','cache_before=7'),
                        ('base=1000','base=2'),('aborts=0','aborts=1'),('PASS','FAIL')]:
            with self.subTest(old=old),self.assertRaises(ValueError):
                validate_output(output.replace(old,new),vector,1)
        with self.assertRaises(ValueError):validate_output(output+output.splitlines()[-1]+'\n',vector,1)

    def test_vector_readback_reset_and_chain_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'vectors.txt'
            for aw in (1,5,7):
                meta=write_vectors(path,aw,20260929,True)
                raw=path.read_bytes(); _,parts,ids,_=segments(raw)
                self.assertEqual(len(ids),meta['squares'])
                self.assertEqual(sum(line.startswith(b'RUN ') for line in raw.splitlines()),meta['readbacks'])
                self.assertIn(b'RUN_NOREAD no-host-chain',raw)
                if aw<=5:self.assertIn(b'ABORT ntt 1',raw)
                self.assertEqual(raw.splitlines(keepends=True)[0]+b''.join(
                    b''.join(payload.splitlines(keepends=True)[1:]) for _,_,payload in parts),raw)


if __name__=='__main__':unittest.main()

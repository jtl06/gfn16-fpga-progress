import tempfile
from pathlib import Path
import unittest
from reference.stream27_longchain import digits,vectors,validate_log


class LongChainTests(unittest.TestCase):
    def test_radix_roundtrip_including_minusone(self):
        for base in (3,9,17):
            for value in range(base**2+1):
                d=digits(value,base,2)
                self.assertEqual(sum(x*base**i for i,x in enumerate(d))%(base**2+1),value)

    def test_vector_oracle_and_checkpoint_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'vectors.txt';r=vectors(p,n=4,rounds=10)
            self.assertEqual((r['squares'],r['readbacks']),(40,8))
            lines=p.read_text().splitlines();self.assertEqual(lines[0],'4')
            value=0;base=0
            for i in range(1,len(lines),2):
                command=lines[i].split();d=list(map(int,lines[i+1].split()))
                if command[0].startswith('LOAD'):
                    base=int(command[2]);value=sum(x*base**j for j,x in enumerate(d))
                else:
                    value=value*value*(2 if int(command[2]) else 1)%(base**4+1)
                    self.assertEqual(sum(x*base**j for j,x in enumerate(d))%(base**4+1),value)

    def test_completion_line_alone_does_not_pass(self):
        r=dict(n=4,squares=1,readbacks=1,cases=[dict(label='test',double_bits=[0])])
        with self.assertRaisesRegex(ValueError,'metrics'):
            validate_log('PASS n=4 squares=1 readbacks=1 aborts=0',r)

    def test_chain_length_is_bounded(self):
        for rounds in (0,1,257,True):
            with self.assertRaises(ValueError):vectors(Path('unused'),n=4,rounds=rounds)

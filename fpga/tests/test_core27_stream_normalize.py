"""Synthetic metadata fixtures only; these are not FPGA performance measurements."""
import copy
import unittest
from reference.square_core27_stream_normalize import expected_atomic,expected_config,normalize


class NormalizeEvidence(unittest.TestCase):
    def fixture(self):
        rows=[]
        for warm in (False,True):
            roots=0 if warm else 4*(65536+2)
            rows.append(dict(aw=16,n=65536,ntt_lanes=64,io_lanes=16,base=604832956,
                case='fixture-warm' if warm else 'fixture-cold',cycles=roots+10,
                conversion=1,roots=roots,ntt=2,crt=3,carry=4,passes=2,
                cache_before=15 if warm else 0,root_loads=0 if warm else 4,
                root_hits=4 if warm else 0,readback=1))
        return dict(status='passed',radix_bits=32,configuration=expected_config(64),
                    atomic_profile=expected_atomic(),metrics=rows,vectors={'16':dict(squares=2,readbacks=2)})
    def test_valid_and_raw_immutable(self):
        raw=self.fixture();before=copy.deepcopy(raw);result=normalize(raw)
        self.assertEqual(raw,before)
        self.assertIs(result['metrics'][0]['readback'],True)
        self.assertIs(result['metrics'][0]['root_cache_warm'],False)
        self.assertIs(result['metrics'][1]['root_cache_warm'],True)
    def test_bad_readback_types_and_values(self):
        for value in (True,1.0,2,-1,None):
            raw=self.fixture();raw['metrics'][0]['readback']=value
            with self.subTest(value=value),self.assertRaises(ValueError):normalize(raw)
    def test_cache_incoherence(self):
        for index,key,value in ((0,'cache_before',3),(0,'root_loads',0),(0,'root_hits',1),
                                (1,'root_loads',1),(1,'root_hits',0),(1,'roots',1)):
            raw=self.fixture();raw['metrics'][index][key]=value
            if key=='roots':raw['metrics'][index]['cycles']+=1
            with self.subTest(key=key),self.assertRaises(ValueError):normalize(raw)
    def test_profile_and_counts(self):
        for mutate in (lambda r:r.update(status='failed'),lambda r:r.update(radix_bits=27),
                       lambda r:r['configuration'].update(fuse_input_mont=True),
                       lambda r:r['atomic_profile'].update(radix_bits=27),
                       lambda r:r['vectors']['16'].update(readbacks=1),
                       lambda r:r['metrics'][0].update(ntt_lanes=16),
                       lambda r:r['metrics'][0].update(cycles=1),
                       lambda r:r['metrics'][1].update(case='fixture-cold')):
            raw=self.fixture();mutate(raw)
            with self.assertRaises(ValueError):normalize(raw)


if __name__=='__main__':unittest.main()

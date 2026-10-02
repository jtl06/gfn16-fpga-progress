"""Synthetic evidence-validation fixtures; no fit or throughput claims."""
import copy
import unittest
from reference.square_core27_stream_prefetch_normalize import normalize,expected_config,expected_atomic


def fixture():
    cold=dict(aw=5,n=32,ntt_lanes=64,io_lanes=16,base=97,case='cold',cycles=3463,
        conversion=11,roots=3089,ntt=246,crt=64,carry=53,passes=2,
        profile_before=0,profile_loads=1,profile_hits=0,profile_words=3084,seed_setup=122,readback=1)
    warm=dict(cold,case='warm',cycles=374,roots=0,profile_before=1,profile_loads=0,
              profile_hits=1,profile_words=0,readback=0)
    return dict(status='passed',configuration=expected_config(64),atomic_profile=expected_atomic(),
        radix_bits=32,metrics=[cold,warm],vectors={'5':dict(squares=2,readbacks=1)})


class PrefetchNormalize(unittest.TestCase):
    def test_preserves_raw_and_explicit_profile_metadata(self):
        raw=fixture();before=copy.deepcopy(raw);result=normalize(raw)
        self.assertEqual(raw,before)
        self.assertFalse(result['metrics'][0]['profile_cache_warm'])
        self.assertTrue(result['metrics'][1]['profile_cache_warm'])
        self.assertIs(type(result['metrics'][0]['readback']),bool)
        self.assertNotIn('root_cache_warm',result['metrics'][0])

    def test_cold_and_warm_fields_are_not_invented(self):
        for which in (0,1):
            for key in ('profile_before','profile_loads','profile_hits','profile_words','roots'):
                raw=fixture();raw['metrics'][which][key]+=1
                with self.subTest(which=which,key=key),self.assertRaises(ValueError):normalize(raw)

    def test_profile_and_basis_cannot_be_borrowed(self):
        for key,value in [('root_cache',True),('profile_cache',False),('generated_roots',False),
                          ('prefetch_roots',False),('profile_format',2),('ntt_lanes',16),('fuse_input_mont',True)]:
            raw=fixture();raw['configuration'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):normalize(raw)
        raw=fixture();raw['atomic_profile']['radix_bits']=27
        with self.assertRaises(ValueError):normalize(raw)

    def test_bad_types_coverage_counter_and_duplicate(self):
        for key,value in [('aw',True),('profile_before',False),('readback',2),('seed_setup',247),
                          ('passes',1),('cycles',3464),('n',16),('base',68)]:
            raw=fixture();raw['metrics'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):normalize(raw)
        for change in ('duplicate','coverage','failed'):
            raw=fixture()
            if change=='duplicate':raw['metrics'][1]['case']='cold'
            elif change=='coverage':raw['vectors']['5']['squares']=3
            else:raw['status']='running'
            with self.assertRaises(ValueError):normalize(raw)


if __name__=='__main__':unittest.main()

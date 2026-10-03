import copy
import json
import unittest
from fpga.reference import stream27_r14_host_offload_long_v1 as m

class LongTests(unittest.TestCase):
    def value(self):
        count=100;warm=[f+99*8464+12562 for f in (204,4436)];done=[w+2 for w in warm]
        return dict(count=count,squares=200,descriptors=198,doubles=sum(map(sum,m.bits(count))),
            input_words=393408,raw_words=131136,checked_words=131072,initial_resets=1,model_threads=1,
            cycles=done[1],warm_edges=warm,done_edges=done,overlap_edges=done[0]-1,
            reference_seconds=10.,model_seconds=20.,seconds=30.)
    def check_value(self,v,stderr=''):
        return m.validate('R14_LONG_PASS '+json.dumps(v)+'\n',stderr,0,m.config(),{})
    def test_typed_calendar(self):
        self.assertEqual(self.check_value(self.value())['status'],'PASS_expected_contracts')
        for key in ('descriptors','raw_words','initial_resets','checked_words','cycles'):
            v=self.value();v[key]+=1
            with self.assertRaises(ValueError):self.check_value(v)
        v=self.value();v['done_edges'][0]+=1
        with self.assertRaises(ValueError):self.check_value(v)
        with self.assertRaises(ValueError):self.check_value(self.value(),'warning')
    def test_scalar_prefix(self):
        self.assertEqual(m.bits(100),[r[:100] for r in m.bits(1000)])
        with self.assertRaises(ValueError):m.bits(101)
    def test_own_on_only_source_and_reference(self):
        manifest,files=m.role()
        self.assertEqual(len(manifest['build']['sv_sources']),66)
        self.assertNotIn('equivalence',manifest['build']['top'])
        self.assertEqual(manifest['build']['parameters']['HOST_OFFLOAD'],1)
        self.assertIn('COUNT=100,INTERVAL=8464',files[m.HEADER].decode())
        cpp=files[m.CPP].decode()
        for text in ('s4_full_reference::square','R14_LONG_ALL_N_REFERENCE','R14_LONG_EVERY_EDGE_CALENDAR',
                     'R14_LONG_RAW_DONE_W_PLUS_TWO','R14_LONG_RAW_OWNER_ORDER','R14_LONG_FINITE_NO_RELOAD'):
            self.assertIn(text,cpp)
        self.assertNotIn('run_feed_twin',cpp)
        self.assertEqual(cpp.count('d.rst_n=0'),1)
        self.assertEqual(manifest['r14_own_long']['normal_gate'],m.GATE)
    def test_unmeasured_full_count_only_delta(self):
        a,fa=m.role(100);b,fb=m.role(1000)
        self.assertEqual(a['build'],b['build'])
        self.assertEqual([n for n in fa if fa[n]!=fb[n]],[m.HEADER])
        self.assertTrue(b['r14_own_long']['own_runtime_unmeasured'])

if __name__=='__main__':unittest.main()

import json
import unittest
from fpga.reference import stream27_r14f_host_offload_long_v1 as m
class Tests(unittest.TestCase):
    def value(self):
        warm=[f+99*8461+12559 for f in (204,4434)];done=[w+2 for w in warm]
        return dict(count=100,squares=200,descriptors=198,doubles=sum(map(sum,m.bits(100))),input_words=393408,
            raw_words=131136,checked_words=131072,initial_resets=1,model_threads=1,cycles=done[1],warm_edges=warm,done_edges=done,
            overlap_edges=done[0]-1,reference_seconds=10.,model_seconds=20.,seconds=30.)
    def test_typed_own_field100_calendar(self):
        v=self.value();text='R14F_LONG_PASS '+json.dumps(v)+'\n'
        self.assertEqual(m.validate(text,'',0,m.config(),{})['status'],'PASS_expected_contracts')
        for field in ('descriptors','checked_words','cycles'):
            wrong=dict(v);wrong[field]+=1
            with self.assertRaises(ValueError):m.validate('R14F_LONG_PASS '+json.dumps(wrong)+'\n','',0,m.config(),{})
        with self.assertRaises(ValueError):m.validate(text,'',0,dict(m.config(),interval=8464),{})
    def test_no_relay_or_old_leaf(self):
        manifest,files=m.role()
        self.assertEqual(len(manifest['build']['sv_sources']),66)
        self.assertIn('protected_field100',manifest['build']['top'])
        self.assertNotIn('relay13',manifest['build']['top'])
        for flag in ('INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG','FORWARD_INGRESS_REG'):
            self.assertNotIn(flag,manifest['build']['parameters'])
        self.assertIn('rtl/genefer_stream27_host_offload_ingress_field100_v1.sv',manifest['build']['sv_sources'])
        self.assertIn('INTERVAL=8461,FIRST_DIGIT=8459,CARRY_DONE=12558',files[m.HEADER].decode())
        self.assertEqual(files[m.CPP].decode().count('d.rst_n=0'),1)
    def test_source_only_count_delta(self):
        a,fa=m.role(100);b,fb=m.role(1000)
        self.assertEqual(a['build'],b['build']);self.assertEqual([n for n in fa if fa[n]!=fb[n]],[m.HEADER])
        self.assertEqual(m.bits(100),[r[:100] for r in m.bits(1000)])
if __name__=='__main__':unittest.main()

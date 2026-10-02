"""Strict normalized-evidence rejection tests; aethia only."""
import copy
import socket
import unittest
from reference.square_core27_folded_report import normalize


@unittest.skipUnless(socket.gethostname() == 'aethia', 'aethia only')
class FoldedReport(unittest.TestCase):
    def report(self, lanes=64, warm=True):
        aw=16; n=1<<aw
        ntt=2*aw*((n+2*lanes-1)//(2*lanes)+9)+3*((n+lanes-1)//lanes+8)+10
        roots=0 if warm else 4*(n+2)
        item=dict(aw=aw,ntt_lanes=lanes,io_lanes=16,conversion=4105,ntt=ntt,crt=4158,carry=8312,
                  roots=roots,cycles=4105+ntt+4158+8312+roots,cache_before=15 if warm else 0,
                  root_loads=0 if warm else 4,root_hits=4 if warm else 0,readback=1)
        return dict(status='passed',radix_bits=32,crt_modulus=487945222748036195811329,
                    max_doubled_coefficient=131071999737856000131072,profiles=[[lanes,16]],
                    host='aethia',ancestor_sha256='ancestor',runtime_threads=8,steps=[],
                    sources={'rtl/kernel/genefer_ntt_banked27_folded_engine.sv':'475a7500e58485c943961729334f8c03e35eb52095657813f8c770d29cb5167c'},metrics=[item])

    def test_profiles_cold_warm_and_boolean_readback(self):
        for lanes in (16,64):
            for warm in (False,True):
                for value in (0,1,False,True):
                    raw=self.report(lanes,warm); raw['metrics'][0]['readback']=value
                    before=copy.deepcopy(raw); view=normalize(raw)
                    self.assertEqual(raw,before)
                    self.assertIs(type(view['metrics'][0]['readback']),bool)
                    self.assertEqual(view['configuration']['ntt_routing'],'folded-root-v1')
                    self.assertFalse(view['configuration']['stream_carry'])
                    self.assertEqual(view['metrics'][0]['cycles']-view['metrics'][0]['roots'],94721 if lanes==16 else 36353)

    def test_bad_readback(self):
        for value in (None,2,-1,'0','false',0.0):
            raw=self.report(); raw['metrics'][0]['readback']=value
            with self.subTest(value=value),self.assertRaises(ValueError): normalize(raw)

    def test_ancestor_proof_is_not_compiled_closure(self):
        raw=self.report()
        name='rtl/kernel/genefer_square_core27.sv'
        raw['sources'][name]='baseline-proof-only'
        view=normalize(raw)
        self.assertNotIn(name,view['sources'])
        self.assertEqual(view['ancestor_sources'][name],'baseline-proof-only')
        self.assertEqual(raw['sources'][name],'baseline-proof-only')

    def test_counter_and_cache_mutants(self):
        for key,value in [('cache_before',7),('root_loads',4),('root_hits',0),('roots',1),
                          ('cycles',36352),('conversion',4104),('ntt',19743),('io_lanes',64),
                          ('aw',0),('ntt_lanes',16),('carry',True)]:
            raw=self.report(); raw['metrics'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): normalize(raw)

    def test_missing_wrong_or_failed_evidence(self):
        for key,value in [('status','running'),('status','failed'),('radix_bits',27),
                          ('crt_modulus',1),('profiles',[[32,16]]),('metrics',[]),('sources',{})]:
            raw=self.report(); raw[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): normalize(raw)


if __name__ == '__main__': unittest.main()

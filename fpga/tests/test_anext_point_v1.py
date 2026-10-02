import unittest
from fpga.reference import anext_point_source_v1 as src
from fpga.reference.anext_point_contract_v1 import schedule
from fpga.reference.anext_composition_contract_v1 import schedule as old

class PointComposition(unittest.TestCase):
    def test_exact_sources_and_reversible_delta(self):
        self.assertEqual(len(src.verify()),6)
        for name,text in src.expected().items():
            self.assertNotIn('genefer_anext_core_v1',text)
        with self.assertRaises(ValueError):src.apply_delta('missing anchors')

    def test_exact_event_delta_and_port_guard(self):
        changed={'point_engine_cycles','ntt_controller_cycles','warm_backend','warm_host',
                 'cold_cached_backend','cold_cached_host','cold_loaded_backend','cold_loaded_host','assumptions'}
        for aw in (5,8,16):
            a,b=old(aw),schedule(aw)
            for key in a:
                if key not in changed:self.assertEqual(a[key],b[key],key)
                elif key!='assumptions':self.assertEqual(a[key]+1,b[key],key)
        self.assertEqual(schedule(16)['warm_backend'],21873)
        with self.assertRaises(ValueError):schedule(5,block_response_edges=2)

    def test_new_cycles_and_old_cycles_negative(self):
        from fpga.tests.test_anext_native_output_v1 import fixture
        from fpga.reference.anext_point_output_v1 import validate
        for aw in (5,8):
            original,vectors=fixture(aw);rows=[]
            for line in original.splitlines():
                if line.startswith('A4_CORE_SQUARE '):
                    words=line.split()
                    for i,word in enumerate(words):
                        if '=' in word:
                            key,value=word.split('=')
                            if key in ('ntt','total','latency'):words[i]=key+'='+str(int(value)+1)
                    line=' '.join(words)
                rows.append(line)
            text='\n'.join(rows)+'\n';cfg=dict(mode='normal',aw=aw);assets={'vectors':vectors}
            self.assertEqual(validate(text,'',0,cfg,assets)['candidate'],'A-next-point-v1')
            for bad in (original,text.replace('seed=0','seed=1',1),text+'extra\n'):
                with self.assertRaises((ValueError,AssertionError)):validate(bad,'',0,cfg,assets)
            with self.assertRaises((ValueError,AssertionError)):validate(text,'',True,cfg,assets)

if __name__=='__main__':unittest.main()

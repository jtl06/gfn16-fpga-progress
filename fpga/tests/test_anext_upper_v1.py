import unittest
from fpga.reference import anext_upper_source_v1 as src
class Upper(unittest.TestCase):
    def test_binding_and_cell_guard(self):
        self.assertEqual(len(src.verify()),6)
        a=src.point.expected();b=src.expected()
        for name,text in a.items():
            expected=text.replace(src.OLD_BIND,src.NEW_BIND) if name.endswith('genefer_anext_point_block_engine_v1.sv') else text
            self.assertEqual(b[src.renames(name)],src.renames(expected))
    def test_point_cycle_contract_unchanged(self):
        from fpga.tests.test_anext_native_output_v1 import fixture
        from fpga.reference.anext_upper_output_v1 import validate
        for aw in (5,8):
            old,v=fixture(aw);lines=[]
            for line in old.splitlines():
                words=line.split()
                if words[0]=='A4_CORE_SQUARE':
                    for i,w in enumerate(words):
                        if '=' in w:
                            k,x=w.split('=')
                            if k in ('ntt','total','latency'):words[i]=k+'='+str(int(x)+1)
                lines.append(' '.join(words))
            new='\n'.join(lines)+'\n';cfg=dict(mode='normal',aw=aw);assets={'vectors':v}
            self.assertEqual(validate(new,'',0,cfg,assets)['candidate'],'A-next-upper-v1')
            with self.assertRaises((ValueError,AssertionError)):validate(old,'',0,cfg,assets)
            with self.assertRaises((ValueError,AssertionError)):validate(new,'',False,cfg,assets)
if __name__=='__main__':unittest.main()

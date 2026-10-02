import copy
import re
import unittest
from unittest.mock import patch
from fpga.reference import stream27_host_chain_diet as diet
from fpga.reference import stream27_p16_diet_full_native as native


class DietWholeSource(unittest.TestCase):
    def test_zero_is_complete_donor(self):
        sentinel={'files':{'unchanged':'bytes'},'anything':[1,2,3]}
        with patch.object(diet.parent,'prepare',return_value=sentinel) as donor:
            self.assertIs(diet.prepare(256,16),sentinel)
            donor.assert_called_once_with(256,16,paired=False,contexts=1,allow_full_constants=False,canonical_pipe_stages=0)

    def test_reject_unqualified_geometries_and_flags(self):
        for changes in ({'n':256},{'p':8},{'contexts':2},{'canonical_pipe_stages':0},
                        {'mont_factored':0},{'corr_serial_bfs':True},{'allow_full_constants':False}):
            args=dict(n=65536,p=16,contexts=1,canonical_pipe_stages=1,allow_full_constants=True,
                corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1);args.update(changes)
            with self.assertRaises(ValueError):diet.prepare(**args)

    def test_closed_normal_and_negative_outputs(self):
        c=native.counts();self.assertEqual(c['candidate_cycles'],1395164)
        self.assertEqual(c['true_final_rows'],8192);self.assertEqual(c['paired_reads'],131072)
        line='S4_P16_DIET_HOST_PASS aw=16 p=16 '+' '.join(f'{key}={value}' for key,value in c.items())+' t5b_wait_edges=272282\n'
        self.assertEqual(native.validate(line,'',0,native.config(),{})['status'],'PASS_expected_contracts')
        for stdout,stderr,rc,config in ((line+'extra\n','',0,native.config()),(line,'error',0,native.config()),
            (line,'',1,native.config()),(line.replace('operations=9','operations=8'),'',0,native.config()),
            (line,'',0,dict(native.config(),MONT_FACTORED=0)),(line,'',0,dict(native.config(),aw=True))):
            with self.assertRaises(ValueError):native.validate(stdout,stderr,rc,config,{})

    def test_harness_only_geometry_and_canonical_changes(self):
        text=native.bench_source();old=(native.ROOT/native.OLD_CPP).read_text()
        self.assertIn('AW==16 && P==16',text);self.assertIn('c.canonical==18*N',text)
        self.assertEqual(text.count('(special?10u:9u)'),2)
        inverse=text.replace('AW==16 && P==16 && N==65536','AW==16 && P==8 && N==65536').replace(
            'isolated exact full-N composed-diet P16 host gate','isolated exact full-N P8 host gate').replace(
            '(special?10u:9u)','(special?7u:6u)').replace('c.canonical==18*N','c.canonical==12*N').replace(
            'S4_P16_DIET_HOST_PASS aw=16 p=16','S4_FULL_HOST_PASS aw=16 p=8')
        self.assertEqual(inverse,old)

    def test_full_source_namespace_and_preserved_nonfield_montgomery(self):
        kwargs=dict(allow_full_constants=True,canonical_pipe_stages=1,corr_serial_bfs=2,
            comm_stage_shared_mlab=1,mont_factored=1)
        b=diet.prepare(**kwargs)
        self.assertEqual(b['geometry']['warm_interval'],8459)
        self.assertEqual(b['geometry']['correction_cache_latency'],77)
        self.assertEqual(b['geometry']['cache_margin'],31)
        self.assertEqual(len(b['diet_binding']['new_roots']),3)
        for name in diet.PRESERVED:self.assertEqual(b['files'][name],(diet.ROOT/'rtl/kernel'/name).read_text())
        modules=[module for text in b['files'].values() for module in re.findall(r'\bmodule\s+(\w+)\b',text)]
        self.assertEqual(len(modules),len(set(modules)))
        crt=b['files']['genefer_crt3_27_mont_pipe.sv']
        self.assertIn('genefer_montgomery_mul27_sparse_pipe',crt)
        self.assertNotIn('genefer_stream27_montgomery_factored_v1',crt)
        for root in b['diet_binding']['new_roots']:
            self.assertIn(root+'.sv',b['files'])
            self.assertIn('MONT_FACTORED=1',b['files'][root+'.sv'])
        self.assertFalse(b['diet_binding']['whole_resource_go'])


if __name__=='__main__':unittest.main()

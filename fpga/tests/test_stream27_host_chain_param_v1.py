import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import stream27_host_chain_param_v1 as core
from fpga.reference import stream27_host_chain_param_native_v1 as native
from fpga.reference.stream27_host_core_native_v3 import cases
from fpga.reference.stream27_host_core_native_v1 import corpus_text


class SharedP8Host(unittest.TestCase):
    def test_real_p8_components_and_widths(self):
        for n in (32,256):
            b=core.prepare(n,8,paired=True)
            self.assertEqual(b['parameters']['P'],8)
            self.assertIn('p8',b['top'])
            self.assertIn('genefer_stream27_blockcarry_setup_param_v1.sv',b['files'])
            self.assertIn('genefer_stream27_blockcarry_lane_param_v1.sv',b['files'])
            root=next(s for name,s in b['files'].items() if 'host_chain_aw' in name)
            self.assertIn('ROW_W=AW-$clog2(P)',root);self.assertIn('K=2*N+24*P',root)
            self.assertNotIn('P!=16',root);self.assertNotIn('K=2*N+384',root)
            self.assertIn('((lane&1)<<2)|((lane&2))|((lane&4)>>2)',root)
            self.assertEqual(b['geometry']['rows'],n//8)
            self.assertIn('.EPOCH_SEED(EPOCH_SEED)',b['files'][b['top']+'.sv'])

    def test_exact_profile_and_corpus_actual_p8_packet(self):
        with tempfile.TemporaryDirectory(prefix='s4-p8-source-') as root:
            out=Path(root)/'packet';r=native.prepare(out,n=32);source=out/'inputs/fpga'
            m=json.loads((out/'manifest.json').read_text())
            self.assertEqual(m['build']['parameters'],dict(AW=5,P=8,CONTEXTS=1,EPOCH_SEED=65534))
            header=(source/'rtl/tb/s4_host_config_v1.h').read_text()
            self.assertIn('MIN_BASE=172',header);self.assertIn('constexpr unsigned P=8',header)
            self.assertEqual((source/'assets/host-corpus-v1.txt').read_text(),corpus_text(32,cases(32)))
            bench=(source/'rtl/tb/stream27_host_core_v1.cpp').read_text()
            self.assertIn('d.conversion_cycles==N/P',bench);self.assertIn('d.feed_mode=0',bench)
            self.assertIn('feed_mode0',r['scope']);self.assertIn('preserved reset',r['pending_long'])


if __name__=='__main__':unittest.main()

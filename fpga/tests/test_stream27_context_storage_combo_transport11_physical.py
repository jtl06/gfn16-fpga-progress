import importlib.util
import unittest
from fpga.reference import stream27_context_storage_combo_transport11_physical as p


class Transport11Physical(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out=p.ROOT/'results/throughput-20260929/trackS-c2-storage-combo-transport11-physical-v1/physical-12000-v1'
        cls.m=p.read(cls.out/'project/manifest.json');cls.s=p.read(cls.out/'structural-inventory.json')

    def test_source_and_complete_inventory(self):
        loader=importlib.util.spec_from_file_location('r11_test_guard',p.ROOT/'tools/prefit_structural_guard_v1.py')
        guard=importlib.util.module_from_spec(loader);loader.loader.exec_module(guard)
        self.assertEqual(guard.source_inventory(self.out/'project',self.s)['findings'],[])
        self.assertEqual(len(self.s['transfers']),27)
        native=p.read(p.ROOT/'results/throughput-20260929/trackS-c2-storage-combo-transport11-native-v1/full-normal-v2/production-bundle.json')
        self.assertEqual(self.m['source_sha256'],native['generated_sha256'])
        for t in self.s['transfers']:
            for a in t.get('exception',{}).get('contract_anchors',[]):
                self.assertEqual((self.out/'project'/a['source']).read_text().count(a['text']),1)

    def test_full_transport_flags_and_real_calendar(self):
        params=self.m['core_parameters']
        for flag in ('CRT_TRANSPORT_REG','INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG','LEAN_PROGRESS_WATCHDOG','LEAN_PRODUCTION'):
            self.assertEqual(params[flag],1)
        m=self.m['context_transport11']
        self.assertEqual(m['ntt_compare_reg'],0)
        self.assertEqual(m['term_recurrence_edges'],4)
        self.assertTrue(m['declared_bits_not_mapped_savings'])
        g=self.m['geometry']
        self.assertEqual((g['warm_interval'],g['first_digit'],g['carry_done'],g['sink_accept']),(8463,8462,12561,8419))
        self.assertEqual(p.read(self.out/'provisional-geometry.json')['kwargs'],p.KWARGS)

    def test_origin_carry_and_lean_scope(self):
        text=(self.out/'project/rtl'/next(n for n in self.m['source_sha256'] if n.startswith('genefer_stream27_threefield_carry_aw'))).read_text()
        self.assertIn('if(raw_begin_carry && ((|lane_busy) || (crt_transport_slot && crt_transport_start)))carry_bad=1;',text)
        self.assertIn('if(begin_carry && (|lane_busy))carry_bad=1;',text)
        self.assertEqual(self.m['label'],p.LABEL)
        self.assertFalse(self.m['lean_watchdog_warm_progress']['host_gl_implemented'])


if __name__=='__main__':
    unittest.main()

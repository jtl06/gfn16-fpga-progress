import importlib.util
import unittest
from fpga.reference import stream27_context_feedback12_physical as p


class Feedback12Physical(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out=p.ROOT/'results/throughput-20260929/trackS-c2-feedback12-physical-v1/physical-12000-v2'
        cls.m=p.read(cls.out/'project/manifest.json');cls.s=p.read(cls.out/'structural-inventory.json')

    def test_own_gate_and_every_source_anchor(self):
        loader=importlib.util.spec_from_file_location('r12_test_guard',p.ROOT/'tools/prefit_structural_guard_v1.py')
        guard=importlib.util.module_from_spec(loader);loader.loader.exec_module(guard)
        self.assertEqual(guard.source_inventory(self.out/'project',self.s)['findings'],[])
        self.assertEqual(len(self.s['transfers']),27)
        role=p.ROOT/'results/throughput-20260929/trackS-c2-feedback12-native-v1/aw8-normal'
        self.assertEqual(self.m['native_normal_id'],p.read(role/'global-ticket.json')['id'])
        for t in self.s['transfers']:
            for a in t.get('exception',{}).get('contract_anchors',[]):
                self.assertEqual((self.out/'project'/a['source']).read_text().count(a['text']),1)

    def test_explicit_fifo_plus_q_and_calendar(self):
        g=self.m['geometry'];meta=self.m['context_feedback12']
        self.assertEqual((g['warm_interval'],g['first_digit'],g['carry_done'],g['sink_accept']),(8464,8462,12561,8419))
        self.assertEqual(meta['existing_feedback_fifo_rows'],0)
        self.assertEqual(meta['explicit_feedback_register_rows'],1)
        self.assertTrue(meta['cold_correction_retirement_literal'])
        self.assertTrue(meta['queued_descriptor_rechecked_at_accept'])
        self.assertEqual(p.read(self.out/'provisional-geometry.json')['kwargs'],p.KWARGS)

    def test_full_source_and_unsigned_base0_identity(self):
        self.assertEqual(len(self.m['source_sha256']),58)
        for name in self.m['source_sha256']:
            if name.startswith('genefer_stream27_shared_warm_aw'):
                text=(self.out/'project/rtl'/name).read_text()
                self.assertIn("correction_c0_ok=(base==32'd0) || magnitude<{1'b0,base};",text)
        self.assertEqual(self.m['label'],p.LABEL)
        full=p.ROOT/'results/throughput-20260929/trackS-c2-feedback12-native-v1/full-normal/production-bundle.json'
        if full.exists():self.assertEqual(self.m['source_sha256'],p.read(full)['generated_sha256'])
        old=p.read(self.out.parent/'physical-12000-v1/project/manifest.json')
        self.assertEqual(self.m['source_sha256'],old['source_sha256'])


if __name__=='__main__':
    unittest.main()

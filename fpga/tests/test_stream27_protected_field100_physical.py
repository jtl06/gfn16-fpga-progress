import importlib.util
import unittest
from fpga.reference import stream27_protected_field100_physical as p


class Field100Physical(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.role=p.ROOT/'results/throughput-20260929/trackS-c2-protected-field100-native-v1/aw8-normal'
        cls.out=p.ROOT/'results/throughput-20260929/trackS-c2-protected-field100-physical-v1/physical-12000-v3'
        cls.m,cls.files,cls.s,cls.proof=p.build(cls.role,'s4-p16-c2-protected-field100-aw8-normal-q1-v1')

    def test_exact_captures_controls_and_no_transport(self):
        full=p.read(self.role.parent/'full-normal-v2/production-bundle.json')
        self.assertEqual(self.m['source_sha256'],full['generated_sha256'])
        self.assertEqual(self.m['core_parameters'],dict(full['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42))
        self.assertEqual(self.m['seed'],self.s['identity']['seed'])
        self.assertEqual(self.m['seed'],2)
        for k in ('LEAN_PRODUCTION','CRT_TRANSPORT_REG','INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG'):
            self.assertNotIn(k,self.m['core_parameters'])
        for name,raw in self.files.items():self.assertEqual((self.out/'project'/name).read_bytes(),raw)
        self.assertEqual(self.proof['kwargs'],p.KWARGS)

    def test_all_anchors_and_registered_sources(self):
        self.assertEqual(len(self.s['transfers']),25)
        loader=importlib.util.spec_from_file_location('field100_test_guard',p.ROOT/'tools/prefit_structural_guard_v1.py')
        g=importlib.util.module_from_spec(loader);loader.loader.exec_module(g)
        self.assertEqual(g.source_inventory(self.out/'project',self.s)['findings'],[])
        for t in self.s['transfers']:
            for a in t.get('exception',{}).get('contract_anchors',[]):
                self.assertEqual(self.files[a['source']].decode().count(a['text']),1,(t['id'],a))
            for stage in t['registered_stages']:
                for a in stage['anchors']:self.assertEqual(self.files[stage['source']].decode().count(a),1,(t['id'],a))

    def test_FAST_semantics_and_calendar(self):
        m=self.m['context_protected_field100'];g=self.m['geometry']
        self.assertEqual((m['field_FAST_origin_edges_added'],m['field_report_lag'],m['arithmetic_report_lag'],m['host_report_lag']),(0,1,2,1))
        self.assertFalse(m['R11_transports_composed']);self.assertFalse(m['hardware_logic_level_cap_proven'])
        self.assertTrue(m['numeric_tail_activity_not_bounded_by_one_edge'])
        self.assertEqual((g['warm_interval'],g['first_digit'],g['carry_done'],g['sink_accept']),(8461,8459,12558,8417))
        for f in range(3):self.assertIn(f'field{f}_FAST_to_report_and_quarantine',[t['id'] for t in self.s['transfers']])


if __name__=='__main__':unittest.main()

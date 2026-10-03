import importlib.util
import unittest
from fpga.reference import stream27_protected_relay13_physical as p


class Relay13Physical(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out=p.ROOT/'results/throughput-20260929/trackS-c2-protected-relay13-physical-v1/physical-11500-v1'
        cls.m=p.read(cls.out/'project/manifest.json');cls.s=p.read(cls.out/'structural-inventory.json')

    def test_all_anchors_and_physical_identity(self):
        loader=importlib.util.spec_from_file_location('r13_test_guard',p.ROOT/'tools/prefit_structural_guard_v1.py')
        g=importlib.util.module_from_spec(loader);loader.loader.exec_module(g)
        self.assertEqual(g.source_inventory(self.out/'project',self.s)['findings'],[])
        self.assertEqual((self.m['clock_period_ns'],self.m['seed']),(11.5,1))
        for t in self.s['transfers']:
            for a in t.get('exception',{}).get('contract_anchors',[]):
                self.assertEqual((self.out/'project'/a['source']).read_text().count(a['text']),1,(t['id'],a))
            for stage in t['registered_stages']:
                for a in stage['anchors']:self.assertEqual((self.out/'project'/stage['source']).read_text().count(a),1)

    def test_nine_complete_tuples_no_CRT_stage(self):
        self.assertEqual(len(self.s['transfers']),34)
        byid={t['id']:t for t in self.s['transfers']}
        for f in range(3):
            for k in ('forward_ingress','inverse_ingress','term_pair'):
                t=byid[f'field{f}_{k}_transport'];stage=t['registered_stages'][0]
                self.assertTrue(stage['payload']);self.assertEqual(len(stage['metadata']),2)
                self.assertEqual(stage['alignment'],'same_accepted_edge')
            self.assertEqual(byid[f'field{f}_to_CRT']['registered_stages'],[])
        self.assertEqual(self.m['core_parameters']['CRT_TRANSPORT_REG'],0)
        self.assertNotIn('LEAN_PRODUCTION',self.m['core_parameters'])

    def test_geometry_provisional_and_frozen_parent(self):
        g=self.m['geometry'];meta=self.m['context_protected_relay13']
        self.assertEqual((g['warm_interval'],g['first_digit'],g['carry_done'],g['pointwise_accept'],g['sink_accept']),(8464,8462,12561,4208,8420))
        self.assertEqual(meta['public_FAST_origin_lag'],0);self.assertEqual(meta['field_to_CRT_edges_added'],0)
        self.assertTrue(meta['cold_one_shot_acceptance_retirement_literal'])
        self.assertTrue(meta['protocol_FAST_and_raw_tuple_retirement_literal'])
        self.assertTrue(meta['register_bits_not_mapped_cost']);self.assertFalse(meta['logic_level_cap_proven'])
        proof=p.read(self.out/'provisional-geometry.json');self.assertEqual(proof['kwargs'],p.KWARGS)
        self.assertEqual(proof['generator']['sha256'],p.PIN)
        self.assertEqual(len(self.m['source_sha256']),58)
        full=p.read(p.ROOT/'results/throughput-20260929/trackS-c2-protected-relay13-native-v1/full-normal/production-bundle.json')
        self.assertEqual(self.m['source_sha256'],full['generated_sha256'])
        self.assertEqual(self.m['core_parameters'],dict(full['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42))
        for n,pin in self.m['source_sha256'].items():self.assertEqual(p.sha((self.out/'project/rtl'/n).read_bytes()),pin)


if __name__=='__main__':unittest.main()

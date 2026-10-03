import importlib.util
import unittest
from fpga.reference import stream27_context_storage_combo_timing10_physical as p


class Timing10Physical(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out=p.ROOT/'results/throughput-20260929/trackS-c2-storage-combo-timing10-physical-v1/physical-13000-v1'
        cls.m=p.read(cls.out/'project/manifest.json');cls.s=p.read(cls.out/'structural-inventory.json')

    def test_source_controls_and_all_anchors(self):
        loader=importlib.util.spec_from_file_location('r10_test_guard',p.ROOT/'tools/prefit_structural_guard_v1.py')
        guard=importlib.util.module_from_spec(loader);loader.loader.exec_module(guard)
        self.assertEqual(guard.source_inventory(self.out/'project',self.s)['findings'],[])
        self.assertEqual(len(self.s['transfers']),21)
        self.assertEqual(len(self.m['source_sha256']),58)
        for transfer in self.s['transfers']:
            for anchor in transfer.get('exception',{}).get('contract_anchors',[]):
                self.assertEqual((self.out/'project'/anchor['source']).read_text().count(anchor['text']),1)

    def test_actual_full25_final7_and_geometry(self):
        leaves=list((self.out/'project/rtl').glob('*merged_gs*inputreg*.sv'))
        self.assertEqual(len(leaves),3)
        for leaf in leaves:
            text=leaf.read_text()
            self.assertEqual(text.count('logic [6:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:6];'),1)
            self.assertIn('for(int k=1;k<7;k=k+1)generation_pipe[k]<=generation_pipe[k-1];',text)
        fields=list((self.out/'project/rtl').glob('genefer_stream27_shared_warm*timing10_v1.sv'))
        self.assertEqual(len(fields),3)
        for field in fields:
            self.assertIn('#(.GEN_W(25)) inverse_transform',field.read_text())
        self.assertEqual((self.m['geometry']['warm_interval'],self.m['geometry']['sink_accept']),(8460,8417))

    def test_lean_label_snapshot_and_provisional(self):
        self.assertEqual(self.m['label'],p.LABEL)
        self.assertFalse(self.m['lean_production']['host_gl_implemented'])
        self.assertFalse(self.m['lean_production']['twin_fault_immunity_inherited'])
        self.assertTrue(self.m['context_timing10']['coherent_profile_owner_snapshot'])
        proof=p.read(self.out/'provisional-geometry.json')
        self.assertEqual(proof['kwargs'],dict(p=16,contexts=2,enabled=1,lean_production=1))
        t=next(x for x in self.s['transfers'] if x['id']=='coherent_profile_to_canonical')
        self.assertEqual(t['registered_stages'][0]['metadata'],['canonical_owner','canonical_config_owner'])


if __name__=='__main__':
    unittest.main()

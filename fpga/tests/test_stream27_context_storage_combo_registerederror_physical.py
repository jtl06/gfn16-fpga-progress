"""Read-only source/contract checks of the prepared R9 physical snapshot."""
import importlib.util
import unittest
from fpga.reference import stream27_context_storage_combo_registerederror_physical as p


class R9Physical(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out=p.ROOT/'results/throughput-20260929/trackS-c2-storage-combo-registerederror-physical-v1/physical-v2'
        cls.manifest=p.read(cls.out/'project/manifest.json')
        cls.spec=p.read(cls.out/'structural-inventory.json')

    def test_all_source_controls_and_twenty_crossings(self):
        loader=importlib.util.spec_from_file_location('r9_test_guard',p.ROOT/'tools/prefit_structural_guard_v1.py')
        guard=importlib.util.module_from_spec(loader);loader.loader.exec_module(guard)
        result=guard.source_inventory(self.out/'project',self.spec)
        self.assertEqual(result['findings'],[])
        self.assertEqual(len(result['transfers']),20)
        self.assertEqual(len(self.manifest['source_sha256']),55)
        # Earlier metadata-only preparation retained exact production bytes.
        old=p.read(self.out.parent/'physical-v1/project/manifest.json')
        self.assertEqual(old['source_sha256'],self.manifest['source_sha256'])

    def test_every_exception_anchor_even_registered_transfers(self):
        for transfer in self.spec['transfers']:
            for anchor in transfer.get('exception',{}).get('contract_anchors',[]):
                text=(self.out/'project'/anchor['source']).read_text()
                self.assertEqual(text.count(anchor['text']),1,(transfer['id'],anchor))

    def test_explicit_delta_and_no_parent_clock_claim(self):
        m=self.manifest['context_registered_error']
        self.assertEqual(m['joint_publication_delta'],[1,2])
        self.assertEqual(m['copy_cycles_extra_per_job'],1)
        self.assertTrue(m['full56_publication_owner_count_lease_check'])
        self.assertFalse(m['clock_or_area_claim'])
        params=self.manifest['core_parameters']
        self.assertEqual((params['EPOCH_SEED0'],params['EPOCH_SEED1']),(65534,42))
        self.assertEqual(params['ERROR_AGGREGATION_REGISTERED'],1)
        self.assertEqual(params['CANONICAL_C0_DIRECT'],1)


if __name__=='__main__':
    unittest.main()

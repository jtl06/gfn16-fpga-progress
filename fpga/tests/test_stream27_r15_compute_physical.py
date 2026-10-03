"""Pure source/inventory checks; no compiler, native job or timing claim."""
import unittest
from fpga.reference import stream27_r15_compute_physical as p

class PhysicalSource(unittest.TestCase):
    def test_exact_captured_sixty_and_compiled_parameters(self):
        role=p.ROOT/'results/throughput-20260929/trackS-r15-compute-native-v1/aw8-normal'
        m,files,spec,proof=p.build(role)
        full=p.read(role.parent/'full-normal/production-bundle.json')
        self.assertEqual(m['source_sha256'],full['generated_sha256'])
        self.assertEqual({n[4:]:p.sha(raw) for n,raw in files.items() if n.startswith('rtl/')},full['generated_sha256'])
        self.assertEqual(len(full['files']),60)
        self.assertEqual(m['compile_processors'],16)
        self.assertEqual(m['core_parameters'],dict(full['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42))
        self.assertEqual(proof['kwargs'],p.KWARGS)
        self.assertEqual(proof['fit_n'],65536)
        self.assertEqual(proof['native_n'],256)
        self.assertEqual(len(spec['transfers']),26)
        self.assertIn('unimplemented',m['label'])
        self.assertEqual(m['r15_flags']['PCIE_SHELL'],0)
        for transfer in spec['transfers']:
            for anchor in transfer.get('exception',{}).get('contract_anchors',[]):
                self.assertEqual(files[anchor['source']].decode().count(anchor['text']),1,(transfer['id'],anchor))

if __name__=='__main__':unittest.main()

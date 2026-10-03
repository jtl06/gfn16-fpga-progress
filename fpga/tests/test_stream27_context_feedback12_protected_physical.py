import unittest
from fpga.reference import stream27_context_feedback12_physical as p


class ProtectedFeedback12Physical(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out=p.ROOT/'results/throughput-20260929/trackS-c2-feedback12-protected-physical-v1/physical-12000-v1'
        cls.role=p.ROOT/'results/throughput-20260929/trackS-c2-feedback12-protected-native-v1/aw8-normal'
        cls.m,cls.files,cls.spec,cls.proof=p.build(cls.role,'s4-p16-c2-r12-protected-aw8-normal-q1-v1',lean_production=0)

    def test_source_and_compiled_parameters(self):
        full=p.read(self.role.parent/'full-normal/production-bundle.json')
        self.assertEqual(self.m['source_sha256'],full['generated_sha256'])
        self.assertEqual(self.m['core_parameters'],dict(full['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42))
        self.assertNotIn('LEAN_PRODUCTION',self.m['core_parameters'])
        self.assertEqual(self.m['core_parameters']['LEAN_PROGRESS_WATCHDOG'],0)
        self.assertEqual(self.proof['kwargs']['lean_production'],0)
        self.assertEqual(self.m,p.read(self.out/'project/manifest.json'))

    def test_all_protected_crossing_anchors(self):
        self.assertEqual(len(self.spec['transfers']),27)
        for t in self.spec['transfers']:
            for a in t.get('exception',{}).get('contract_anchors',[]):
                self.assertEqual(self.files[a['source']].decode().count(a['text']),1,(t['id'],a))
        text=p.encoded(self.spec).decode()
        self.assertNotIn('no full56',text)
        self.assertNotIn('Lean trusted-profile',text)
        self.assertIn('assign error=local_error || child_error || canon_error;',text)

    def test_baseline_transport_and_geometry(self):
        for k in ('CRT_TRANSPORT_REG','INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG'):
            self.assertEqual(self.m['core_parameters'][k],1)
        g=self.m['geometry']
        self.assertEqual((g['warm_interval'],g['first_digit'],g['carry_done'],g['sink_accept']),(8464,8462,12561,8419))
        self.assertEqual(len(self.m['source_sha256']),58)
        for name,raw in self.files.items():
            self.assertEqual((self.out/'project'/name).read_bytes(),raw)


if __name__=='__main__':unittest.main()

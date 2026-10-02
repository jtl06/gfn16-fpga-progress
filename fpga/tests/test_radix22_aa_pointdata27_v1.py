"""Pure source isolation and fault-contract tests; no HDL tool on Mac."""
import hashlib
from pathlib import Path
import unittest
from fpga.reference import radix22_aa_pointdata27_v1 as a
from fpga.reference import radix22_aa_fault_contract_v1 as f


class PointData27Tests(unittest.TestCase):
    def test_exact_RAM_only_isolation(self):
        parent=(a.ROOT/a.PARENT).read_text(); candidate=(a.ROOT/a.TARGET).read_text()
        self.assertEqual(candidate,a.source());self.assertEqual(candidate.replace(a.NEW,a.OLD),parent)
        self.assertIn('data_w[bank]>=P',candidate)
        for pin in ('[31:0] write_data','[LANES*32-1:0] vector_write_data','.normalization(normalization)',
                    'logic [31:0] point_lhs_q','data_destination[bank]<=data_q[bank]'):
            self.assertIn(pin,candidate)

    def test_arithmetic_or_check_mutation_rejects(self):
        raw=(a.ROOT/a.PARENT).read_bytes()
        for old,new in ((b'data_w[bank]>=P',b'data_w[bank][26:0]>=P'),(b'.P(P),.Q(Q)',b'.P(P),.Q(0)'),
                        (b'logic [31:0] point_lhs_q',b'logic [26:0] point_lhs_q')):
            with self.assertRaises(ValueError):a.source(raw.replace(old,new))

    def test_measured_not_already_pruned(self):
        r=a.audit();self.assertEqual(r['banks32'],128)
        self.assertEqual(len(r['protected_high_bit_register_sample']),15)
        self.assertTrue(r['sample_is_partial']);self.assertFalse(r['new_area_saving_measured'])

    def test_bench_source_and_exact_normal_counter(self):
        self.assertEqual((a.ROOT/a.CPP).read_text(),a.cpp_source())
        for field in range(3):
            m,files=a.role(5,field)
            self.assertEqual(m['build']['cpp_source'],a.CPP)
            self.assertIn(a.TARGET,m['build']['sv_sources']);self.assertNotIn(a.PARENT,m['build']['sv_sources'])
            self.assertIn('cycles=545',m['steps'][0]['expected_stdout'])
            self.assertEqual(m['steps'][1]['expected_returncode'],1)
            self.assertEqual(m['steps'][2]['expected_returncode'],0)
            self.assertEqual(m['aa_data27']['cycle_delta_source_prediction'],0)
            if field==0:self.assertEqual([x['expected_returncode'] for x in m['steps'][3:]],[-6,-6,-6])

    def fixture(self, reason='A10_NONCANONICAL_WRITE', kind='--high-bit'):
        engine=(a.ROOT/a.TARGET).read_text();ram=(a.ROOT/a.RAM).read_text()
        assets={'engine':engine,'ram':ram}
        cfg=dict(kind=kind,aw=5,field=104857601,engine_sha256=hashlib.sha256(engine.encode()).hexdigest(),ram_sha256=a.RAM_SHA)
        use='engine' if reason=='A10_NONCANONICAL_WRITE' else 'ram'
        name=Path(a.TARGET if use=='engine' else a.RAM).name
        line=next(i for i,x in enumerate(assets[use].splitlines(),1) if reason in x)
        top='TOP.genefer_a10_banked27_host16_engine_v1.child.memories[0]'+('.data_ram' if use=='ram' else '')
        word=0x08000001 if kind=='--bit27' else 0x80000001
        out=f'AA_DATA27_HIGHBIT kind={kind} word={word} aw=5 field=104857601\n'
        err=f'[0] %Error: /closed/{name}:{line}: Assertion failed in {top}: {reason}\n%Error: /closed/{name}:{line}: Verilog $stop\nAborting...\n'
        return out,err,cfg,assets

    def test_actual_signal_contract_and_wrong_incidents(self):
        for reason in ('A10_NONCANONICAL_WRITE','RAM residue write exceeds27 bits'):
            for kind in ('--high-bit','--bit27','--vector-high-bit'):
                out,err,cfg,assets=self.fixture(reason,kind)
                self.assertFalse(f.validate(out,err,-6,cfg,assets)['synthesized_hardware_admission_proved'])
        out,err,cfg,assets=self.fixture()
        for rc in (0,1,134,True):
            with self.assertRaises(ValueError):f.validate(out,err,rc,cfg,assets)
        for change in (err.replace('A10_NONCANONICAL_WRITE','A10_RAM_COLLISION'),err.replace('memories[0]','memories[1]'),err+'extra\n'):
            with self.assertRaises(ValueError):f.validate(out,change,-6,cfg,assets)

    def test_candidate_project_only_required_delta(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            result=a.project(Path(directory)/'candidate');p=Path(result['project'])
            old=a.ROOT/'results/throughput-20260929/a10-point-field-probe-v3/project-workers6'
            for name in ('probe.qpf','probe.sdc','run.tcl'):
                self.assertEqual((p/name).read_bytes(),(old/name).read_bytes())
            self.assertEqual(result['sources'],10)
            self.assertTrue(result['native_pending'])


if __name__=='__main__':unittest.main()

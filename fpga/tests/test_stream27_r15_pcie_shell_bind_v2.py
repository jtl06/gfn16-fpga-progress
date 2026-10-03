"""Actual generated-source closure checks, not HDL or vendor simulation."""
import hashlib
import json
import unittest
from unittest.mock import patch
from fpga.reference import stream27_r15_pcie_shell_bind_v2 as shell
from fpga.reference import stream27_r15_board_glue_v2 as old_board
from fpga.reference import stream27_r15_board_glue_v3 as board
from fpga.reference.stream27_r15_all_io_bind import prepare


class SourceClosure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent=prepare(65536,p=16,contexts=2,fixed_schedule=1,lean_build=1,
          progress_watchdog=1,storage_to_ram=1,direct_cold=1,pcie_shell=0)
        cls.bundle=shell.bind(cls.parent,pcie_shell=1)

    def test_off_and_literal_component(self):
        self.assertEqual(shell.bind(self.parent),self.parent)
        for name,raw in self.parent['files'].items():self.assertEqual(self.bundle['files'][name],raw)
        self.assertEqual(len(self.bundle['rtl_sources']),72)
        self.assertEqual(self.bundle['parameters'],{})
        self.assertEqual(self.bundle['r15_real_shell']['effective_parameters']['EPOCH_SEED0'],0)
        self.assertEqual(self.bundle['r15_real_shell']['effective_parameters']['EPOCH_SEED1'],0)

    def test_actual_vendor_and_guard_copy(self):
        d=self.bundle['r15_real_shell']
        self.assertEqual(len(d['vendor_sources']),345)
        self.assertEqual(len(d['qip_roots']),5)
        self.assertEqual(len(d['generated_custom_copies']),71)
        p=d['generated_custom_copies']['genefer_stream27_r15_dma_aperture_v1.sv']
        self.assertEqual(d['vendor_sources'][p],shell.GUARD_PIN)
        self.assertTrue(d['aperture_wiring']['registered_response_credit_only'])
        self.assertEqual(d['aperture_wiring']['minimum_downstream_response_edges'],1)
        self.assertFalse(d['vendor_simulation_ready'])
        self.assertFalse(d['fit_qualified'])

    def test_generated_hdl_and_constraints_exact_delta(self):
        prior=shell.ROOT/'results/throughput-20260929/r15-pcie-system-generation-v2-artifacts/full-collection.json'
        old={r['path']:r['sha256'] for r in json.loads(prior.read_bytes())['files']}
        new=self.bundle['r15_real_shell']['vendor_sources']
        self.assertEqual(set(old),set(new))
        changed_hdl=[p for p in old if p.endswith(('.sv','.v','.vhd')) and old[p]!=new[p]]
        self.assertEqual(len(changed_hdl),2)
        self.assertTrue(all(p.endswith('/genefer_stream27_r15_dma_aperture_v1.sv') for p in changed_hdl))
        self.assertTrue(all(new[p]==shell.GUARD_PIN for p in changed_hdl))
        for p in old:
            if p.endswith(('.qip','.sdc')):self.assertEqual(old[p],new[p])

    def test_identical_board_wiring_and_clocks(self):
        current,p=board.emit();old,_=old_board.emit()
        self.assertEqual(current,old)
        self.assertTrue(p['generated_top_byte_identical_to_prior'])
        self.assertEqual(len(p['ports']),243)
        d=self.bundle['r15_real_shell']
        self.assertEqual(d['clock_proof']['core_period_ns'],12)
        self.assertEqual(d['clock_proof']['board_input_hz'],100000000)
        self.assertEqual(d['clock_proof']['hip_application_hz'],250000000)

    def test_collection_and_guard_drift_refuse(self):
        with patch.object(shell,'COLLECTION_PIN','0'*64):
            with self.assertRaisesRegex(ValueError,'COLLECTION_PIN'):shell.observed_sources()
        with patch.object(shell,'guard_source',return_value=b'wrong'):
            with self.assertRaisesRegex(ValueError,'REGISTERED_CREDIT'):shell.aperture_wiring()

    def test_actual_project_controls_and_projection(self):
        p=shell.ROOT/'results/throughput-20260929/trackS-r15-real-pcie-shell-v2/physical-source-v4/project'
        m=json.loads((p/'manifest.json').read_bytes());d=m['r15_real_shell']
        self.assertEqual(m['physical_mode'],'r15_real_shell_v1')
        self.assertEqual(len(d['vendor_sources']),335)
        self.assertEqual(len(d['omitted_generation_state']),10)
        for name,pin in m['control_sha256'].items():
            self.assertEqual(hashlib.sha256((p/name).read_bytes()).hexdigest(),pin)
        self.assertEqual(json.loads((p/'rtl/proofs/real-shell.json').read_bytes()),d)
        q=(p/'probe.qsf').read_text()
        self.assertEqual(q.count('-name QIP_FILE '),5)
        self.assertNotIn('-name VIRTUAL_PIN',q)
        self.assertNotIn('set_parameter',q)

if __name__=='__main__':unittest.main()

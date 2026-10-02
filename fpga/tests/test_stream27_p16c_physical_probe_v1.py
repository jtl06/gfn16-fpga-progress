import hashlib
from pathlib import Path
import tempfile
import unittest

from fpga.reference.stream27_p16c_physical_probe_v1 import compile_probe,prepare,prepare_small_gate,verify_project,small_numeric_square
from fpga.reference.stream_ntt_model import FIELDS


class P16CSourceTests(unittest.TestCase):
    def test_lazy_composed_square_matches_direct_schoolbook(self):
        for n,p in ((32,8),(64,16),(256,16)):
            for field,(prime,_) in enumerate(FIELDS):
                vectors=[[0]*n,[(i*i*37+i+prime-1)%prime for i in range(n)],
                         [prime-1 if i%3 else 1 for i in range(n)]]
                for values in vectors:
                    actual=small_numeric_square(values,p,field);expected=[0]*n
                    for a in range(n):
                        for b in range(n):
                            expected[(a+b)%n]=(expected[(a+b)%n]+values[a]*values[b]*(1 if a+b<n else -1))%prime
                    self.assertEqual(actual,expected)
        with self.assertRaisesRegex(ValueError,'N256_LIMIT'):small_numeric_square([0]*512)

    def test_real_source_counts_and_canonical_consumer_boundaries(self):
        b=compile_probe(65536,allow_full_constants=True)
        self.assertEqual(len(b['files']),13);self.assertEqual(b['geometry']['token_total_bits'],39)
        self.assertEqual(b['exact_changes']['interior_lazy_BF'],248)
        self.assertEqual(b['exact_changes']['canonical_final_GS_pairs'],8)
        self.assertEqual(b['exact_changes']['upper_normalizers'],8)
        self.assertEqual(b['exact_changes']['net_standalone_multiplier_removal'],24)
        gs=next(text for name,text in b['generated_files'].items() if name.startswith('genefer_stream28_merged_gs'))
        self.assertEqual(gs.count('genefer_stream27_merged_final_gs_pair_v1 #'),8)
        self.assertEqual(gs.count('genefer_ntt_lazy28_butterfly_v1 #'),120)
        self.assertIn('canonical_u0',gs);self.assertIn('canonical_v0',gs)
        top=b['files'][b['top']+'.sv'];self.assertIn('data_in(canonical_spectrum)',top)
        self.assertNotIn('28x28',top)
        for source in b['generated_files'].values():self.assertNotIn('$readmem',source)
        self.assertFalse(b['physical_fit_qualified']);self.assertFalse(b['full_N_numeric_NTT_performed'])

    def test_registered_cones_and_exact_s_m1_binding(self):
        b=compile_probe(64)
        cell=b['files']['genefer_stream27_mdc_commutator_sm1_registered_v1.sv']
        self.assertIn('advance = rst_n && !quarantine && !out_error;',cell)
        self.assertEqual(cell.count('genefer_stream27_mdc_fifo_smallreg_v1 #'),2)
        for name,text in b['generated_files'].items():
            self.assertNotIn('!fault_pending',text);self.assertNotIn('!cadence_bad',text)
            if name.startswith('genefer_stream28_merged_'):
                self.assertIn('wire stop=quarantine || aggregate_error;',text)
                self.assertIn('else if(!stop && (|stage_pending))aggregate_error<=1;',text)
        self.assertEqual(b['calendar']['first_physical_output'],85)
        self.assertEqual(b['calendar']['first_terminal_sample'],86)

    def test_portable_project_closure_and_drift_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'stage';r=prepare(dest,n=64)
            project=dest/'project';self.assertEqual(verify_project(project)['sources'],13)
            self.assertFalse(r['full_N_numeric_NTT_performed'])
            self.assertEqual(r['period_ns'],10);self.assertEqual(r['seed'],1)
            qsf=(project/'probe.qsf').read_text()
            self.assertIn('set_parameter -name CONTEXTS 1',qsf)
            with (project/'probe.sdc').open('a') as stream:stream.write('\n# test tamper\n')
            with self.assertRaisesRegex(ValueError,'P16C_PROJECT_DRIFT'):verify_project(project)

    def test_full_N_memory_and_cost_ledger_no_free_small_registers(self):
        b=compile_probe(65536,allow_full_constants=True);r=b['resource_basis']
        self.assertEqual(r['DSP_proxy'],280);self.assertEqual(r['root_M20K_proxy'],228)
        self.assertEqual(r['IO_root_M20K'],0);self.assertGreater(r['delay_M20K_proxy'],0)
        self.assertEqual(r['short_FIFO_storage_bits'],78624)
        self.assertGreater(r['components']['short_delay_registers']['ALM_planning_proxy'],19000)
        self.assertGreater(r['included_noncontrol_ALM_proxy'],100000)
        self.assertFalse(r['physical_inference_qualified'])
        self.assertIn('UNMEASURED',r['components']['lazy_interior_pairs']['basis'])

    def test_small_native_gate_is_closed_bounded_lint_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)/'gate';gate=prepare_small_gate(d)
            self.assertEqual(gate['n'],64);self.assertLess(gate['planned_probe_edges'],gate['maximum_probe_edges'])
            self.assertEqual([stage['kind'] for stage in gate['stages']],['lint','build','probe'])
            self.assertIn('--lint-only',gate['stages'][0]['argv'])
            self.assertIn('-Wall',gate['stages'][0]['argv']);self.assertIn('-Wall',gate['stages'][1]['argv'])
            self.assertNotIn('-Wno-fatal',str(gate))
            self.assertEqual(hashlib.sha256((d/'stream27_p16c_aw6_v1.cpp').read_bytes()).hexdigest(),gate['benchmark_sha256'])
            self.assertEqual(verify_project(d/'project')['sources'],13)


if __name__=='__main__':unittest.main()

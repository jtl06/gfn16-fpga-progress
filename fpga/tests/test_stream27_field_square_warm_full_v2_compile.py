import hashlib
from pathlib import Path
import unittest

from fpga.reference.stream27_field_square_warm_full_v1_compile import prepare as parent
from fpga.reference.stream27_field_square_warm_full_v2_compile import prepare


ROOT=Path(__file__).resolve().parents[1]


class RegisteredSourceTests(unittest.TestCase):
    def test_n256_and_full_constants_sources_closed(self):
        for n in (256,65536):
            b=prepare(n,allow_full_constants=n>256)
            self.assertEqual(len(b['files']),7);self.assertEqual(len(b['rtl_sources']),16)
            for path,pin in b['source_sha256'].items():
                self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),pin)
            for path,pin in b['generated_sha256'].items():
                self.assertEqual(hashlib.sha256(b['files'][path].encode()).hexdigest(),pin)
            self.assertEqual(b['geometry'],parent(n,allow_full_constants=n>256)['geometry'])
            self.assertEqual(b['CONTEXTS_supported'],[1]);self.assertFalse(b['native_run_performed'])

    def test_pending_never_gates_work(self):
        b=prepare(256);top=b['files'][b['top']+'.sv']
        for bad in ('!fault_pending','!admission_bad','!join_bad','!epoch_pending','!digit_admission_bad'):
            self.assertNotIn(bad,top)
        self.assertIn('assign out_error=controller_error;',top)
        self.assertIn('wire term_join_valid=term_slot && term_output_row==addA_row',top)
        self.assertIn('if(!stop)begin',top)
        self.assertNotIn('busy',top);self.assertNotIn('active_epoch',top)
        arithmetic=b['files']['genefer_stream27_row_arithmetic_v4_registered.sv']
        self.assertNotIn('&& !fault_pending',arithmetic)
        for name,text in b['files'].items():
            if name.startswith(('genefer_stream27_dif_','genefer_stream27_dit_')):
                self.assertNotIn('&& !cadence_bad',text)
                self.assertNotIn('genefer_stream27_mdc_commutator_slots_v2',text)
                self.assertIn('wire accept=row_slot && !stop && !local_fault;',text)

    def test_lookup_cone_and_intrinsic_commit(self):
        p=(ROOT/'rtl/kernel/genefer_stream27_epoch_protocol_v5.sv').read_text()
        lookup=p.split('always_comb begin : lookup_values',1)[1].split('always_comb begin : protocol_checks',1)[0]
        for signal in ('external_fault_pending','fault_pending','correction_accept','frame_accept','stop','quarantine'):
            self.assertNotIn(signal,lookup)
        commit=p.split('assign commit_enable=',1)[1].split(';',1)[0]
        self.assertNotIn('fault_pending',commit);self.assertNotIn('bad',commit)
        self.assertIn('sink_generation==live_generation',commit)
        self.assertIn('sink_generation==generation[sink_index]',commit)
        self.assertIn('sink_frame_start==(sink_age[sink_index]==0)',commit)
        self.assertIn("sink_matches!=2'b11",commit)
        pointwise=p.split('assign pointwise_accept=',1)[1].split(';',1)[0]
        self.assertIn("pw_matches!=2'b11",pointwise)
        for signal in ('frame_accept','correction_accept','pointwise_accept','commit_enable'):
            self.assertIn('assign '+signal+'=rst_n &&',p)

    def test_term_and_root_physical_contract(self):
        term=(ROOT/'rtl/kernel/genefer_stream27_term_context_v2.sv').read_text()
        for line in term.splitlines():
            if 'wire product_accept=' in line or 'term_slot<=' in line:
                self.assertNotIn('local_bad',line);self.assertNotIn('fault_pending',line)
        self.assertIn('if(product_slot && bank_owner[prod_bank]==product_owner)',term)
        self.assertIn('if(bypass)begin current_term=product_data',term)
        b=prepare(256);roots=next(text for name,text in b['files'].items() if name.startswith('genefer_stream27_term_roots_'))
        self.assertEqual(roots.count('prefetched<=roots['),1)
        self.assertIn('prefetched<=roots[read_address]',roots)
        cell=(ROOT/'rtl/kernel/genefer_stream27_mdc_commutator_slots_v3_registered.sv').read_text()
        self.assertIn('advance = rst_n && !quarantine && !out_error;',cell)


if __name__=='__main__':unittest.main()

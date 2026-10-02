import unittest
from pathlib import Path

from fpga.reference.stream27_field_square_warm_v4_compile import (
    prepare,dependency_contract,comb_blocks,PROTOCOL,TOP)
from fpga.reference.stream27_field_square_warm_v3_compile import prepare as parent_bundle
from fpga.reference.stream27_field_square_warm_v3_compile import replay_small_overlap
from fpga.reference.stream27_field_square_oracle import image_cases,residues


class WarmFieldCompositionV4(unittest.TestCase):
    def test_exact_additive_successor_no_arithmetic_or_calendar_delta(self):
        old=parent_bundle();new=prepare();old_files=dict(old['files']);new_files=dict(new['files'])
        old_source=old_files.pop(old['top']+'.sv');new_source=new_files.pop(TOP+'.sv')
        self.assertEqual(old_files,new_files)
        self.assertEqual(old_source.replace(old['top'],TOP).replace(
            'genefer_stream27_epoch_protocol_v3','genefer_stream27_epoch_protocol_v4'),new_source)
        for key in ('first_physical_output','first_commit','warm_interval','next_correction_accept',
                    'next_cache_capture','next_pointwise_accept','epoch_RAM_bits_added'):
            self.assertEqual(old[key],new[key])
        self.assertNotIn('rtl/kernel/genefer_stream27_epoch_protocol_v3.sv',new['rtl_sources'])
        self.assertIn(PROTOCOL,new['rtl_sources'])
        self.assertFalse(new['native_run_performed'])

    def test_procedural_dependency_guard_detects_actual_v3_and_reintroduced_loop(self):
        p=prepare();s=p['files'][TOP+'.sv'];root=Path(__file__).resolve().parents[1]
        protocol=(root/PROTOCOL).read_text();v3=(root/'rtl/kernel/genefer_stream27_epoch_protocol_v3.sv').read_text()
        self.assertEqual(len(comb_blocks(protocol)),2)
        self.assertEqual(dependency_contract(protocol,s)['added_edges'],0)
        with self.assertRaisesRegex(ValueError,'WARM_LOOKUP_FAULT_DEPENDENCY'):
            dependency_contract(v3,s)
        with self.assertRaisesRegex(ValueError,'WARM_LOOKUP_FAULT_DEPENDENCY'):
            dependency_contract(protocol.replace("correction_base='0;","correction_base=external_fault_pending ? 0 : 0;"),s)
        with self.assertRaisesRegex(ValueError,'WARM_CANDIDATE_FEEDBACK'):
            dependency_contract(protocol,s.replace('digit_admission_bad=','digit_admission_bad=epoch_pending || ',1))

    def test_sequential_update_body_is_byte_exact_parent(self):
        root=Path(__file__).resolve().parents[1]
        old=(root/'rtl/kernel/genefer_stream27_epoch_protocol_v3.sv').read_text()
        new=(root/PROTOCOL).read_text()
        self.assertEqual(old[old.index('    always_ff'):],new[new.index('    always_ff'):])
        for expression in ('out_error || (!stop && (bad || external_fault_pending))',
                           'correction_valid && corr_found && !stop && !fault_pending',
                           'pointwise_slot && pw_found && !stop && !fault_pending'):
            self.assertIn(expression,new)

    def test_small_exact_two_cache_oracle_unchanged(self):
        images=(image_cases()[9][1],image_cases()[3][1])
        for starts,corrections in (((0,20),(0,25)),((0,4),(0,4)),((0,4),(4,9))):
            result=replay_small_overlap(images,starts,corrections)
            self.assertEqual(result['output'],tuple(residues(image) for image in images))
            self.assertEqual(result['peak_owners'],2)
            self.assertFalse(result['full_N_numeric_NTT_performed'])


if __name__=='__main__':unittest.main()

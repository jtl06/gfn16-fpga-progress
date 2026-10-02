"""Source-only pinned bindings and independent finite bench calendar.

This does not elaborate HDL or compile/execute the native bench on the Mac.
"""
import hashlib
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
PINS={
 'rtl/kernel/genefer_track_a4_host_word_v1.sv':'255c65ed340a391e9dd43c09fbc2d6299c5fb67e9b76360e9364a8af175e62cf',
 'rtl/kernel/genefer_track_a4_host_shell_v2.sv':'f62dab985ebb34f760e9d568b835ce17bc52fd37fdd3b71c0f0a99ae182058da',
 'rtl/kernel/genefer_track_a4_digit_image_v1.sv':'606e807d3a845697038deec169ef5b8aea572c85e4d2bf622444cd03700372f6',
 'rtl/kernel/genefer_track_a4_canonical_controller_v2.sv':'f8d8e523ac934dfd3df2b697fe03be14250a584da2aaca761779feaf03f3fbba',
 'rtl/kernel/genefer_track_a4_control_fsm_v2.sv':'343d392e1b69f4230e3a59029aafd3355e8139b502589ff56c7b1fbe1bf49d03',
 'rtl/kernel/genefer_anext_cancel_host_word_v1.sv':'6f2e705eb8e039e6a7b1b614223d58bc836d9ccd5ca9221cd4e3628d30202cb6',
 'rtl/kernel/genefer_anext_cancel_digit_image_v1.sv':'ab3c84b08d522ebcd8e1b882f20c51f35e3ae817918f70299b4a0f1bc66ada09',
 'rtl/kernel/genefer_anext_cancel_host_shell_v1.sv':'1f5d878f6ffbdb9d745b36ed5926a7ee1a4d417ea8b9dee418b8991c70e220c7',
}

def counts(aw):
    if aw not in (5,8):raise ValueError('bounded AW5/AW8')
    n=1<<aw;t=n//16
    return dict(commands=7*n+29,readbacks=n+12,error_responses=4,explicit_hold_checks=14*n+61,
        host_cases=6,cancel_seams=4,ram_words=17*n,image_read_words=28*t+192,
        image_faults=7,image_cancels=8,image_ram_words=20*n,ticks=67*n+5*t+1139,max_latency=max(100,2*n+12))

def footer(aw):return f'ANEXT_CANCEL_HOST_PAIR_PASS aw={aw} '+' '.join(f'{k}={v}' for k,v in counts(aw).items())+'\n'

class CancelHostSource(unittest.TestCase):
    def test_exact_kernel_pins(self):
        for name,pin in PINS.items():self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),pin,name)

    def test_real_children_ram_and_actual_caller_qualification(self):
        text=(ROOT/'rtl/tb/genefer_anext_cancel_host_pair_v1.sv').read_text()
        for module in ('genefer_track_a4_host_shell_v2','genefer_anext_cancel_host_shell_v1',
                       'genefer_track_a4_digit_image_v1','genefer_anext_cancel_digit_image_v1'):
            self.assertIn(module+' #(.AW(AW))',text)
        for instance in ('old','actual'):
            for enable in ('compute_configure','compute_clear_image','compute_read_en','compute_write_en','compute_boundary_commit'):
                self.assertIn(f'.{enable}({enable} && !{instance}.square_cancel)',text)
            self.assertIn(instance+'.image.banks[b].ram.mem[peek_offset]',text)
        for enable in ('configure','read_en','write_en','clear_corrections','set_minus_one','boundary_commit'):
            self.assertIn(f'.{enable}(i_{enable} && !i_cancel)',text)
            self.assertIn(f'.{enable}(i_{enable})',text)
        self.assertIn('.cancel(i_cancel)',text)
        self.assertIn('actual.host_word.mem_write_select',text)
        self.assertIn('if(shadow0_valid[b])',text);self.assertIn('if(i_read_valid && i_read_mask_out[b])',text)

    def test_independent_oracle_and_fault_seam(self):
        text=(ROOT/'rtl/tb/anext_cancel_host_pair_v1.cpp').read_text()
        for marker in ('x/image.base,r=x%image.base','int32_t(image.raw[j])','ANEXT_CANCEL_HOST_E2',
                       'ANEXT_CANCEL_SIGNED33_READ','ANEXT_CANCEL_IMAGE_READ_E0',
                       'ANEXT_CANCEL_SEAM_PENDING_ACCESS','ANEXT_CANCEL_NO_HOST_FALLBACK_OR_COMMIT',
                       'ANEXT_CANCEL_LATER_FAULT_HELD_SUCCESS','ANEXT_CANCEL_PRIOR_COMMIT_NOT_ROLLED_BACK',
                       'ANEXT_CANCEL_IMAGE_SAME_EDGE_KILL','ANEXT_CANCEL_IMAGE_PUBLICATION_AND_SHADOW_FREEZE',
                       'ANEXT_CANCEL_RESET_ELIGIBILITY'):
            self.assertIn(marker,text)
        self.assertNotIn('boost/',text);self.assertNotIn('gmp',text)
        baseline=text.index('old==actual && actual==expected[b*T+row]')
        mutant=text.index('actual==(expected[0]^1u)')
        self.assertLess(baseline,mutant)
        self.assertIn('ANEXT_CANCEL_HOST_NEGATIVE_ORACLE_REJECT',text)
        self.assertIn('context.threads(1)',text);self.assertIn('d.threads()==1',text)

    def test_independent_command_edge_calendar(self):
        # Every acknowledged command adds accept1 + explicit hold2 + ack1.
        # Setup child E97 + two START/WAIT edges + reload cancel defer =100.
        # Host E2 + two START/WAIT edges =4. Last load/one-pass write waits
        # N+9; two-pass wrap write2N+12; exceptional lastloadN+T+10.
        for aw in (5,8):
            n=1<<aw;t=n//16;command_counts=[2*n+9,n+5,n+6,n+3,n+3,n+3]
            waits=[13*n+251,6*n+t+127,5*n+214,5*n+113,5*n+112,5*n+116]
            extra=[0,0,13,17,8,8] # manual canceled edge/quiet tail, held later fault.
            host_edges=sum(4*c+w+x for c,w,x in zip(command_counts,waits,extra))
            initial_reset=2;standalone_edges=4*t+42
            self.assertEqual(sum(command_counts),counts(aw)['commands'])
            self.assertEqual(host_edges+initial_reset+standalone_edges,counts(aw)['ticks'])
            self.assertEqual(counts(aw)['max_latency'],100 if aw==5 else 524)
        self.assertEqual(counts(5)['ticks'],3293);self.assertEqual(counts(8)['ticks'],18371)

    def test_exact_footer_contract(self):
        self.assertEqual(footer(5),'ANEXT_CANCEL_HOST_PAIR_PASS aw=5 commands=253 readbacks=44 error_responses=4 explicit_hold_checks=509 host_cases=6 cancel_seams=4 ram_words=544 image_read_words=248 image_faults=7 image_cancels=8 image_ram_words=640 ticks=3293 max_latency=100\n')
        self.assertEqual(footer(8),'ANEXT_CANCEL_HOST_PAIR_PASS aw=8 commands=1821 readbacks=268 error_responses=4 explicit_hold_checks=3645 host_cases=6 cancel_seams=4 ram_words=4352 image_read_words=640 image_faults=7 image_cancels=8 image_ram_words=5120 ticks=18371 max_latency=524\n')
        with self.assertRaises(ValueError):counts(16)

if __name__=='__main__':unittest.main()

"""Pure source/constant/calendar tests; no HDL/native execution."""
from pathlib import Path
import json
import tempfile
import unittest

from fpga.reference import merged_stream27_root_compile_v1 as compiler
from fpga.reference import merged_stream27_model_v1 as model
from fpga.reference import merged_negacyclic27_model as arithmetic


class MergedRootCompilerTests(unittest.TestCase):
    def test_embedded_source_exact_root_init_and_layout_hooks(self):
        for p in (8,16):
            for field in (0,1,2):
                bundle=compiler.compile_roots(32,p,field)
                library=bundle['files'][bundle['compiled_sv_files'][0]]
                self.assertNotIn('$readmemh',library)
                self.assertEqual(library.count('module merged_stream27_root_'),10)
                for entry in bundle['modules']:
                    self.assertIn('module '+entry['module']+' #(',library)
                    self.assertIn(f"parameter int WIDTH={entry['width']},",library)
                    if entry['file']:
                        words=[int(x,16) for x in bundle['files'][entry['file']].splitlines()]
                        self.assertEqual(len(words),entry['depth'])
                        for row,word in enumerate(words):
                            self.assertIn(f"roots[{row}]={entry['width']}'h{word:0{(entry['width']+3)//4}x};",library)
                self.assertEqual(bundle['final_upper_scale'], arithmetic.normalization_constant(32,arithmetic.FIELDS[field]))
                self.assertEqual(bundle['final_normalization_extra_sparse_pipes'],p//2)
                self.assertFalse(bundle['lazy2P_supported'])

    def test_compact_next_row_prefetch_dense_cancel_and_reset_calendar(self):
        for p in (8,16):
            for inverse in (False,True):
                plan=model.topology(256,p,inverse=inverse)
                for spec in plan['stages']:
                    stage=spec['stage']
                    words=[model.packed_root_word(plan,stage,a,0,normalized_final=True)
                           for a in range(1<<spec['address_bits'])]
                    current=0;prefetched=None
                    for frame in range(3):
                        for row in range(plan['frame_ticks']):
                            start=row==0
                            # context_enabled/generation are deliberately irrelevant to occupied rows.
                            canceled=frame==1 and row>=2
                            actual=words[0] if start or not spec['address_bits'] else prefetched
                            expected=words[model.root_address(plan,stage,row)]
                            self.assertEqual(actual,expected)
                            following=(1 if start else current+1)%plan['frame_ticks']
                            prefetched=words[model.root_address(plan,stage,following)]
                            current=following
                            if canceled:self.assertGreaterEqual(row,2)
                    # Reset does not clear the RAM/read output; first new row must bypass stale q.
                    current=0
                    self.assertEqual(words[0],model.packed_root_word(plan,stage,0,0,normalized_final=True))

    def test_final_parallel_GS_branch_source_and_registered_edge_ledger(self):
        source=(compiler.ROOT/compiler.FINAL_HELPER).read_text()
        self.assertIn(".dif(1'b1)",source)
        self.assertIn('.lhs(sum_reduced),.rhs(UPPER_SCALE)',source)
        self.assertIn('upper_valid_delay<={upper_valid_delay[0],upper_valid};',source)
        self.assertIn('if(upper_valid_delay[0])upper_delay[1]<=upper_delay[0];',source)
        self.assertIn('if(lower_valid!=upper_valid_delay[1])out_error<=1;',source)
        accepted=(0,1,3,7,8)
        # Native BF5 and sparseMul3 are source-bound existing contracts;
        # multiplier output at k+3 is sampled at k+4, then transported at k+5.
        lower_edges=[k+5 for k in accepted]
        upper_edges=[k+3+2 for k in accepted]
        self.assertEqual(upper_edges,lower_edges)
        self.assertNotEqual([k+3+1 for k in accepted],lower_edges)
        f=arithmetic.FIELDS[0];scale=arithmetic.normalization_constant(32,f)
        psi=arithmetic.psi_for(32,f);lower_root=pow(psi,-16,f.p)*scale%f.p
        for u,v in ((0,0),(1,f.p-1),(f.p-1,f.p-1),(271,991)):
            self.assertEqual(f.mont((u+v)%f.p,scale), (u+v)*scale*pow(arithmetic.RADIX,-1,f.p)%f.p)
            self.assertEqual(f.mont((u-v)%f.p,lower_root), (u-v)*lower_root*pow(arithmetic.RADIX,-1,f.p)%f.p)

    def test_root_helper_contains_only_physical_slot_counter_no_eligibility(self):
        source=(compiler.ROOT/compiler.ROOT_HELPER).read_text()
        self.assertIn('following_address[bit_index]=following_row[ROW_BIT]',source)
        self.assertIn('if(rst_n && in_slot_valid)prefetched<=roots[following_address];',source)
        self.assertIn('else if(in_slot_valid)current_row<=following_row;',source)
        self.assertNotIn('context_enabled',source)
        self.assertNotIn('live_generation',source)

    def test_fresh_source_only_preparation_and_no_full_numeric_transform(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source'
            report=compiler.prepare(path,32,16,1)
            self.assertFalse(report['full_N_numeric_NTT_performed'])
            self.assertFalse(report['promotion_allowed'])
            self.assertEqual(json.loads((path/'manifest.json').read_text()),report)
            for name,digest in report['generated_sha256'].items():
                self.assertEqual(compiler.sha((path/name).read_bytes()),digest)
            with self.assertRaisesRegex(ValueError,'FRESH_OUTPUT'):
                compiler.prepare(path,32,16,1)


if __name__=='__main__':
    unittest.main()

import copy
import re
import unittest
from fpga.reference import stream27_context_storage_combo_bind as combo


class ComboTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parents = {n: combo.prepare(n) for n in combo.CAPTURES}
        cls.candidates = {n: combo.prepare(n, p=16, contexts=2, enabled=1) for n in combo.CAPTURES}

    def test_default_exact_and_closed_geometry(self):
        for n,parent in self.parents.items():
            self.assertEqual(combo.bind(parent), parent)
            self.assertIsNot(combo.bind(parent)['files'], parent['files'])
        with self.assertRaisesRegex(ValueError, 'AW5_UNSUPPORTED'):
            combo.prepare(32, enabled=1)
        for flag in (True,2,-1):
            with self.assertRaises(ValueError):
                combo.bind(self.parents[256],enabled=flag)
        bad=copy.deepcopy(self.parents[256]);bad['files'][bad['top']+'.sv']+='// mutation\n'
        with self.assertRaisesRegex(ValueError,'EXACT_PARENT'):
            combo.bind(bad,enabled=1)

    def test_zero_public_calendar_and_exact_requested_roster(self):
        for n,b in self.candidates.items():
            p=self.parents[n]
            self.assertEqual(b['geometry'],p['geometry'])
            self.assertEqual(b['parameters'],p['parameters'])
            self.assertEqual(b['two_context_schedule'],p['two_context_schedule']) if 'two_context_schedule' in p else None
            self.assertEqual(len(b['files']),53)
            self.assertEqual(b['geometry']['warm_interval'],212 if n==256 else 8459)
            self.assertEqual(b['context_storage_combo']['roster'],
                ['storage2','packed_delays','root_weight_retime','term_payload_lookahead'])
            self.assertNotIn('TERM_SELECT_TOKEN',b['parameters'])
            self.assertNotIn('FINAL_GS_INPUTREG',b['parameters'])
            self.assertEqual(b['context_storage_combo']['logical_leases'],4)
            self.assertEqual(b['context_storage_combo']['full_term_owner_bits'],27)

    def test_live_protocol_authority_and_term_state_literal(self):
        for n,b in self.candidates.items():
            p=self.parents[n]
            old=p['files'][combo.PROTOCOL+'.sv'];new=b['files'][combo.NEW_PROTOCOL+'.sv']
            # All registered owner/valid/ready updates and original validation
            # are untouched; only independent future payload lookup is added.
            for marker in (' always_comb begin: lookup_values',' always_comb begin: protocol_checks',
                           ' always_ff @(posedge clk or negedge rst_n)begin'):
                a=old.index(marker);z=old.index('\n end',a)+len('\n end')
                self.assertIn(old[a:z],new)
            old=p['files'][combo.TERM+'.sv'];new=b['files'][combo.NEW_TERM+'.sv']
            for marker in ('    always_comb begin : validate_calendar',
                           '    always_ff @(posedge clk or negedge rst_n)begin'):
                a=old.index(marker);z=old.index('\n    end',a)+len('\n    end')
                self.assertIn(old[a:z],new)
            for anchor in ('wire bypass=product_slot && product_owner==pointwise_owner && product_row==pointwise_row;',
                           'wire product_accept=(seed_slot || update_slot) && !stop;',
                           'assign cache_ready=product_slot &&',
                           'if(product_slot && bank_owner[prod_bank]==product_owner)begin'):
                self.assertIn(anchor,new)
            self.assertIn('pointwise_payload_owner_next={2\'(i),owner[i],epoch[i],generation[i]};',
                          b['files'][combo.NEW_PROTOCOL+'.sv'])

    def test_all_three_root_bf_cohorts_and_compiled_closure(self):
        for n,b in self.candidates.items():
            aw=n.bit_length()-1
            self.assertEqual(b['context_storage_combo']['root_retime']['root_modules'],3*(2*aw-1))
            self.assertEqual(b['context_storage_combo']['root_retime']['lazy_instances'],3*(2*aw-1)*8)
            text=re.sub(r'//[^\n]*|/\*.*?\*/','','\n'.join(b['files'].values()),flags=re.S)
            definitions=dict(re.findall(r'\bmodule\s+(\w+)\b(.*?)\bendmodule\b',text,flags=re.S))
            pending=[b['top']];seen=set()
            while pending:
                name=pending.pop()
                if name in seen:continue
                self.assertIn(name,definitions);seen.add(name)
                pending+=re.findall(r'\b((?:genefer_|merged_stream27_)\w+)\s+(?:#\([^;]*?\)\s+)?\w+\s*\(',definitions[name])
            self.assertIn(combo.NEW_TERM,seen)
            self.assertIn(combo.NEW_PROTOCOL,seen)
            self.assertIn(combo.roots.NEW_BF,seen)
            self.assertIn(combo.packed.NEW,seen)
            self.assertEqual(b['generated_sha256'],{name:combo.sha(value) for name,value in b['files'].items()})

    def test_same_new_generic_leaves_small_full_and_full_coefficients_preserved(self):
        small,full=self.candidates[256],self.candidates[65536]
        for name in (combo.NEW_TERM+'.sv',combo.NEW_PROTOCOL+'.sv',combo.roots.NEW_BF+'.sv',combo.packed.NEW+'.sv'):
            self.assertEqual(small['files'][name],full['files'][name])
        for n,b in self.candidates.items():
            p=self.parents[n]
            for name in ('genefer_crt3_27_mont_pipe.sv','genefer_div_recip_precision.sv',
                         'genefer_stream27_blockcarry_lane_param_v1.sv','genefer_stream27_canonical_image_pipe_v1.sv',
                         'genefer_stream27_montgomery_factored_v1.sv','genefer_stream27_merged_final_gs_pair_v1.sv'):
                self.assertEqual(b['files'][name],p['files'][name])
            for name in p['files']:
                if name.startswith('merged_stream27_root_library_'):
                    # ROM scalar literals/arrays and UPPER_SCALE are identical.
                    self.assertEqual(re.findall(r"\d+'[sS]?[dDhHbB][0-9a-fA-F_]+",p['files'][name]),
                                     re.findall(r"\d+'[sS]?[dDhHbB][0-9a-fA-F_]+",b['files'][name]))


if __name__=='__main__':unittest.main()

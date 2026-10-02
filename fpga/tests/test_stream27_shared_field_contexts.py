import unittest
from fpga.reference import stream27_shared_field_contexts as core
from fpga.reference import stream27_shared_field_flags as parent


class SourceTests(unittest.TestCase):
    def test_single_context_exact(self):
        self.assertEqual(core.prepare(32,8,0),parent.prepare(32,8,0))

    def test_four_banks_and_full_main_owner(self):
        for n,p in ((32,8),(256,8),(32,16),(256,16)):
            b=core.prepare(n,p,0,contexts=2)
            s=b['files'][b['top']+'.sv']
            self.assertIn('.CONTEXTS(2),.BANKS(4)',s)
            self.assertIn('A_table[0:3]',s)
            self.assertIn('B_table[0:3]',s)
            self.assertIn('.pointwise_epoch_in(fwd_generation[23:8])',s)
            self.assertIn('.sink_epoch_in(out_epoch)',s)
            self.assertNotIn('protocol_pw_epoch[0]',s)
            self.assertNotIn('seed_owner[8]',s)
            self.assertIn('.GEN_W(25)) forward_transform',s)
            self.assertIn('.GEN_W(25)) inverse_transform',s)
            term=next(text for name,text in b['files'].items()
                      if name.startswith('genefer_stream27_term_context_param_'))
            self.assertIn('context_data[0:3][0:3]',term)
            self.assertIn('TAG_W=27+ROW_W',term)
            self.assertIn('pw_bank=pointwise_owner[26:25]',term)
            square=next(text for name,text in b['files'].items()
                        if name.startswith('genefer_stream27_square_'))
            self.assertIn(f'logic [{p-1}:0] lane_valid;',square)
            self.assertIn('[GEN_W-1:0] generation_pipe',square)
            self.assertEqual(b['geometry']['warm_interval'],parent.prepare(n,p,0)['geometry']['warm_interval'])


if __name__=='__main__':unittest.main()

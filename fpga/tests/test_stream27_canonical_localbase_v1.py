"""Small scalar and source checks only; no HDL/fullN computation."""
import re
import unittest
from fpga.reference import stream27_canonical_localbase_v1 as s


class LocalBase(unittest.TestCase):
    def test_zero_extra_cycles_and_complete_normal_reference(self):
        for aw,p in ((5,8),(8,8),(5,16),(8,16)):
            m,files=s.role(aw,p)
            self.assertEqual(m['build']['sv_sources'],[s.donor.RAM,s.SV])
            self.assertEqual(m['localbase']['added_cycles'],0)
            self.assertEqual(m['localbase']['normal_cycles'],9*(1<<aw))
            self.assertEqual(m['localbase']['special_cycles'],10*(1<<aw))
            self.assertEqual(m['steps'][0]['expected_returncode'],0)
            self.assertIn('cases=42',m['steps'][0]['expected_stdout'])
            self.assertIn('reads='+str(42*(1<<aw)),m['steps'][0]['expected_stdout'])
            self.assertIn(b'(special ? 10 : 9) * N',files[s.CPP])
            self.assertIn(b'whole_integer_oracle(trial)',files[s.CPP])

    def test_same_process_token_and_only_setup_snapshots(self):
        text=(s.ROOT/s.SV).read_text()
        self.assertEqual(text.count('always_ff @(posedge clk)if(legal_begin)begin'),1)
        for token in ('base_ext<=','two_base<=','three_base<=','negative_base<=','negative_two_base<=','base_max<='):
            self.assertEqual(len(re.findall(r'(?m)^\s*'+re.escape(token),text)),1)
        self.assertIn('state==PROCESS_WORD && bank==LP\'(b) && !process_bad',text)
        self.assertIn('ram_w[b]=fold_r;',text)
        self.assertIn('value<=value_next;stored_digit_bad<=',text)
        self.assertIn('READ_WORD:state<=VALUE_WORD;',text)
        self.assertNotIn('WRITE_WORD',text)
        self.assertNotIn('three_base=two_base+base_ext',text)
        self.assertEqual(s.sha((s.ROOT/s.donor.SV).read_bytes()),s.DONOR_SV_SHA)

    def test_precomputed_signed34_terms_and_fold_boundaries(self):
        for b in (172,512,604832956,1000000000):
            terms=(b,2*b,3*b,-b,-2*b,b-1)
            self.assertTrue(all(-(1<<33)<=x<(1<<33) for x in terms))
            for x in (-2*b,-2*b+1,-b-1,-b,-1,0,b-1,b,2*b-1,2*b,3*b-1):
                q=2 if x>=2*b else 1 if x>=b else 0 if x>=0 else -1 if x>=-b else -2
                r=x-q*b
                self.assertEqual((q,r),divmod(x,b))
                self.assertTrue(0<=r<b)

    def test_faults_are_separate_and_use_the_same_leaf(self):
        normal,normal_files=s.role();fault,files=s.role(5,8,'faults')
        self.assertEqual(normal['build']['sv_sources'],fault['build']['sv_sources'])
        self.assertEqual(normal_files[s.SV],files[s.SV])
        self.assertEqual([step['expected_returncode'] for step in fault['steps']],[0,1])
        self.assertIn('reset_aborts=11',fault['steps'][0]['expected_stdout'])
        self.assertIn(b'CANON_PIPE_RANGE_EXACT_E3',files[s.FAULT])
        self.assertIn(b'CANON_PIPE_PENDING_E0',files[s.FAULT])


if __name__=='__main__':unittest.main()

"""F3 source/small-N contracts; no GMP/full-N numeric/HDL execution."""
import json
import unittest
from fpga.reference import anext_writeback_qualification_v1 as q
from fpga.reference.anext_writeback_contract_v2 import schedule
from fpga.tests.test_anext_soak_v1 import fixture


class F3Qualification(unittest.TestCase):
    def test_actual_f3_source_and_calendar(self):
        self.assertFalse(q.verify()['RTL_changed'])
        self.assertFalse(q.verify()['inherited_native_result'])
        s=schedule(16)
        self.assertEqual((s['cold_loaded_backend'],s['cold_cached_backend'],s['warm_backend'],s['ntt_controller_cycles']),
                         (26023,26014,21906,17743))
        self.assertEqual(s['cold_loaded_backend']+99*s['warm_backend'],2194717)
        self.assertEqual(s['cold_loaded_backend']+9*s['cold_cached_backend']+990*s['warm_backend'],21947089)
        self.assertEqual((schedule(5)['cold_loaded_backend'],schedule(5)['warm_backend'],schedule(5)['ntt_controller_cycles']),
                         (218,195,126))

    def test_cpp_retained_initial_state_loop_unchanged(self):
        expected=q.expected()
        text=expected['rtl/tb/anext_writeback_soak_v1.cpp']
        self.assertEqual(text.count('d.rst_n=0;'),1)
        self.assertEqual(text.count('command(0,0,0,false);'),1)
        begin=text.index('for (unsigned k = 0; k < bits.size(); ++k)')
        loop=text[begin:text.index('require(next_check == count',begin)]
        for forbidden in ('d.rst_n','command(0','command(1'):
            self.assertNotIn(forbidden,loop)
        self.assertIn('uint64_t(n)/64)+14+(2*uint64_t(aw)+1);',text)
        self.assertIn('k==0?218u:195u',expected['rtl/tb/anext_writeback_small_prp_v1.cpp'])

    def test_prp_arithmetic_assets_unchanged(self):
        from fpga.reference.anext_point_small_prp_v1 import corpus as prior
        from fpga.reference.anext_writeback_small_prp_v1 import corpus
        self.assertEqual(corpus(),prior())
        text,oracle=corpus()
        self.assertEqual((oracle['n'],oracle['operations'],len(oracle['cases'])),(32,5051,8))
        self.assertIn('GFNPRP1 5 8',text)

    def test_small_boundary_controls_and_no_parent_cycle_inheritance(self):
        from fpga.reference.anext_writeback_soak_output_v1 import normalise
        for negative in ('none','boundary','loaded-state'):
            text,oracle,ref,error,rc=fixture(negative)
            rows=[]
            for line in text.splitlines():
                prefix,raw=line.split(' ',1);row=json.loads(raw)
                if prefix=='ANEXT_SOAK_STEP':
                    row['cycles']+=12;row['ntt']+=12 # AW5: original+1point+11F3.
                if prefix=='ANEXT_SOAK_PASS':row['cycles']+=12*row['operations']
                rows.append(prefix+' '+json.dumps(row))
            good='\n'.join(rows)+'\n'
            converted,metrics=normalise(good,oracle,ref)
            result=ref.validate_rows(converted,error,rc,{'negative':negative},oracle)
            if negative=='none':self.assertEqual(result['operations'],4)
            if negative!='loaded-state':
                with self.assertRaises(ValueError):normalise(text,oracle,ref)
                with self.assertRaises(ValueError):normalise(good.replace('"ntt": 126','"ntt": 125',1),oracle,ref)

    def test_unique_identity_anchor_rejects(self):
        for text in ('missing','x x'):
            with self.assertRaises(ValueError):q.once(text,'x','y')


if __name__=='__main__':unittest.main()

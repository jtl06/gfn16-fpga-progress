import copy
import unittest
from fpga.reference import stream27_shared_field_flags as fields
from fpga.reference import stream27_host_chain_diet_qualification as whole
from fpga.reference import stream27_term_select_bind as frozen
from fpga.reference import stream27_term_select_p16_diet_bind as binding
from fpga.reference import stream27_term_select_p16_diet_native as native
from fpga.reference import stream27_term_select_p16_diet_fault_native as faults


class PrivateDietTermSelectorTests(unittest.TestCase):
    def check(self,parent):
        before=copy.deepcopy(parent);b=binding.bind(parent);self.assertEqual(parent,before)
        info=b['term_select'];self.assertEqual(binding.bind(parent,enabled=0),parent)
        self.assertEqual(b['geometry'],parent['geometry'])
        self.assertEqual(binding.reverse_term(info['new_term'],b['files'][info['new_term']+'.sv'],info['parent_mul'],info['new_mul']),
                         (info['parent_term'],parent['files'][info['parent_term']+'.sv']))
        self.assertEqual(frozen.reverse_root(b['files'][b['top']+'.sv'],parent['top'],b['top'],info['parent_term'],info['new_term'],1),
                         parent['files'][parent['top']+'.sv'])
        for name,text in parent['files'].items():
            if name not in (parent['top']+'.sv',info['parent_term']+'.sv'):self.assertEqual(b['files'][name],text)
        self.assertIn(binding.FACTORED+' #(',b['files'][info['new_mul']+'.sv'])
        self.assertNotIn('genefer_montgomery_mul27_sparse_pipe #(',b['files'][info['new_mul']+'.sv'])

    def test_actual_factored_ordinary_and_private_ancestries(self):
        for field in range(3):
            self.check(fields.prepare(256,16,field,mode='warm_signed',corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1))
        for n in (32,256):
            b=whole.prepare(n,16,paired=False,contexts=1,canonical_pipe_stages=1,corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1)
            for name in [k for k in b['files'] if k.startswith('genefer_stream27_shared_warm_')]:
                view=copy.deepcopy(b);view['top']=name[:-3];view['mode']='warm_signed';self.check(view)

    def test_actual_private_normal_role_fullroot_mont_and_fixed_calendar(self):
        m,files,_=native.role();self.assertEqual(m['test_role'],'normal')
        self.assertEqual(m['build']['parameters']['MONT_FACTORED'],1)
        self.assertNotIn('CANONICAL_PIPE_STAGES',m['build']['parameters'])
        self.assertIn('_p16_diet_v1',m['term_select']['binding']['parent_mul'])
        self.assertIn(b'ref_self_check();',files[native.CPP])
        self.assertEqual(m['term_select']['counts']['physical_words'],2304)
        self.assertIn('private-p16-diet-term-selector-normal',m['steps'][0]['name'])
        self.assertLess(len(m['build']['top']),100)
        wrapper=files['rtl/'+m['build']['top']+'.sv'].decode()
        self.assertNotIn('always',wrapper);self.assertNotIn('assign',wrapper)
        self.assertIn('actual_field (.*)',wrapper)

    def test_actual_private_factored_fault_pair_and_exact_typed_mutant(self):
        m,files=faults.role();info=m['term_select']['binding']
        self.assertEqual([s['expected_returncode'] for s in m['steps']],[0,41])
        self.assertEqual(m['steps'][0]['expected_stdout'],m['steps'][1]['expected_stdout'])
        self.assertIn(binding.FACTORED+' #(',files['rtl/'+info['new_mul']+'.sv'].decode())
        self.assertIn(info['parent_term']+' #',files['rtl/'+faults.TOP+'.sv'].decode())
        self.assertIn('S4_P16_DIET_TERM_SELECT_TYPED_BYPASS',m['steps'][1]['expected_stderr'])
        header=files[faults.oracle.HEADER].decode()
        self.assertIn('#include "V'+m['build']['top']+'.h"',header)
        self.assertIn('using DUT=V'+m['build']['top']+';',header)


if __name__=='__main__':unittest.main()

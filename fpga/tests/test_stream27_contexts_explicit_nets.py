import re
import unittest
from fpga.reference import stream27_host_contexts as host
from fpga.reference import stream27_contexts_explicit_nets as declarations


class ExplicitNetTests(unittest.TestCase):
    def test_default_rtl_exact_and_zero_deep_copy(self):
        b = host.prepare(32,16,corr_serial_bfs=2,mont_factored=1,cold_launch_fence=1)
        same = host.prepare(32,16,corr_serial_bfs=2,mont_factored=1,cold_launch_fence=1,
                            explicit_net_declarations=0)
        self.assertEqual(b, same)
        self.assertEqual(declarations.bind(b,0),b)
        copy = declarations.bind(b,0)
        copy['files'].clear()
        self.assertTrue(b['files'])

    def test_profile_drivers_are_explicit_before_actual_instances(self):
        for n,p in ((32,8),(32,16),(256,16)):
            flags = dict(corr_serial_bfs=2,mont_factored=1,cold_launch_fence=1) if p==16 else {}
            b = host.prepare(n,p,explicit_net_declarations=1,**flags)
            self.assertEqual(b['parameters']['EXPLICIT_NET_DECLARATIONS'],1)
            self.assertEqual(len(b['explicit_net_declarations']['changes']),5)
            for name,text in b['files'].items():
                if name.startswith('genefer_stream27_threefield_carry_'):
                    self.assertIn('assign frame_profile_ok=',text)
                    self.assertIn('assign field_input_valid=',text)
                    self.assertNotIn('wire frame_profile_ok=',text)
                    self.assertLess(text.index('wire frame_profile_ok,field_input_valid;'),
                                    text.index('.in_slot_valid(field_input_valid)'))
                if name.startswith('genefer_stream27_shared_warm_'):
                    matches=list(re.finditer(r'\bprotocol_correction_base\b',text))
                    self.assertIn('wire [31:0]',text[max(0,matches[0].start()-20):matches[0].start()])
            root=b['files'][b['top']+'.sv']
            self.assertLess(root.index('wire canon_busy,'),root.index('!canon_busy'))

    def test_no_state_authority_calendar_or_ram_changes(self):
        old = host.prepare(256,16,corr_serial_bfs=2,mont_factored=1,cold_launch_fence=1)
        new = declarations.bind(old)
        self.assertEqual(new['geometry'],old['geometry'])
        for name,text in old['files'].items():
            if name not in new['explicit_net_declarations']['changes']:
                self.assertEqual(new['files'][name],text)
        for name,change in new['explicit_net_declarations']['changes'].items():
            after = new['files'][new['top']+'.sv'] if name==old['top']+'.sv' else new['files'][name]
            before=old['files'][name]
            def state(s):
                return [line for line in s.splitlines()
                        if '<=' in line or re.match(r'\s*always(?:_ff|_comb)?\b',line)]
            self.assertEqual(state(before),state(after))
        self.assertEqual({name:text for name,text in old['files'].items() if name.endswith('ram32.sv')},
                         {name:text for name,text in new['files'].items() if name.endswith('ram32.sv')})


if __name__=='__main__':
    unittest.main()

import unittest
from fpga.reference import stream27_host_chain_v1 as compiler
from fpga.reference import stream27_host_chain_model_v1 as model
from fpga.reference.stream27_host_core_v5 import prepare as scalar


class LongSource(unittest.TestCase):
    def test_real_paired_distinct_modules(self):
        for n in (32,256):
            b=compiler.prepare(n,paired=True)
            self.assertIn('host_chain_t5b_paired',b['top'])
            self.assertIn('candidate (.*)',b['files'][b['top']+'.sv'])
            self.assertIn('.EPOCH_SEED(EPOCH_SEED)',b['files'][b['top']+'.sv'])
            self.assertEqual(len(b['files']),len(scalar(n,paired=True)['files']))

    def test_frozen_arithmetic_identical(self):
        for n in (32,256):
            a=scalar(n);b=compiler.prepare(n)
            mutable=('host_core','host_chain','warm_recurrence','warm_chain','warm_canonical','chain_canonical')
            for name,s in a['files'].items():
                if not any(x in name for x in mutable):self.assertEqual(b['files'][name],s,name)

    def test_full_selector_and_exact_control_bit(self):
        b=compiler.prepare(32)
        canonical=next(s for name,s in b['files'].items() if 'chain_canonical' in name)
        warm=next(s for name,s in b['files'].items() if 'warm_chain' in name)
        self.assertIn('digit_sequence==final_sequence',canonical)
        self.assertIn('boundary_sequence==final_sequence',canonical)
        self.assertIn('!command_valid || command_index!=launched',warm)
        self.assertIn('current_feedback_double',warm)

    def test_mod16_is_not_true_final(self):
        count=65540
        self.assertFalse(model.true_final(3,count,3,0))
        self.assertTrue(model.true_final(count-1,count,3,0))

    def test_full_count_event_and_legacy_equal(self):
        for n in (32,256):
            g=compiler.prepare(n)['geometry']
            for count in (1,2,4,32):
                from fpga.reference.stream27_host_core_v1 import cycle_contract
                a=cycle_contract(n,g,count=count);b=compiler.cycle_contract(n,g,count=count)
                a.pop('scope');b.pop('scope');self.assertEqual(a,b)
            self.assertGreater(compiler.cycle_contract(n,g,count=0xffffffff)['host_done'],0xffffffff)

    def test_p8_not_silently_substituted(self):
        with self.assertRaisesRegex(ValueError,'P8'):compiler.prepare(32,8)

    def test_full_pop_push_old_head(self):
        f=model.ControlFIFO(20,7)
        for i in range(1,5):self.assertTrue(f.edge((i,7,i&1))['accepted'])
        self.assertFalse(f.edge((5,7,1))['ready'])
        result=f.edge((5,7,1),consume=True)
        self.assertEqual(result['popped'],(1,7,1));self.assertTrue(result['accepted'])
        self.assertEqual(list(f.queue),[(i,7,i&1) for i in range(2,6)])

    def test_no_empty_bypass(self):
        f=model.ControlFIFO(2,1)
        r=f.edge((1,1,0),consume=True)
        self.assertEqual(r['error'],'UNDERFLOW');self.assertFalse(r['accepted'])

    def test_typed_bad_descriptor(self):
        for descriptor,error in (((1,2,0),'GENERATION'),((2,1,0),'INDEX'),((0,1,0),'RANGE'),((3,1,0),'RANGE')):
            f=model.ControlFIFO(3,1);self.assertEqual(f.edge(descriptor)['error'],error);self.assertFalse(f.queue)

    def test_real_small_prp(self):
        p=model.program(32,'prp');self.assertEqual(p['count'],956)
        self.assertEqual(p['exponent'],p['base']**32)
        self.assertEqual(len(p['expected']),32)
        self.assertGreater(model.program(256,'prp')['count'],32)


if __name__=='__main__':unittest.main()

import unittest
from fpga.reference import stream27_canonical_pipe_v1 as native
from fpga.reference import stream27_host_chain_param_v3 as shared


class CanonicalPipe(unittest.TestCase):
    def test_frozen_default_and_only_leaf_arithmetic_delta(self):
        for p in (8,16):
            a=shared.parent.prepare(32,p,paired=True)
            self.assertEqual(a,shared.prepare(32,p,paired=True))
            b=shared.prepare(32,p,paired=True,canonical_pipe_stages=1)
            self.assertEqual(a['geometry'],b['geometry'])
            self.assertEqual(len(a['rtl_sources']),len(b['rtl_sources']))
            changed=[k for k in a['files'] if b['files'].get(k)!=a['files'][k]]
            self.assertEqual(len(changed),4)
            self.assertEqual(b['canonical_cost']['normal'],288)
            self.assertEqual(b['canonical_cost']['special'],320)
            self.assertIn('CANONICAL_PIPE_STAGES=1',b['files'][b['top']+'.sv'])

    def test_exact_cost_and_public_interface(self):
        for n,p in ((32,8),(256,16),(65536,8)):
            g={'warm_interval':16653,'carry_done':24847}
            a=shared.cycle_contract(n,g,count=24,cache_hit=True)
            b=shared.cycle_contract(n,g,count=24,cache_hit=True,canonical_pipe_stages=1)
            self.assertEqual(b['host_done']-a['host_done'],3*n)
            self.assertEqual(b['warm_done'],a['warm_done'])
            self.assertEqual(b['image_copy_cycles'],a['image_copy_cycles'])
            self.assertEqual(b['canonical_done_to_host_done'],a['canonical_done_to_host_done'])
        for bad in (-1,2,True,'1'):
            with self.assertRaises(ValueError):shared.prepare(canonical_pipe_stages=bad)

    def test_normal_corpus_and_typed_validator(self):
        for aw,p in ((5,8),(5,16),(8,8),(8,16)):
            counts=native.counts(aw,p)
            self.assertEqual(counts['cases'],42)
            self.assertEqual(counts['special'],4)
            stdout=f'CANON_PIPE_PASS aw={aw} p={p} '+' '.join(f'{k}={v}' for k,v in counts.items())+'\n'
            self.assertEqual(native.validate(stdout,'',0,dict(aw=aw,p=p),{})['status'],'PASS_expected_contracts')
            with self.assertRaises(ValueError):native.validate(stdout.replace('cycles=', 'bad='),'',0,dict(aw=aw,p=p),{})
        m,files=native.role(5,8)
        self.assertEqual(len(m['steps']),1)
        self.assertIn(b'(special ? 10 : 9) * N',files[native.CPP])
        self.assertNotIn(b'        reset_cases(h, recovery, trials[3]);',files[native.CPP])


if __name__=='__main__':unittest.main()

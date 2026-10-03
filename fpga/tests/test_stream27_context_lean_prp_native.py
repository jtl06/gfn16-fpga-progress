import copy
import json
from pathlib import Path
import unittest

from fpga.reference import stream27_context_lean_prp_native as recipe


class HealthyPrp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = recipe.corpus()

    def test_full_exponents_and_radix(self):
        self.assertEqual([case['base'] for case in self.oracle['cases']], list(recipe.BASES))
        for case in self.oracle['cases']:
            base = case['base']
            exponent = base**256
            self.assertEqual(int(case['exponent_bits'], 2), exponent)
            self.assertEqual(case['steps'], exponent.bit_length())
            self.assertEqual(recipe.decode(case['expected_digits'], base), pow(2, exponent, exponent+1))
        self.assertFalse(self.oracle['primality_claim'])
        self.assertFalse(self.oracle['full_sample_claim'])
        self.assertEqual(sum(case['steps'] for case in self.oracle['cases']), 41089)

    def test_sentinel_and_negative_sensitivity(self):
        for base in recipe.BASES[:2]:
            modulus = base**256+1
            self.assertEqual(recipe.encode(pow(base**128, 2, modulus), base), [-1]+[0]*255)
            self.assertEqual(recipe.decode([-1]+[0]*255, base), modulus-1)
        first = self.oracle['cases'][0]
        changed = recipe.encode(pow(2, first['base']**256 ^ 1, first['base']**256+1), first['base'])
        self.assertNotEqual(changed[0], first['expected_digits'][0])
        for value in (598, 1000000001, True):
            with self.assertRaises(ValueError):
                recipe.encode(1, value)

    def normal(self, branch):
        lines = [recipe.LABELS[branch]]
        rows = []
        for index in range(10):
            source = self.oracle['cases'][index] if index < 8 else dict(base=recipe.BASES[index-8],steps=1,doubles=0,
                expected_digits=[-1]+[0]*255)
            row = dict(case=index,base=source['base'],steps=source['steps'],doubles=source['doubles'],
                done_edge=recipe.FIRST[index%2]+(source['steps']-1)*214+215+10*256+20,
                sentinel=index>=8,digits=source['expected_digits'])
            rows.append(row)
            lines.append('A_CONTEXT_PRP_RESULT '+json.dumps(row,separators=(',',':')))
        lines.append('A_CONTEXT_PRP_PASS cases=8 sentinel_cases=2 squares=41091 doubles=15137 signed96_words=2560 interval=214')
        asset = json.dumps(self.oracle,indent=2)+'\n'
        return '\n'.join(lines)+'\n',dict(branch=branch,mode='normal',oracle_sha256=recipe.sha(asset.encode())),dict(oracle=asset)

    def test_typed_complete_outputs_and_mutants(self):
        for branch in recipe.LABELS:
            stdout, config, assets = self.normal(branch)
            value = recipe.validate(stdout,'',0,config,assets)
            self.assertEqual(value['squares'],41091)
            for bad in (stdout.replace('"case":0','"case":1',1), stdout.replace('interval=214','interval=213'),
                        stdout.replace('"sentinel":true','"sentinel":false',1), stdout.replace('"digits":[','"digits":[1,',1),
                        stdout.replace(recipe.LABELS[branch],recipe.LABELS['lean' if branch=='protected' else 'protected']),stdout+'extra\n'):
                with self.assertRaises(ValueError):
                    recipe.validate(bad,'',0,config,assets)
            for mode in ('negative-comparator','negative-schedule'):
                negative=dict(config,mode=mode)
                recipe.validate(recipe.LABELS[branch]+'\n','A_PRP_RESIDUE_MISMATCH case=0 digit=0\n',1,negative,assets)
                with self.assertRaises(ValueError):
                    recipe.validate(recipe.LABELS[branch]+'\n','',0,negative,assets)

    def test_exact_private_twin_sources_and_runtime(self):
        lean,lf,lb = recipe.role('lean')
        protected,pf,pb = recipe.role('protected')
        self.assertEqual(len(lb['files']),58)
        self.assertEqual(len(pb['files']),58)
        captured=json.loads((recipe.DONOR/'production-bundle.json').read_bytes())
        self.assertEqual(lb['generated_sha256'],captured['generated_sha256'])
        self.assertEqual(lb['files'],captured['files'])
        self.assertEqual(lf[recipe.CPP],pf[recipe.CPP])
        self.assertEqual(lf['reference-assets/r10-healthy-prp-n256.json'],pf['reference-assets/r10-healthy-prp-n256.json'])
        self.assertEqual(lean['build']['parameters']['LEAN_PRODUCTION'],1)
        self.assertNotIn('LEAN_PRODUCTION',protected['build']['parameters'])
        text=lf[recipe.CPP].decode()
        self.assertEqual(text.count('DUT d(&context)'),1)
        self.assertLess(text.index('gfn16_runtime::configure(context,argc,argv)'),text.index('DUT d(&context)'))
        self.assertIn('N+4',text)
        self.assertIn('sentinel?10u:9u',text)
        self.assertIn('next==counts',text)
        self.assertIn('d.command_generation=1',text)
        self.assertIn('uint16_t(EPOCHS[c]+count(ci)-1)',text)
        controls,_,_=recipe.role('lean',True)
        self.assertEqual(controls['test_role'],'deliberate_fault')
        self.assertEqual(len(controls['steps']),2)
        self.assertTrue(all(step['expected_returncode']==1 for step in controls['steps']))


if __name__=='__main__':
    unittest.main()

"""Ordinary small-N/source-only tests. Never executes HDL or full-N arithmetic."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import anext_point_base_fuzz_v1 as fuzz


def fixture(aw,mode='normal'):
    text,oracle=fuzz.corpus(aw);p=fuzz.profile(aw);rows=[]
    for c in oracle['cases'] if mode=='normal' else oracle['cases'][:1]:
        changed=mode=='negative-schedule';b=c['base'];n=p['n']
        residue=pow(2,b**n-int(changed),b**n+1)
        digits=fuzz.encode(residue,b,n);cycles=p['cold']+(c['operations']-1)*p['warm']
        rows.append(f'E2E_RESULT case={c["index"]} base={b} class=unclassified steps={c["operations"]} doubles={c["doubles"]-int(changed)} cycles={cycles} cold=1 warm={c["operations"]-1} conversion={p["prefill"]} roots=9 prp={int(residue==1)} digits='+','.join(map(str,digits)))
    if mode=='normal':
        cycles=sum(p['cold']+(c['operations']-1)*p['warm'] for c in oracle['cases'])
        rows.append(f'E2E_PASS aw={aw} cases={p["cases"]} operations={oracle["operations"]} doubles={oracle["doubles"]} readbacks={p["cases"]} cycles={cycles} cold={p["cases"]} warm={oracle["operations"]-p["cases"]} conversion={p["cases"]*p["prefill"]} roots={p["cases"]*9}')
    return '\n'.join(rows)+'\n','' if mode=='normal' else fuzz.MISMATCH,0 if mode=='normal' else 1,dict(aw=aw,mode=mode),dict(corpus=text,oracle=json.dumps(oracle))


class BaseRangeFuzz(unittest.TestCase):
    def test_domain_coverage_and_canonical_oracle(self):
        for aw in (5,8):
            p=fuzz.profile(aw);text,o=fuzz.corpus(aw);values=fuzz.bases(aw)
            self.assertEqual(len(values),p['cases'])
            self.assertIn(p['floor'],values);self.assertIn(1000000000,values)
            self.assertIn(604832956,values)
            self.assertEqual(o['corpus_sha256'],fuzz.hashlib.sha256(text.encode()).hexdigest())
            self.assertTrue(all(c['classification']=='unclassified' for c in o['cases']))
            for c in o['cases']:
                expected=pow(2,c['base']**p['n'],c['base']**p['n']+1)
                self.assertEqual(fuzz.decode(c['expected_digits'],c['base'],p['n']),expected)
        for aw in (True,4,16):
            with self.assertRaises(ValueError):fuzz.corpus(aw)

    def test_exact_normal_and_both_negative_contracts(self):
        for aw in (5,8):
            for mode in fuzz.MODES:
                args=fixture(aw,mode)
                self.assertEqual(fuzz.validate(*args)['status'],'PASS_expected_contracts')
                stdout,stderr,rc,config,assets=args
                bads=[(stdout+'junk\n',stderr,rc,config,assets),
                      (stdout,stderr,True,config,assets),
                      (stdout.replace('roots=9','roots=8',1),stderr,rc,config,assets),
                      (stdout.replace('class=unclassified','class=prime',1),stderr,rc,config,assets),
                      (stdout,stderr,rc,{**config,'unknown':1},assets)]
                for bad in bads:
                    with self.assertRaises(ValueError):fuzz.validate(*bad)

    def test_assets_boundary_digit_and_schedule_reject(self):
        for aw in (5,8):
            stdout,stderr,rc,config,assets=fixture(aw)
            mutated=copy.deepcopy(assets);o=json.loads(mutated['oracle']);o['cases'][0]['base']+=1
            mutated['oracle']=json.dumps(o)
            with self.assertRaises(ValueError):fuzz.validate(stdout,stderr,rc,config,mutated)
            first=json.loads(assets['oracle'])['cases'][0]
            old='digits='+','.join(map(str,first['expected_digits']))
            bad=[*first['expected_digits']];bad[-1]=(bad[-1]+1)%first['base']
            with self.assertRaises(ValueError):fuzz.validate(stdout.replace(old,'digits='+','.join(map(str,bad)),1),stderr,rc,config,assets)
            with self.assertRaises(ValueError):fuzz.validate(stdout.replace('doubles='+str(first['doubles']),'doubles='+str(first['doubles']-1),1),stderr,rc,config,assets)

    def test_additive_bench_has_generic_small_geometry_no_midchain_reload(self):
        text=fuzz.bench()
        self.assertIn('static_assert(AW==5 || AW==8',text)
        self.assertIn('aw==AW && count==CASES',text)
        self.assertIn('k==0?COLD:WARM',text)
        start=text.index('for(unsigned k=0;k<steps;++k)')
        loop=text[start:text.index('actual[i]=command(2',start)]
        self.assertNotIn('command(0',loop);self.assertNotIn('command(1',loop);self.assertNotIn('d.rst_n',loop)
        self.assertEqual(text.count('command(5,0,0,base,bit);'),1)
        with self.assertRaises(ValueError):fuzz.once('x x','x','y')

    def test_closed_role_build_preserves_30_point_rtl(self):
        with tempfile.TemporaryDirectory() as temporary:
            for aw in (5,8):
                output=Path(temporary)/str(aw)
                result=fuzz.prepare(aw,output)
                m=json.loads((output/'manifest.json').read_text())
                self.assertEqual(result['compiled_sv'],30)
                self.assertEqual(m['sources']['rtl/kernel/genefer_anext_point_core_v1.sv'],fuzz.CORE)
                self.assertEqual(m['sources']['rtl/kernel/genefer_anext_point_block_engine_v1.sv'],fuzz.BLOCK)
                self.assertEqual(len(m['steps']),3)
                self.assertEqual((output/'source/fpga'/fuzz.CPP).read_text(),fuzz.bench())


if __name__=='__main__':unittest.main()

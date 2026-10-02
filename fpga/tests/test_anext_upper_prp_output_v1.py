"""AW5-only independent output fixtures; no full-size arithmetic."""
import json,unittest
from fpga.reference import anext_upper_small_prp_v1 as p

def fixture(mode='normal'):
    text,o=p.corpus();lines=[];cycles=0
    for c in o['cases'][:8 if mode=='normal' else 1]:
        base=c['base'];n=c['operations'];delta=int(mode=='negative-schedule')
        v=pow(2,base**32-delta,base**32+1);cost=207+(n-1)*184;cycles+=cost
        lines.append(f"E2E_RESULT case={c['index']} base={base} class={c['classification']} steps={n} doubles={c['doubles']-delta} cycles={cost} cold=1 warm={n-1} conversion=12 roots=9 prp={int(v==1)} digits="+','.join(map(str,p.encode(v,base))))
    if mode=='normal':lines.append(f"E2E_PASS aw=5 cases=8 operations={o['operations']} doubles={o['doubles']} readbacks=8 cycles={cycles} cold=8 warm={o['operations']-8} conversion=96 roots=72")
    return '\n'.join(lines)+'\n',{'corpus':text,'oracle':json.dumps(o)}
class PRPOutput(unittest.TestCase):
    def test_all_modes(self):
        for mode in ('normal','negative-comparator','negative-schedule'):
            out,assets=fixture(mode);self.assertEqual(p.validate(out,'' if mode=='normal' else p.MISMATCH,0 if mode=='normal' else 1,{'mode':mode},assets)['status'],'PASS_expected_contracts')
    def test_bad_output(self):
        out,a=fixture();row=out.splitlines()[0];old=int(row.split('cycles=')[1].split()[0]);wrong=out.replace(f'cycles={old}',f'cycles={old-1}',1)
        for bad in (wrong,out+'extra\n','\n'.join(out.splitlines()[1:])+'\n',out.replace('doubles=1825','doubles=1824')):
            self.assertNotEqual(bad,out)
            with self.assertRaises(ValueError):p.validate(bad,'',0,{'mode':'normal'},a)
if __name__=='__main__':unittest.main()

import json,unittest
from fpga.reference.anext_small_prp_v1 import corpus,validate,encode,MISMATCH

def fixture(mode):
    text,o=corpus();lines=[];total=0
    for c in o['cases'][:8 if mode=='normal' else 1]:
        exp=c['base']**32-(mode=='negative-schedule');value=pow(2,exp,c['base']**32+1)
        cycles=206+(c['operations']-1)*183;total+=cycles
        lines.append(f'E2E_RESULT case={c["index"]} base={c["base"]} class={c["classification"]} steps={c["operations"]} doubles={c["doubles"]-(mode=="negative-schedule")} cycles={cycles} cold=1 warm={c["operations"]-1} conversion=12 roots=9 prp={int(value==1)} digits='+','.join(map(str,encode(value,c['base']))))
    if mode=='normal':lines.append(f'E2E_PASS aw=5 cases=8 operations={o["operations"]} doubles={o["doubles"]} readbacks=8 cycles={total} cold=8 warm={o["operations"]-8} conversion=96 roots=72')
    return '\n'.join(lines)+'\n',dict(corpus=text,oracle=json.dumps(o))

class SmallPRP(unittest.TestCase):
    def test_domain_certificates_and_schedule(self):
        _,o=corpus();self.assertEqual([c['base'] for c in o['cases'][:4]],[301,300,448,7552])
        self.assertEqual(sum(c['classification']=='prime' for c in o['cases']),3)
        for c in o['cases']:
            n=c['base']**32+1;x=1
            for bit in c['exponent_bits']:x=x*x*(1<<int(bit))%n
            self.assertEqual(x,pow(2,n-1,n))
    def test_closed_positive_and_host_negatives(self):
        for mode in ('normal','negative-comparator','negative-schedule'):
            text,assets=fixture(mode);err='' if mode=='normal' else MISMATCH;rc=0 if mode=='normal' else 1
            self.assertEqual(validate(text,err,rc,dict(mode=mode),assets)['status'],'PASS_expected_contracts')
            for bad in (text+'extra\n',text.replace('roots=9','roots=3089',1),text.replace('conversion=12','conversion=11',1)):
                with self.assertRaises(ValueError):validate(bad,err,rc,dict(mode=mode),assets)
            with self.assertRaises(ValueError):validate(text,'wrong\n',rc,dict(mode=mode),assets)
if __name__=='__main__':unittest.main()

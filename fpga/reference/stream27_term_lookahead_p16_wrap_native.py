"""Separate unchanged-RTL native owner-wrap successor; completed gates stay frozen."""
import argparse
from pathlib import Path
from . import stream27_term_lookahead_p16_native as parent
from . import stream27_term_lookahead_p16_bind as binding
BASE_ROLE=parent.role
SELF='reference/stream27_term_lookahead_p16_wrap_native.py'
def role(aw=8,field=1):
    m,files=BASE_ROLE(aw,field)
    cpp=files[parent.CPP].decode()
    old=f'S4_TERM_LOOKAHEAD_PAIRED_NORMAL aw={aw} p=16 field={field}'
    label=f'S4_TERM_LOOKAHEAD_WRAP_NORMAL aw={aw} p=16 field={field}'
    cpp=binding.once(cpp,old,label)
    cpp=binding.once(cpp,'        run(d,{frame(2)},counts,false,true);',
        '        run(d,{frame(2,0,0,65535),frame(3,INTERVAL,CORRECTION,0)},counts);\n        run(d,{frame(2)},counts,false,true);')
    for old,new in (
        ('d.generation_in=7;d.live_generation=7;','d.generation_in=255;d.live_generation=255;'),
        ('d.correction_generation=7;','d.correction_generation=255;'),
        ('d.live_generation=live?7:8;','d.live_generation=live?255:0;'),
        ('d.generation_out==7,','d.generation_out==255,'),
        ('d.commit_generation==7,','d.commit_generation==255,')):
        cpp=binding.once(cpp,old,new)
    files[parent.CPP]=cpp.encode()
    files['lineage/'+SELF]=(binding.ROOT/SELF).read_bytes()
    counts=m['term_lookahead']['counts'];rows=m['term_lookahead']['geometry']['rows']
    counts.update(cases=10,frames=11,physical_rows=11*rows,physical_words=11*(1<<aw),eligible_rows=9*rows,commits=9*rows)
    m['steps'][0].update(name='term-lookahead-paired-owner-wrap-normal',expected_stdout=label+' '+' '.join(f'{k}={v}' for k,v in counts.items())+'\n')
    m['sources']={name:parent.base.sha(raw) for name,raw in files.items()}
    m['term_lookahead']['owner_wrap_native']=dict(epochs=[65535,0],generation=255,cancelled_live_generation=0,rtl_unchanged=True)
    return m,files
def prepare(output,budget,aw=8,field=1,after=None):
    # Scoped role substitution reuses the existing owned preparer, not launcher policy.
    original=parent.role
    try:
        parent.role=role
        return parent.prepare(output,budget,aw,field,after,revision=3)
    finally:parent.role=original
if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--output',type=Path,required=True);q.add_argument('--budget',type=Path,required=True)
    q.add_argument('--aw',type=int,choices=(8,16),default=8);q.add_argument('--field',type=int,default=1);q.add_argument('--after')
    a=q.parse_args();prepare(a.output,a.budget,a.aw,a.field,a.after)

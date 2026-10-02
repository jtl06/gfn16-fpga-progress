"""Actual shared P8/P16 long-feed packages with the narrow start-valid repair.

Retains v3's numeric/cycle/one-edge reset/descriptor/true-final assertions.
P8 changes only real parameter binding, profile guard and N/P row accounting;
there is no inherited P16 execution or hidden per-square canonical barrier.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
from . import stream27_host_chain_native_v3 as parent
from . import stream27_host_chain_param_v2 as core

ROOT=core.ROOT
PIN='4d42f2328b63f849d8f0ac5ea5d17542035c7d7c9f53057cae6ef7e92829c104'


def prepare(destination,*,n=32,p=16,ordinal=False):
    if p not in (8,16):raise ValueError('S4_LONG_NATIVE_P8_P16')
    if hashlib.sha256((ROOT/'reference/stream27_host_chain_native_v3.py').read_bytes()).hexdigest()!=PIN:
        raise ValueError('S4_LONG_RESET_NATIVE_PARENT_DRIFT')
    # Rebind the original source emitter, leaving each frozen ancestor intact.
    module=parent.parent.parent
    path=ROOT/'reference/stream27_host_chain_native_v1.py';raw=path.read_text()
    node=next(x for x in ast.parse(raw).body if isinstance(x,ast.FunctionDef) and x.name=='prepare')
    body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    class Binding:
        @staticmethod
        def prepare(n,**kwargs):return core.prepare(n,p,**kwargs)
    ns=dict(vars(module));ns['core']=Binding
    exec(compile(body,'[shared reset-safe long host]','exec'),ns)
    r=ns['prepare'](destination,n=n,ordinal=ordinal)
    destination=Path(destination).resolve();source=destination/'inputs/fpga'
    cpp=source/module.BENCH;text=cpp.read_text()
    text=text.replace('d.warm_count=2;d.start=1;edge(d);','d.warm_count=type==2?3:2;d.start=1;edge(d);')
    old='need(d.operations_started<=count&&d.completed_squares<=count,"S4_LONG_ORDINAL_BOUND");'
    new='''need(d.operations_started<=count&&(d.operations_started==0 || d.completed_squares<=count),
            "S4_LONG_ORDINAL_BOUND job="+std::to_string(c.jobs)+" age="+std::to_string(elapsed)+" count="+std::to_string(count)+" started="+std::to_string(d.operations_started)+" completed="+std::to_string(d.completed_squares));'''
    if text.count(old)!=1:raise ValueError('S4_LONG_COMPLETION_QUALIFIER')
    text=text.replace(old,new)
    if p==8:
        if text.count('N/16')!=3:raise ValueError('S4_LONG_PARAM_ROW_COUNTS')
        text=text.replace('N/16','N/P')
    cpp.write_text(text)
    legacy=source/'rtl/tb/stream27_host_core_v1.cpp'
    if p==8:
        text=legacy.read_text()
        if text.count('N/16')!=1:raise ValueError('S4_LONG_PARAM_SCALAR_ROWS')
        legacy.write_text(text.replace('N/16','N/P'))
    header=source/'rtl/tb/s4_host_config_v1.h';text=header.read_text()
    k=2*n+24*p;minimum=max(2*n+5,(2*k+2)//3+1)
    text,count=re.subn(r'MIN_BASE=\d+',f'MIN_BASE={minimum}',text)
    if count!=1:raise ValueError('S4_LONG_PARAM_BASE')
    if p==8:
        text=text.replace('S4_SCALAR_HOST_T5B','S4_SHARED_P8_SCALAR_HOST_T5B')
        text=text.replace('S4_LONG_HOST','S4_SHARED_P8_LONG_HOST').replace('S4_LONG_ORDINAL','S4_SHARED_P8_LONG_ORDINAL')
    header.write_text(text+f'constexpr unsigned P={p};\n')
    local='reference/stream27_host_chain_native_v4.py';target=source/'lineage'/local;target.write_bytes((ROOT/local).read_bytes())
    mpath=destination/'manifest.json';m=json.loads(mpath.read_text());m['build']['parameters']['P']=p
    for step in m['steps']:
        for key in ('expected_stdout',):
            if key in step:
                if p==8:
                    step[key]=step[key].replace('S4_SCALAR_HOST_T5B','S4_SHARED_P8_SCALAR_HOST_T5B')
                    step[key]=step[key].replace('S4_LONG_HOST','S4_SHARED_P8_LONG_HOST').replace('S4_LONG_ORDINAL','S4_SHARED_P8_LONG_ORDINAL')
                step[key]=step[key].replace('true_final_rows='+str((1 if ordinal else 2)*n//16),
                                          'true_final_rows='+str((1 if ordinal else 2)*n//p))
    m['sources']={str(path.relative_to(source)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(source.rglob('*')) if path.is_file()}
    mpath.write_text(json.dumps(m,indent=2)+'\n')
    r.update(manifest_sha256=hashlib.sha256(mpath.read_bytes()).hexdigest(),source_count=len(m['sources']),p=p,
             reset_delta=core.prepare(n,p)['reset_delta'])
    r['long_counts']['true_final_rows']=2*n//p
    r['limitations']=[item.replace('or P8 whole arithmetic qualification','or fullN whole arithmetic qualification') for item in r['limitations']]
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    r=prepare(sys.argv[1],n=int(sys.argv[2]),p=int(sys.argv[3]),ordinal=len(sys.argv)==5 and sys.argv[4]=='ordinal')
    print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top','p','long_counts','ordinal')},indent=2))

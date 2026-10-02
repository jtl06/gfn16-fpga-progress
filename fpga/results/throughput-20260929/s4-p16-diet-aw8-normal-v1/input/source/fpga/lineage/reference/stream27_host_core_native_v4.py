"""Same immutable scalar gate with persistent cold-epoch ledger RTL."""
import ast
import hashlib
import json
from pathlib import Path
import types
from . import stream27_host_core_native_v2 as v2
from . import stream27_host_core_native_v3 as parent
from .stream27_host_core_v3 import prepare as compile_core

PIN='144e94e9ae2399735a154d7b04f21ab3a7eec178e95f13a2b1d12434eb94019a'


def prepare(destination,*,n=32):
    path=parent.original.ROOT/'reference/stream27_host_core_native_v3.py';raw=path.read_text()
    if hashlib.sha256(raw.encode()).hexdigest()!=PIN:raise ValueError('S4_HOST_COLD_EPOCH_NATIVE_PARENT_DRIFT')
    nodes=[node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name=='prepare']
    if len(nodes)!=1:raise ValueError('S4_HOST_COLD_EPOCH_NATIVE_ENTRY')
    node=nodes[0];body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    proxy=types.ModuleType('frozen_native_v2_with_cold_epoch_compiler');proxy.__dict__.update(vars(v2));proxy.compile_core=compile_core
    namespace=dict(vars(parent));namespace['parent']=proxy
    exec(compile(body,str(path)+'[cold epoch compiler successor]','exec'),namespace)
    r=namespace['prepare'](destination,n=n);destination=Path(destination).resolve();source=destination/'inputs/fpga'
    bench=source/parent.original.BENCH;text=bench.read_text()
    changes=[('static void candidate(DUT& d,const Job& job,bool hit){','static void candidate(DUT& d,const Job& job,bool hit,unsigned kind,unsigned index){'),
        ('"S4_HOST_NATIVE_ERROR elapsed="+std::to_string(elapsed)',
         '"S4_HOST_NATIVE_ERROR case="+std::to_string(kind)+" job="+std::to_string(index)+" elapsed="+std::to_string(elapsed)'),
        ('candidate(d,job,cache==job.base);','candidate(d,job,cache==job.base,c.id,j);')]
    for old,new in changes:
        if text.count(old)!=1:raise ValueError('S4_HOST_COLD_EPOCH_DIAGNOSTIC_ANCHOR')
        text=text.replace(old,new)
    bench.write_text(text)
    local='reference/stream27_host_core_native_v4.py';target=source/'lineage'/local;target.write_bytes((parent.original.ROOT/local).read_bytes())
    mpath=destination/'manifest.json';m=json.loads(mpath.read_text());m['sources'][parent.original.BENCH]=parent.original.sha(bench);m['sources']['lineage/'+local]=parent.original.sha(target)
    mpath.write_text(json.dumps(m,indent=2)+'\n');r['manifest_sha256']=parent.original.sha(mpath);r['source_count']=len(m['sources'])
    r['cold_epoch_delta']='Root ledger only: persistent nextcold epoch after fully copied priorjob; frozen protocol/NTT/carry/canonical unchanged. Existing numeric/cycle/readback expectations remain exact.'
    r['failed_v3_native']='report0b477f66/actualelapsed4: cold cache-hit epoch0 violates retained next_epoch1; diagnostic case/job labels now explicit.'
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    if len(sys.argv)!=3:raise ValueError('S4_HOST_COLD_EPOCH_NATIVE_USAGE destination n')
    r=prepare(sys.argv[1],n=int(sys.argv[2]));print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top')},indent=2))

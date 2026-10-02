"""Mixed cold/batch jobs, real wrap and failed-job reset/reload recovery gate."""
import ast
import hashlib
import json
from pathlib import Path
import types
from . import stream27_host_core_native_v2 as v2
from . import stream27_host_core_native_v4 as parent
from .stream27_host_core_v4 import prepare as compile_core

PIN='a44aa81a726bfb5f8106cb634db1a4bd17a1e7021d33834f5f97a0151c17256a'


def prepare(destination,*,n=32):
    path=parent.parent.original.ROOT/'reference/stream27_host_core_native_v4.py';raw=path.read_text()
    if hashlib.sha256(raw.encode()).hexdigest()!=PIN:raise ValueError('S4_HOST_WRAP_NATIVE_PARENT_DRIFT')
    nodes=[node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name=='prepare']
    if len(nodes)!=1:raise ValueError('S4_HOST_WRAP_NATIVE_ENTRY')
    node=nodes[0];body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    # V4 rebinds v3->v2; supply the exact new compiler at that source boundary.
    proxy=types.ModuleType('native_v2_with_completed_wrap_compiler');proxy.__dict__.update(vars(v2));proxy.compile_core=compile_core
    namespace=dict(vars(parent));namespace['v2']=proxy;namespace['compile_core']=compile_core
    exec(compile(body,str(path)+'[real modulo wrap and post-fault recovery]','exec'),namespace)
    r=namespace['prepare'](destination,n=n);destination=Path(destination).resolve();source=destination/'inputs/fpga'
    original=parent.parent.original;bench=source/original.BENCH;text=bench.read_text()
    changes=[('mutations=0,faults=0,resets=0;','mutations=0,faults=0,resets=0,recoveries=0;'),
        ('for(unsigned type=0;type<4;++type)quarantine(d,type,counts);',
         '''for(unsigned type=0;type<4;++type){quarantine(d,type,counts);
        reset(d);Image zero{};load(d,zero);Job recovered{};recovered.base=MIN_BASE;recovered.count=1;
        candidate(d,recovered,false,9,type);production(d,recovered);compare(d,recovered,9,type,false,counts);
        ++counts.jobs;++counts.frames;++counts.recoveries;}'''),
        ('<<" copied_words="<<counts.reads<<"\\n";',
         '<<" copied_words="<<counts.reads<<" recovery_jobs="<<counts.recoveries<<"\\n";')]
    for old,new in changes:
        if text.count(old)!=1:raise ValueError('S4_HOST_WRAP_RECOVERY_BENCH_ANCHOR:'+old)
        text=text.replace(old,new)
    bench.write_text(text)
    local='reference/stream27_host_core_native_v5.py';target=source/'lineage'/local;target.write_bytes((original.ROOT/local).read_bytes())
    mpath=destination/'manifest.json';m=json.loads(mpath.read_text());m['sources'][original.BENCH]=original.sha(bench);m['sources']['lineage/'+local]=original.sha(target)
    m['build']['parameters']['EPOCH_SEED']=65534
    old=m['steps'][0]['expected_stdout'];new=old.replace('jobs=10 frames=19','jobs=14 frames=23').replace(f'paired_reads={10*n}',f'paired_reads={14*n}').replace(f'copied_words={10*n}\n',f'copied_words={14*n} recovery_jobs=4\n')
    if old==new:raise ValueError('S4_HOST_WRAP_RECOVERY_COUNTER_ANCHOR')
    m['steps'][0]['expected_stdout']=new
    mpath.write_text(json.dumps(m,indent=2)+'\n');r['manifest_sha256']=original.sha(mpath);r['source_count']=len(m['sources'])
    r['counts'].update(jobs=14,frames=23,paired_reads=14*n,copied_words=14*n,recovery_jobs=4)
    r['wrap_test']='Actual EPOCH_SEED65534 parameter, shared frozen protocol/roots/dimensions unchanged; count4 spans65534,65535,0,1 then next completed coldjob2. Default source resetseed0.'
    r['recovery_test']='Every invalidbase/count0/count33/signed-2 fault is followed by real reset+fullreload+successful exact-cycle zero square and actual signed96 T5b image comparison.'
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    if len(sys.argv)!=3:raise ValueError('S4_HOST_WRAP_NATIVE_USAGE destination n')
    r=prepare(sys.argv[1],n=int(sys.argv[2]));print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top','counts')},indent=2))

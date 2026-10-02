"""Identical numeric/cycle/recovery gate, explicit seed width RTL successor."""
import ast
import hashlib
import json
from pathlib import Path
from . import stream27_host_core_native_v5 as parent
from .stream27_host_core_v5 import prepare as compile_core

PIN='40015c708e23f8991a4aaf374e83297c0669aae61d3d3d86f17ffd0f84171d9c'


def prepare(destination,*,n=32):
    original=parent.parent.parent.original;path=original.ROOT/'reference/stream27_host_core_native_v5.py';raw=path.read_text()
    if hashlib.sha256(raw.encode()).hexdigest()!=PIN:raise ValueError('S4_HOST_SEED_WIDTH_NATIVE_PARENT_DRIFT')
    nodes=[node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name=='prepare']
    if len(nodes)!=1:raise ValueError('S4_HOST_SEED_WIDTH_NATIVE_ENTRY')
    node=nodes[0];body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    namespace=dict(vars(parent));namespace['compile_core']=compile_core
    exec(compile(body,str(path)+'[explicit32bit native parameter width]','exec'),namespace)
    r=namespace['prepare'](destination,n=n);destination=Path(destination).resolve();source=destination/'inputs/fpga'
    local='reference/stream27_host_core_native_v6.py';target=source/'lineage'/local;target.write_bytes((original.ROOT/local).read_bytes())
    mpath=destination/'manifest.json';m=json.loads(mpath.read_text());m['sources']['lineage/'+local]=original.sha(target)
    mpath.write_text(json.dumps(m,indent=2)+'\n');r['manifest_sha256']=original.sha(mpath);r['source_count']=len(m['sources'])
    r['seed_width_delta']='ONLY native parameter boundary32bitunsigned/rangeguard0..65535/explicit16bit reset cast. All corpus/C++/footers/expectedcycles/P/dimensions/threads unchanged from v5.'
    r['failed_v5_native']='Lint-only WIDTHTRUNC on CONST32fffe to logic16 EPOCH_SEED; no build/probe/runtime, no numeric failure inference.'
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    if len(sys.argv)!=3:raise ValueError('S4_HOST_SEED_WIDTH_NATIVE_USAGE destination n')
    r=prepare(sys.argv[1],n=int(sys.argv[2]));print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top','counts')},indent=2))

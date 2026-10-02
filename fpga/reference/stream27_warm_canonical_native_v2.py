"""Same real canonical/T5b gate with additive current-live read qualification."""
import ast
import hashlib
import json
from pathlib import Path
from . import stream27_warm_canonical_native_v1 as parent
from .stream27_warm_canonical_v2 import prepare as compile_core

PIN='5713df95b44ba5e4b0ffd934f435929dde8fd9d9d61609818c33612b95c2b212'


def prepare(destination,*,n=32):
    path=parent.ROOT/'reference/stream27_warm_canonical_native_v1.py';raw=path.read_text()
    if hashlib.sha256(raw.encode()).hexdigest()!=PIN:raise ValueError('S4_CANONICAL_NATIVE_PARENT_DRIFT')
    nodes=[node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name=='prepare']
    if len(nodes)!=1:raise ValueError('S4_CANONICAL_NATIVE_PARENT_FUNCTION')
    node=nodes[0];body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    namespace=dict(vars(parent));namespace['compile_core']=compile_core
    exec(compile(body,str(path)+'[terminal read successor]','exec'),namespace)
    r=namespace['prepare'](destination,n=n);destination=Path(destination).resolve();source=destination/'inputs/fpga'
    local='reference/stream27_warm_canonical_native_v2.py';target=source/'lineage'/local;target.write_bytes((parent.ROOT/local).read_bytes())
    manifest=destination/'manifest.json';m=json.loads(manifest.read_text());m['sources']['lineage/'+local]=parent.sha(target)
    manifest.write_text(json.dumps(m,indent=2)+'\n');r['manifest_sha256']=parent.sha(manifest);r['source_count']=len(m['sources'])
    r['terminal_read_live_qualified']=True;r['parent_native_preparer_sha256']=PIN
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    if len(sys.argv)!=3:raise ValueError('S4_CANONICAL_NATIVE_V2_USAGE destination n')
    r=prepare(sys.argv[1],n=int(sys.argv[2]));print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top')},indent=2))

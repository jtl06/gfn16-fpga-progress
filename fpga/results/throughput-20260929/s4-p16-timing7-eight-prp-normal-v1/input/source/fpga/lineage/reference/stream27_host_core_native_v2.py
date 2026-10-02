"""Same scalar T5b gate with current copied-image publication assertions."""
import ast
import hashlib
import json
from pathlib import Path
from . import stream27_host_core_native_v1 as parent
from .stream27_host_core_v2 import prepare as compile_core

PIN='2a38dd13687805773e1556d9882652a24f9a8d4ca36b91af2cc30dfd26e4b2fc'


def prepare(destination,*,n=32):
    path=parent.ROOT/'reference/stream27_host_core_native_v1.py';raw=path.read_text()
    if hashlib.sha256(raw.encode()).hexdigest()!=PIN:raise ValueError('S4_HOST_PUBLICATION_NATIVE_PARENT_DRIFT')
    nodes=[node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name=='prepare']
    if len(nodes)!=1:raise ValueError('S4_HOST_PUBLICATION_NATIVE_ENTRY')
    node=nodes[0];body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    namespace=dict(vars(parent));namespace['compile_core']=compile_core
    exec(compile(body,str(path)+'[current host publication successor]','exec'),namespace)
    r=namespace['prepare'](destination,n=n);destination=Path(destination).resolve();source=destination/'inputs/fpga'
    bench=source/parent.BENCH;text=bench.read_text()
    changes=[('!d.busy&&!d.error&&!d.t5b_error,"S4_HOST_LOAD_IDLE"',
              '!d.busy&&!d.error&&!d.t5b_error&&!d.canonical_ready,"S4_HOST_LOAD_IDLE"'),
        ('!d.read_valid&&!d.t5b_read_valid&&!d.error&&!d.t5b_error,"S4_HOST_LOAD_WINS_READ"',
         '!d.read_valid&&!d.t5b_read_valid&&!d.error&&!d.t5b_error&&!d.canonical_ready,"S4_HOST_LOAD_WINS_READ"')]
    for old,new in changes:
        if text.count(old)!=1:raise ValueError('S4_HOST_PUBLICATION_BENCH_ANCHOR')
        text=text.replace(old,new)
    bench.write_text(text)
    local='reference/stream27_host_core_native_v2.py';target=source/'lineage'/local;target.write_bytes((parent.ROOT/local).read_bytes())
    mpath=destination/'manifest.json';m=json.loads(mpath.read_text());m['sources'][parent.BENCH]=parent.sha(bench);m['sources']['lineage/'+local]=parent.sha(target)
    mpath.write_text(json.dumps(m,indent=2)+'\n');r['manifest_sha256']=parent.sha(mpath);r['source_count']=len(m['sources'])
    r['current_host_image_publication_assertions']=True;r['parent_preparer_sha256']=PIN
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    if len(sys.argv)!=3:raise ValueError('S4_HOST_NATIVE_PUBLICATION_USAGE destination n')
    r=prepare(sys.argv[1],n=int(sys.argv[2]));print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top')},indent=2))

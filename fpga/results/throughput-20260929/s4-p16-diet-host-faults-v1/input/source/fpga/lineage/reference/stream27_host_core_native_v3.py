"""Immutable independent expected images plus separate publication RTL delta.

Historical v1 native failure is an oracle corpus list-alias defect, not a DUT
arithmetic result. Recompute each image from the original cold seed and current
mutation/base/count commands using independent whole integer arithmetic. Freeze
each expected image as a tuple before advancing to any later partial write.
The separate host RTL v2 changes only the current-publication qualifier.
"""
import ast
import hashlib
import json
from pathlib import Path
import types
from . import stream27_host_core_native_v1 as original
from . import stream27_host_core_native_v2 as parent

PIN='f6b458959e873cf1e31a44f8202b88ddfed15f8d7657572b5f7f5111c7c7fbf1'


def cases(n):
    result=original.cases(n)
    for case in result:
        words=list(case['initial']);case['initial']=tuple(words)
        for job in case['jobs']:
            current=list(words)
            for address,value in job['changes']:current[address]=value
            expected=original.ordinary_image(current,job['base'],job['count'],job['mask'],job['twice'])
            job['expected']=tuple(expected);words=list(expected)
    return result


def prepare(destination,*,n=32):
    path=original.ROOT/'reference/stream27_host_core_native_v2.py';raw=path.read_text()
    if hashlib.sha256(raw.encode()).hexdigest()!=PIN:raise ValueError('S4_HOST_IMMUTABLE_CORPUS_PARENT_DRIFT')
    nodes=[node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name=='prepare']
    if len(nodes)!=1:raise ValueError('S4_HOST_IMMUTABLE_CORPUS_PARENT_FUNCTION')
    node=nodes[0];body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    original_proxy=types.ModuleType('frozen_scalar_preparer_with_immutable_corpus');original_proxy.__dict__.update(vars(original));original_proxy.cases=cases
    namespace=dict(vars(parent));namespace['parent']=original_proxy
    exec(compile(body,str(path)+'[independent immutable expected image successor]','exec'),namespace)
    r=namespace['prepare'](destination,n=n);destination=Path(destination).resolve();source=destination/'inputs/fpga'
    local='reference/stream27_host_core_native_v3.py';target=source/'lineage'/local;target.write_bytes((original.ROOT/local).read_bytes())
    mpath=destination/'manifest.json';m=json.loads(mpath.read_text());m['sources']['lineage/'+local]=original.sha(target)
    mpath.write_text(json.dumps(m,indent=2)+'\n');r['manifest_sha256']=original.sha(mpath);r['source_count']=len(m['sources'])
    r['oracle_delta']='Only immutable independent expected images: later partial mutation cannot retroactively modify an earlier expected image; arithmetic/cycles/footers unchanged.'
    r['RTL_delta']='Separate host_core_v2 current-publication flag only; root/carry/NTT/recurrence/barrier/read/copy cycles unchanged.'
    r['failed_parent_native']='s4-aw5-scalar-host-t5b-q1-v1 actual expectedaddr3=7/actual0; historical corpus alias, no DUT arithmetic failure inference.'
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    if len(sys.argv)!=3:raise ValueError('S4_HOST_IMMUTABLE_CORPUS_USAGE destination n')
    r=prepare(sys.argv[1],n=int(sys.argv[2]));print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top')},indent=2))

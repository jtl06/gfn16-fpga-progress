"""Actual Verilator header filename V-prefix; preserved unlaunched v1 prep."""
import ast
import hashlib
import json
from pathlib import Path
from . import stream27_host_chain_reset_native_v1 as original


def prepare(destination):
    path=original.ROOT/'reference/stream27_host_chain_reset_native_v1.py';raw=path.read_text()
    node=next(x for x in ast.parse(raw).body if isinstance(x,ast.FunctionDef) and x.name=='prepare')
    body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    old="header=top+'___024root.h'"
    if body.count(old)!=1:raise ValueError('RESET_OBSERVER_V_PREFIX_ANCHOR')
    body=body.replace(old,"header='V'+top+'___024root.h'")
    ns=dict(vars(original));exec(compile(body,'[actual Verilator V header prefix]','exec'),ns)
    r=ns['prepare'](destination);destination=Path(destination).resolve();source=destination/'inputs/fpga'
    local='reference/stream27_host_chain_reset_native_v2.py';target=source/'lineage'/local;target.write_bytes((original.ROOT/local).read_bytes())
    mpath=destination/'manifest.json';m=json.loads(mpath.read_text());m['sources']['lineage/'+local]=original.parent.parent.parent.sha(target)
    mpath.write_text(json.dumps(m,indent=2)+'\n');r.update(manifest_sha256=original.parent.parent.parent.sha(mpath),source_count=len(m['sources']),
      preparation_delta='Header filename actual V-prefix, no DUT/observer/protocol changes; v1 unlaunched KeyError source preparation retained.')
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    r=prepare(sys.argv[1]);print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top','scope')},indent=2))

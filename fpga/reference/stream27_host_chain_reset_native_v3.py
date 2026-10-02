"""Explicit included entry-point rename; no nested main macro collision.

V2 actual C++ build failed before runtime, not a reset observation. Preserve
that packet; rename only its included long-main function and remove the outer
macro. All DUT RTL, observer rows, arithmetic and reset edges stay unchanged.
"""
import hashlib
import json
from pathlib import Path
from . import stream27_host_chain_reset_native_v2 as parent

PIN='c7fe8447e020753a68f9ae9d3a2621a75463305cdd33269825a1c47013e67697'


def prepare(destination):
    root=parent.original.ROOT
    if hashlib.sha256((root/'reference/stream27_host_chain_reset_native_v2.py').read_bytes()).hexdigest()!=PIN:raise ValueError('RESET_OBSERVER_CPP_PARENT_DRIFT')
    r=parent.prepare(destination);destination=Path(destination).resolve();source=destination/'inputs/fpga'
    included=source/'rtl/tb/stream27_host_chain_v1.cpp';s=included.read_text();old='int main(int argc,char** argv)'
    if s.count(old)!=1:raise ValueError('RESET_OBSERVER_EXPLICIT_MAIN_ANCHOR')
    included.write_text(s.replace(old,'int retained_long_main(int argc,char** argv)'))
    bench=source/'rtl/tb/stream27_host_chain_reset_observer_v1.cpp';s=bench.read_text()
    old='#define main retained_long_main\n#include "stream27_host_chain_v1.cpp"\n#undef main'
    if s.count(old)!=1:raise ValueError('RESET_OBSERVER_OUTER_MACRO_ANCHOR')
    bench.write_text(s.replace(old,'#include "stream27_host_chain_v1.cpp"'))
    local='reference/stream27_host_chain_reset_native_v3.py';target=source/'lineage'/local;target.write_bytes((root/local).read_bytes())
    mpath=destination/'manifest.json';m=json.loads(mpath.read_text())
    for path in (included,bench,target):m['sources'][str(path.relative_to(source))]=hashlib.sha256(path.read_bytes()).hexdigest()
    mpath.write_text(json.dumps(m,indent=2)+'\n');r.update(manifest_sha256=hashlib.sha256(mpath.read_bytes()).hexdigest(),source_count=len(m['sources']),
      observer_CPP_delta='Only explicit retained_long_main rename + remove outer macro; original nested macro redefinition/main duplicate caused actual nonzero C++ build, no native reset data in v2.')
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    r=prepare(sys.argv[1]);print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top','scope')},indent=2))

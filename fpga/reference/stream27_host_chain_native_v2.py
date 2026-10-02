"""Separate in-range wrong-index fault corpus; all RTL remains v1 exact.

Prepared-only v1 used count2/index2 for its wrong-index witness, which is also
out of range. This successor makes that one job count3 so index2 is specifically
wrong-order, while count2/index0 remains the distinct range fault. No native
v1 job was submitted, and its captured source preparation is preserved.
"""
import hashlib
import json
from pathlib import Path
from . import stream27_host_chain_native_v1 as parent

PIN='45c3185c6f236d6c041db454277a93e91c342e12560ba1f6a72e4a1b8b991701'


def prepare(destination,*,n=32,ordinal=False):
    if parent.sha(parent.ROOT/'reference/stream27_host_chain_native_v1.py')!=PIN:raise ValueError('S4_LONG_FAULT_CORPUS_PARENT_DRIFT')
    r=parent.prepare(destination,n=n,ordinal=ordinal);destination=Path(destination).resolve();source=destination/'inputs/fpga'
    bench=source/parent.BENCH;s=bench.read_text();old='d.warm_count=2;d.start=1;edge(d);'
    if s.count(old)!=1:raise ValueError('S4_LONG_WRONG_INDEX_ISOLATION_ANCHOR')
    bench.write_text(s.replace(old,'d.warm_count=type==2?3:2;d.start=1;edge(d);'))
    local='reference/stream27_host_chain_native_v2.py';target=source/'lineage'/local;target.write_bytes((parent.ROOT/local).read_bytes())
    mpath=destination/'manifest.json';m=json.loads(mpath.read_text());m['sources'][parent.BENCH]=parent.sha(bench);m['sources']['lineage/'+local]=parent.sha(target)
    mpath.write_text(json.dumps(m,indent=2)+'\n');r.update(manifest_sha256=parent.sha(mpath),source_count=len(m['sources']),
      fault_corpus_delta='Only wrong-index witness count2->3, index2 unchanged, now legal range but incorrect next1. Range witness count2/index0 unchanged. All generated RTL bytes, arithmetic/positive/control/calendar/footers unchanged.')
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    r=prepare(sys.argv[1],n=int(sys.argv[2]),ordinal=len(sys.argv)==4 and sys.argv[3]=='ordinal')
    print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top','long_counts','ordinal')},indent=2))

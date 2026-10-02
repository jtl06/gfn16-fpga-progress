"""Strengthen the native oracle to serial large divmod, preserving v1 inputs.

RTL is unchanged. This arithmetic reference is distinct from the RTL's
two-independent-splits and small-feedback recurrence.
"""
import hashlib
import json
from pathlib import Path
from .stream27_threefield_carry_native_v1 import ROOT,prepare as parent,sha,BENCH

BENCH_PIN='453e7e53efb4ac2982039614e0258974cebd4e7737c3f88c7dc633a20c4cdd29'
PARENT_PIN='08b619302df43e8c0310dd13692a1acff27a0cd62470301b0377a55b911c90ad'


def serial_bench(s):
    start=s.index('static Image blockcarry(');end=s.index('struct Frame',start)
    replacement='''static Image blockcarry(const Coefficients& c,uint32_t base){
    Image out;
    for(unsigned b=0;b<P;++b){I carry=0;
        for(unsigned row=0;row<T;++row){auto z=euclidean(c[b*T+row]+carry,base);carry=z.first;out.digits[b*T+row]=z.second;}
        auto tail=euclidean(carry,base);unsigned destination=(b+1)%P;
        need(tail.second<base && tail.first>=-I(BOUND) && tail.first<=I(BOUND),"S4_REFERENCE_BOUNDARY");
        int sign=b==P-1?-1:1;out.c0[destination]=sign*int32_t(tail.second);out.c1[destination]=sign*int32_t(tail.first);
    }
    need(canonical(c,base)==canonical(effective(out),base),"S4_REFERENCE_REPRESENTED_RESIDUE");return out;
}
'''
    return s[:start]+replacement+s[end:]


def prepare(destination,*,n=32):
    if sha(ROOT/BENCH)!=BENCH_PIN or sha(ROOT/'reference/stream27_threefield_carry_native_v1.py')!=PARENT_PIN:
        raise ValueError('S4_SERIAL_REFERENCE_PARENT_DRIFT')
    destination=Path(destination).resolve();r=parent(destination,n=n);source=destination/'inputs/fpga'
    path=source/BENCH;path.write_text(serial_bench(path.read_text()))
    lineage=source/'lineage/reference/stream27_threefield_carry_native_v2.py';lineage.write_bytes((ROOT/'reference/stream27_threefield_carry_native_v2.py').read_bytes())
    manifest=destination/'manifest.json';m=json.loads(manifest.read_text());m['sources'][BENCH]=sha(path)
    m['sources']['lineage/reference/stream27_threefield_carry_native_v2.py']=sha(lineage)
    manifest.write_text(json.dumps(m,indent=2)+'\n');r['manifest_sha256']=sha(manifest);r['source_count']=len(m['sources'])
    r['independent_reference']='Signed128 schoolbook + SERIAL large Euclidean divmod per block (not RTL parts/y/small-cell algorithm); canonical math equality is intermediate only.'
    r['parent_preparer_sha256']=PARENT_PIN;r['parent_bench_sha256']=BENCH_PIN
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    if len(sys.argv)!=3:raise ValueError('S4_THREEFIELD_SERIAL_USAGE destination n')
    r=prepare(sys.argv[1],n=int(sys.argv[2]));print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top')},indent=2))

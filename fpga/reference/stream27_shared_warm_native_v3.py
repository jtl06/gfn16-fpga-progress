"""Corrected small-DIF static wiring; fresh package, historical v1 preserved."""
import json
from pathlib import Path
from .stream27_shared_warm_native_v1 import prepare as parent_prepare,sha


def prepare(destination):
    destination=Path(destination).resolve();r=parent_prepare(destination)
    source=destination/'inputs/fpga';path=source/'rtl/tb/stream27_shared_warm_aw8_v1.cpp'
    s=path.read_text();old='"S4_DATA tick="+std::to_string(tick)+" lane="+std::to_string(lane)'
    new='"S4_DATA case="+std::to_string(counts.cases)+" tick="+std::to_string(tick)+" lane="+std::to_string(lane)+" expected="+std::to_string(physical->expected[reverse4(lane)*T+row])+" actual="+std::to_string(unpack(d.data_out,lane))'
    if s.count(old)!=1:raise ValueError('S4_V3_BENCH_ANCHOR')
    path.write_text(s.replace(old,new))
    manifest=destination/'manifest.json';m=json.loads(manifest.read_text());m['sources']['rtl/tb/stream27_shared_warm_aw8_v1.cpp']=sha(path)
    manifest.write_text(json.dumps(m,indent=2)+'\n');r['manifest_sha256']=sha(manifest)
    r.update(correction='Natural c0/c1 and ψ^(kT) constants statically permuted into the small DIF physical lane order.',
        expected_parent_failure='case2/tick143/lane0 expected19887389; wrong wiring predicted6017980',
        preserved_failure='queue/evidence/s4-aw8-shared-q1-v1/attempt-0/collected')
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    if len(sys.argv)!=2:raise ValueError('S4_V3_USAGE')
    print(json.dumps(prepare(sys.argv[1]),indent=2))

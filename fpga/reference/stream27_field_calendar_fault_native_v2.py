"""Correct only baseline output sampling phase, not missing-FIRST calendar.

The inherited field geometry records physical/commit output AFTER its tick's
posedge. This diagnostic samples before the posedge, so that same output is
visible at tick+1. The epoch pointwise due is an ACCEPTANCE pre-edge calendar:
its missing-FIRST assertion must remain exactly POINTWISE (39P8/41P16).
Frozen v1 failure is retained; all RTL and geometry constants are unchanged.
"""
import hashlib
import json
from pathlib import Path
from . import stream27_field_calendar_fault_native_v1 as parent

ROOT=parent.ROOT


def prepare(destination,*,p=8):
    r=parent.prepare(destination,p=p);destination=Path(destination).resolve();source=destination/'inputs/fpga'
    bench=source/parent.BENCH;text=bench.read_text()
    old='''need(!d.fault_pending&&!d.out_error,"S4_CALENDAR_UNMODIFIED_NORMAL");
   if(d.out_slot_valid){++physical;need(tick>=PHYSICAL&&tick<PHYSICAL+T,"S4_CALENDAR_PHYSICAL_ORDER");'''
    new='''need(!d.fault_pending&&!d.out_error,"S4_CALENDAR_UNMODIFIED_NORMAL");
   // Geometry PHYSICAL/SINK are POST-edge outputs. This loop observes PRE-edge.
   need(bool(d.out_slot_valid)==(tick>=PHYSICAL+1 && tick<PHYSICAL+T+1),
        "S4_CALENDAR_PHYSICAL_ORDER pre_tick="+std::to_string(tick)+" expected_first="+std::to_string(PHYSICAL+1)+" actual_slot="+std::to_string(d.out_slot_valid));
   need(bool(d.commit_valid)==(tick>=SINK+1 && tick<SINK+T+1),"S4_CALENDAR_COMMIT_PREEDGE");
   if(d.out_slot_valid){++physical;'''
    if text.count(old)!=1:raise ValueError('S4_CALENDAR_PRE_POST_PHASE_ANCHOR')
    bench.write_text(text.replace(old,new))
    local='reference/stream27_field_calendar_fault_native_v2.py';target=source/'lineage'/local;target.write_bytes((ROOT/local).read_bytes())
    path=destination/'manifest.json';m=json.loads(path.read_text())
    m['sources']={str(path.relative_to(source)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(source.rglob('*')) if path.is_file()}
    path.write_text(json.dumps(m,indent=2)+'\n')
    r.update(manifest_sha256=parent.sha(path),source_count=len(m['sources']),
        phase_delta='Only normal baseline pre-edge physical/commit comparison now PHYSICAL+1/SINK+1, with strict full per-edge slot equality and rich failure. Missing-FIRST pre-edge POINTWISE and registered error, external fault, reset duration, source RTL/geometry/footers/typednegative unchanged.',
        failed_v1='P8 actual normal branch rc1/S4_CALENDAR_PHYSICAL_ORDER before fault injection, preserved; not a missing-FIRST protection result.')
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    print(json.dumps(prepare(sys.argv[1],p=int(sys.argv[2])),indent=2))

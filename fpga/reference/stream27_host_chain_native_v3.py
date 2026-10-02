"""Qualify the existing raw completed diagnostic by actual cold acceptance.

No RTL/numeric/cycle expectation changes. Frozen scalar child completed_frames
retains the previous job's value until frame_accept. The long wrapper exposes
operations_started=0 until that actual event, then every completion bound must
hold. V2's unconditional bound during cached second-job setup was incorrect.
"""
import hashlib
import json
from pathlib import Path
from . import stream27_host_chain_native_v2 as parent

PIN='d0efd1e2b47ca002c3177f72e7c956ae65e0f5060c296bb8a517eb33f560d82a'


def prepare(destination,*,n=32,ordinal=False):
    root=parent.parent.ROOT
    if parent.parent.sha(root/'reference/stream27_host_chain_native_v2.py')!=PIN:raise ValueError('S4_LONG_DIAGNOSTIC_PARENT_DRIFT')
    r=parent.prepare(destination,n=n,ordinal=ordinal);destination=Path(destination).resolve();source=destination/'inputs/fpga'
    name=parent.parent.BENCH;bench=source/name;s=bench.read_text()
    old='need(d.operations_started<=count&&d.completed_squares<=count,"S4_LONG_ORDINAL_BOUND");'
    new='''need(d.operations_started<=count&&(d.operations_started==0 || d.completed_squares<=count),
            "S4_LONG_ORDINAL_BOUND job="+std::to_string(c.jobs)+" age="+std::to_string(elapsed)+" count="+std::to_string(count)+" started="+std::to_string(d.operations_started)+" completed="+std::to_string(d.completed_squares));'''
    if s.count(old)!=1:raise ValueError('S4_LONG_RAW_COMPLETION_QUALIFIER_ANCHOR')
    bench.write_text(s.replace(old,new))
    local='reference/stream27_host_chain_native_v3.py';target=source/'lineage'/local;target.write_bytes((root/local).read_bytes())
    mpath=destination/'manifest.json';m=json.loads(mpath.read_text());m['sources'][name]=parent.parent.sha(bench);m['sources']['lineage/'+local]=parent.parent.sha(target)
    mpath.write_text(json.dumps(m,indent=2)+'\n');r.update(manifest_sha256=parent.parent.sha(mpath),source_count=len(m['sources']),
      diagnostic_delta='Raw completed_squares bound qualified ONLY until actual first cold accept: operations_started0 then old child counter can persist; all later/full completion, ordinal/rawload/count/pop/numeric/cycle assertions unchanged. Rich failing age/job/count/started/completed added.',
      failed_v2='Actual GCP invocation e05a1eda357445c8bcb320be3d22bf80,14:42:38–14:47:07,reportb3bd23a9/stderrcaab4d38, runtime S4_LONG_ORDINAL_BOUND; preserved. No complete PRP/PASS inferred.')
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    r=prepare(sys.argv[1],n=int(sys.argv[2]),ordinal=len(sys.argv)==4 and sys.argv[3]=='ordinal')
    print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top','long_counts','ordinal')},indent=2))

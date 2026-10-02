"""Exact single-reset pre-release observer and declared rc1 source-fault witness."""
import hashlib
import json
from pathlib import Path
from . import stream27_host_chain_reset_native_v3 as parent


def prepare(destination):
    r=parent.prepare(destination);destination=Path(destination).resolve();source=destination/'inputs/fpga';root=parent.parent.original.ROOT
    bench=source/'rtl/tb/stream27_host_chain_reset_observer_v1.cpp';s=bench.read_text()
    old='reset(d);snapshot(d,history,age,1,"released");'
    new='''feed_clear(d);d.rst_n=0;d.clk=0;d.eval();snapshot(d,history,age,1,"assert_pre");
 d.clk=1;d.eval();snapshot(d,history,age,1,"assert_rise");d.clk=0;d.eval();snapshot(d,history,age,1,"assert_fall");
 need(!d.busy&&!d.done&&!d.error&&!d.read_valid&&!d.warm_done&&!d.canonical_ready&&!d.t5b_read_valid&&!d.t5b_done&&!d.t5b_busy,"S4_HOST_RESET_FLUSH");
 d.rst_n=1;d.clk=0;d.eval();snapshot(d,history,age,1,"release_pre");
 d.clk=1;d.eval();snapshot(d,history,age,1,"release_rise");d.clk=0;d.eval();snapshot(d,history,age,1,"released");
 need(!d.error&&!d.profile_cache_valid,"S4_HOST_RESET_CACHE");'''
    if s.count(old)!=1:raise ValueError('RESET_ORIGIN_PRIMARY_RESET_ANCHOR')
    s=s.replace(old,new);prefix=r['top']+'__DOT__candidate__DOT__engine__DOT__recurrence__DOT__arithmetic__DOT__field0__DOT__'
    anchor=' std::cout<<"}";'
    if s.count(anchor)!=1:raise ValueError('RESET_ORIGIN_RAW_PENDING_ANCHOR')
    additions='\n'.join(' std::cout<<",\\"'+label+'\\":"<<uint64_t(d.rootp->'+prefix+member+');' for label,member in
      [('raw_child_pending_mask','child_pending'),('raw_external_pending','__Vcellinp__epoch_protocol__external_fault_pending')])
    s=s.replace(anchor,additions+'\n'+anchor);bench.write_text(s)
    validator='reference/stream27_host_chain_reset_validate_v2.py';target=source/validator;target.write_bytes((root/validator).read_bytes())
    for local in (validator,'reference/stream27_host_chain_reset_native_v4.py'):
        target=source/'lineage'/local;target.write_bytes((root/local).read_bytes())
    mpath=destination/'manifest.json';m=json.loads(mpath.read_text());step=m['steps'][0]
    step.update(name='s4-long-reset-origin-expected-fault',expected_returncode=1,
      validator=dict(source=validator,function='validate',config=dict(aw=5,purpose='reset-origin-expected-fault'),assets={}))
    m['sources']={str(path.relative_to(source)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(source.rglob('*')) if path.is_file()}
    mpath.write_text(json.dumps(m,indent=2)+'\n');r.update(manifest_sha256=hashlib.sha256(mpath.read_bytes()).hexdigest(),source_count=len(m['sources']),
      scope='Expected rc1 broken-source reset diagnostic. Exact one reset edge unchanged, additional pre-deassert/release snapshots and raw pending mask; no functional reset/PRP PASS.',
      prior_observation='Actual observerv3 report51a65d0d/stdoutff1a200c,52 fresh snapshots age10 quiet/236 field-protocol fault atE1, hostdone+errorE2; reload fault stopped before same-history. Preserve partial record, not completed diagnosticPASS.')
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    r=prepare(sys.argv[1]);print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top','scope')},indent=2))

"""Isolated R10 base-ENA normal; uses existing bounded native package path."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from . import stream27_canonical_begin_split_bind as bind
from . import stream27_context_storage_combo_directbound_liveprobe_v3 as donor

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_canonical_begin_split_native.py'
BASE=ROOT/'results/throughput-20260929/trackS-r10-canonical-begin-split-native-v1'
CAPTURE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-registerederror-native-v1/aw8-normal/production-bundle.json'
TOP='genefer_stream27_canonical_begin_split_pair_v1'
CPP='rtl/tb/stream27_canonical_begin_split_pair.cpp'
ID='s4-p16-canonical-begin-split-normal-q1-v1'
FAULT_ID='s4-p16-canonical-begin-split-fault-q1-v1'
GATE='s4-p16-c2-combo-r9-aw8-normal-q1-v1'
DONOR_CPP_PIN='85aee844d2707eef3026b89fd5b96054fa161a3bba2ab84802f15ecb481781e4'
DONOR_HELPER_PIN='0412e9400592cd6131f9b99db1f7aecba7e6b4cbf29878188f337b0827fae476'
LIVE='''void live_base(H& h){
 auto x=input();
 for(uint32_t base:{1013u,1000000000u}){
  h.reset();h.load(x);h.clear();
  // Input changes after all LOADs, just before the accepted BEGIN edge.
  h.d.base=base;h.d.begin_canonical=1;h.edge();h.d.begin_canonical=0;
  need(h.d.local_busy&&!h.d.local_error,"R10_BEGIN_SPLIT_LIVE_ACCEPT");
  // Unrelated live base changes after BEGIN must not alter the active image.
  h.d.base=0;h.run();h.all(x);
 }
 need(h.reads==512&&h.images==2,"R10_BEGIN_SPLIT_LIVE_COUNTS");
 h.reads=h.images=0;
}
'''


def sha(raw):return hashlib.sha256(raw).hexdigest()
def need(ok,why):
    if not ok:raise ValueError('BEGIN_SPLIT_NATIVE_'+why)
def dump(path,obj):
    with Path(path).open('x') as f:json.dump(obj,f,indent=2);f.write('\n')


def role(mode='normal'):
    need(mode in ('normal','fault'),'MODE')
    need(sha((ROOT/donor.SELF).read_bytes())==DONOR_HELPER_PIN,'FROZEN_DONOR_WRAPPER')
    bundle=json.loads(CAPTURE.read_bytes())
    parent=bundle['files'][bind.OLD+'.sv']
    child=bind.bind_leaf(parent,enabled=1)
    need(bind.reverse_leaf(child)==parent,'COMPLETE_LEAF_REVERSE')
    wrapper=donor.wrapper().replace(donor.LOCAL,bind.NEW).replace(donor.PARENT,bind.OLD).replace(donor.TOP,TOP)
    cpp=(ROOT/donor.CPP).read_bytes()
    need(sha(cpp)==DONOR_CPP_PIN,'FROZEN_CPP')
    text=cpp.decode().replace(donor.TOP,TOP).replace('R8_DIRECTBOUND','R10_BEGIN_SPLIT')
    text=bind.once(text,'}\nint main(int argc,char** argv)',LIVE+'}\nint main(int argc,char** argv)')
    text=bind.once(text,'if(argc==1){normal(h);h.sample();','if(argc==1){live_base(h);normal(h);h.sample();')
    text=bind.once(text,'images=2 signed96_reads=516 dirty_read=1',
                   'images=2 signed96_reads=516 live_base_images=2 live_base_reads=512 dirty_read=1')
    if mode=='fault':
        # Reset on the exact final PROCESS edge: no stale image/read publication.
        # This is leaf eligibility, not an external host fault-barrier proof.
        insertion='''h.reset();h.load(input());h.begin();
 for(unsigned age=1;age<9*N;age++){h.clear();h.edge();need(h.d.local_busy&&!h.d.local_done,"R10_BEGIN_SPLIT_BEFORE_LAST");}
 h.d.rst_n=0;h.edge();need(!h.d.local_image_valid&&!h.d.local_done&&!h.d.local_read_valid,"R10_BEGIN_SPLIT_LAST_EDGE_RESET");
 h.d.rst_n=1;h.clear();for(unsigned k=0;k<4;k++)h.edge();
 h.reads=h.images=0;faults(h);'''
        text=bind.once(text,'h.reads=h.images=0;faults(h);',insertion)
    files={'rtl/'+bind.OLD+'.sv':parent.encode(),'rtl/'+bind.NEW+'.sv':child.encode(),
           'rtl/'+donor.RAM+'.sv':bundle['files'][donor.RAM+'.sv'].encode(),
           'rtl/'+TOP+'.sv':wrapper.encode(),CPP:text.encode()}
    for name in (donor.RUNTIME,SELF,'reference/stream27_canonical_begin_split_bind.py',
                 'reference/stream27_canonical_begin_split_model.py'):
        files[name]=(ROOT/name).read_bytes()
    files['lineage/'+donor.CPP]=cpp
    files['lineage/'+donor.SELF]=(ROOT/donor.SELF).read_bytes()
    need(sha(files[donor.RUNTIME])==donor.RUNTIME_PIN,'RUNTIME_PIN')
    snapshot={name:sha(raw) for name,raw in files.items() if name.endswith('.sv')}
    ready=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-p16-canonical-begin-split-v1',
       source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
       rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))
    expected='R10_BEGIN_SPLIT_PAIR_NORMAL_PASS aw=8 p=16 images=2 signed96_reads=516 live_base_images=2 live_base_reads=512 dirty_read=1 consecutive_reads=3 special_sentinel=1 paired_edges=1 os_threads_peak=1\n'
    if mode=='fault':
        # Same production/observer SV freeze; a separately authored negative CPP.
        frozen=json.loads((BASE/'normal-v1/manifest.json').read_bytes())['rtl_readiness']
        need(frozen['source_snapshot']==snapshot,'UNCHANGED_NORMAL_RTL')
        ready=frozen
        expected='R10_BEGIN_SPLIT_BOUND_PASS aw=8 p=16 live_checks=23024 u32_base=1 signed_extrema=1 zero_always_bad=1 c1_priority=1 origin_faults=4 paired_edges=1 os_threads_peak=1 runtime_contexts=1\n'
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='UNBOUND',output_parent='UNBOUND',
      sources={name:sha(raw) for name,raw in files.items()},build=dict(top=TOP,
       sv_sources=['rtl/'+name+'.sv' for name in (donor.RAM,bind.OLD,bind.NEW,TOP)],cpp_source=CPP,
       parameters={},cflags=['-std=c++17','-Werror=return-type','-DGFN16_RUNTIME_THREADS=1']),
      probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
      steps=[dict(name='begin-split-'+mode,argv=['{exe}']+(['--bounds'] if mode=='fault' else []),expected_returncode=0,expected_stdout=expected,expected_stderr='')],
      test_role='normal' if mode=='normal' else 'deliberate_fault',rtl_readiness=ready,begin_split=dict(parent_leaf_sha256=bind.PARENT_PIN,
        source_bundle_sha256=sha(CAPTURE.read_bytes()),added_edges=0,added_registers=0,
        source_reverse_exact=True,raw_rejected_private_base_may_differ=True,
        host_owner_publication_barrier_not_instantiated=True,no_whole_or_clock_claim=True))
    return manifest,files


def prepare(output,mode='normal'):
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    out=Path(output).resolve();need(out.is_relative_to(BASE) and not out.exists(),'FRESH_OUTPUT')
    need(not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'PAUSE')
    manifest,files=role(mode);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    manifest['source_root']=str(source);dump(out/'manifest.json',manifest)
    dump(out/'host-hours.json',candidate_ladder.budget_from_hourly())
    packet=out/'packet-01';profile='gcp-c4d-static01-v1';worker='s4-canon-begin-split-'+mode+'-01-v1'
    r=package.prepare(out/'manifest.json',source,profile,worker,'run',packet,out/'host-hours.json')
    ticket=json.loads((packet/'ticket.json').read_bytes())
    variant=dict(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
       manifest_sha256=sha((packet/'manifest.json').read_bytes()),worker_id=worker,profile=profile,native_root=ticket['native_root'],
       runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
       stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
       stager_dependencies=[dict(path=str(ROOT/n),sha256=sha((ROOT/n).read_bytes())) for n in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700)
    logical=dict(schema='gfn16-global-ticket-v1',id=ID if mode=='normal' else FAULT_ID,owner='ram27-recovery',
       created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
       tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',allowed_hosts=['gfn16-pilot-c4d','aethia'],
       resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
       minimum_ram_rationale='Four small N256 canonical modules; bounded4GiB component trial, no whole-model memory inference.',
       est_minutes=5,promotion_bound=False,test_role=manifest['test_role'],rtl_readiness=manifest['rtl_readiness'],
       packages=[variant],after=[GATE if mode=='normal' else ID],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',logical)
    return dict(id=logical['id'],ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_NATIVE')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path)
    p.add_argument('--mode',choices=('normal','fault'),default='normal');a=p.parse_args()
    print(json.dumps(prepare(a.output,a.mode),indent=2))

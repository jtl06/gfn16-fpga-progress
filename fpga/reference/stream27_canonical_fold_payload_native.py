"""Private exact protected-parent/fold-payload paired leaf qualification."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from . import stream27_canonical_fold_payload_bind as bind
from . import stream27_context_storage_combo_timing10_bind as parent
from . import stream27_context_storage_combo_directbound_liveprobe_v3 as donor

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_canonical_fold_payload_native.py'
CPP='rtl/tb/stream27_canonical_fold_payload.cpp'
TOP='genefer_stream27_canonical_fold_payload_pair_v1'
BASE=ROOT/'results/throughput-20260929/trackS-canonical-fold-payload-native-v1'
READY='2026-10-02T22:45:55Z'
IDS={mode:'s4-p16-canonical-fold-payload-'+mode+'-q1-v1' for mode in ('normal','fault','oracle')}
PINS={bind.SELF:'00e26e8a8265ab5eb3f2a8ea652c020d3d7cc0b801f409b3613ff340e467f358',
      bind.MODEL:'506364a2077caa906b24ae66b183b0fe036446280bd407f10b6ead7736ff296f',
      donor.RUNTIME:donor.RUNTIME_PIN,
      'rtl/tb/stream27_host_chain_full_reference_v1.h':'88849a77ad7c58fc99f6d56eeded2a772a78fbe2b2da03fabdf7ac71aaf12c54',
      'rtl/tb/stream27_shared_reference_ntt_v1.h':'c7837ba92829293131efda704dfdde347708641bf9aff46dccbcb87b825ba390'}


def sha(raw):return hashlib.sha256(raw).hexdigest()
def need(ok,why):
    if not ok:raise ValueError('FOLD_PAYLOAD_NATIVE_'+why)
def dump(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2);f.write('\n')


def wrapper():
    return donor.wrapper().replace(donor.PARENT,bind.OLD).replace(donor.LOCAL,bind.NEW).replace(donor.TOP,TOP)


def role(mode='normal'):
    need(mode in IDS,'MODE')
    for name,pin in PINS.items():need(sha((ROOT/name).read_bytes())==pin,'FROZEN_SOURCE:'+name)
    b=parent.prepare(256,enabled=1,lean_production=0)
    old=b['files'][bind.OLD+'.sv'];need(sha(old.encode())==bind.PARENT_SHA256,'EXACT_PROTECTED_PARENT')
    new=bind.bind_leaf(old,enabled=1)
    need(bind.bind_leaf(old,enabled=0)==old and bind.reverse_leaf(new)==old,'DISABLED_REVERSE_LITERAL')
    files={'rtl/'+bind.OLD+'.sv':old.encode(),'rtl/'+bind.NEW+'.sv':new.encode(),
           'rtl/'+donor.RAM+'.sv':b['files'][donor.RAM+'.sv'].encode(),'rtl/'+TOP+'.sv':wrapper().encode(),
           CPP:(ROOT/CPP).read_bytes(),SELF:(ROOT/SELF).read_bytes()}
    for name in PINS:files[name]=(ROOT/name).read_bytes()
    text=files[CPP].decode()
    need('RuntimeContext context;' in text and 'context(argc,argv),d(&context)' in text and
         text.index('gfn16_runtime::configure(*this,argc,argv)')<text.index('context(argc,argv),d(&context)'), 'RUNTIME_BEFORE_SINGLE_MODEL')
    need('small_whole_integer(effective,base)' in text and 'h.images==10&&h.reads==2564' in text,
         'INDEPENDENT_NORMAL_CORRECTION_ORACLE')
    argv=[] if mode=='normal' else ['--bounds' if mode=='fault' else '--wrong-word']
    expected='FOLD_PAYLOAD_PAIR_NORMAL_PASS aw=8 p=16 images=10 signed96_reads=2564 correction_images=8 dirty_read=1 consecutive_reads=3 special_sentinel=1 paired_edges=1 os_threads_peak=1\n'
    if mode=='fault':expected='FOLD_PAYLOAD_BOUND_PASS aw=8 p=16 live_checks=23024 u32_base=1 signed_extrema=1 zero_always_bad=1 c1_priority=1 origin_faults=4 paired_edges=1 os_threads_peak=1 runtime_contexts=1\n'
    if mode=='oracle':expected=''
    snapshot={n:sha(raw) for n,raw in files.items() if n.endswith('.sv')}
    readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=IDS[mode].removesuffix('-q1-v1'),
        source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
        rtl_ready_at_utc=READY)
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='UNBOUND',output_parent='UNBOUND',
       sources={n:sha(raw) for n,raw in files.items()},build=dict(top=TOP,
        sv_sources=['rtl/'+n+'.sv' for n in (donor.RAM,bind.OLD,bind.NEW,TOP)],cpp_source=CPP,parameters={},
        cflags=['-std=c++17','-Werror=return-type','-DGFN16_RUNTIME_THREADS=1']),
       probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
       steps=[dict(name='fold-payload-'+mode,argv=['{exe}']+argv,expected_returncode=1 if mode=='oracle' else 0,
        expected_stdout=expected,expected_stderr='FOLD_PAYLOAD_WRONG_WORD\n' if mode=='oracle' else '')],
       test_role='normal' if mode=='normal' else 'deliberate_fault',rtl_readiness=readiness,
       fold_payload=dict(parent_leaf_sha256=bind.PARENT_SHA256,new_leaf_sha256=sha(new.encode()),
        source_reverse_exact=True,protected_parent=True,aw=8,p=16,added_external_edges=0,
        normal_service_edges=2304,sentinel_service_edges=2560,normal_correction_images=8,
        independent_small_whole_integer=True,runtime_contexts=1,runtime_before_model=True,actual_OS_threads_checked=True,
        old_qualification_inherited=False,whole_owner_host_or_clock_instantiated=False,promotion_allowed=False))
    return m,files


def prepare(output,mode='normal'):
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    out=Path(output).resolve();need(out.is_relative_to(BASE) and not out.exists(),'FRESH_OUTPUT')
    need(not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'PAUSE')
    m,files=role(mode);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    m['source_root']=str(source);dump(out/'manifest.json',m)
    dump(out/'host-hours.json',candidate_ladder.budget_from_hourly());variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-canonical-fold-payload-'+mode+'-'+pair+'-v1';packet=out/('packet-'+pair)
        r=package.prepare(out/'manifest.json',source,profile,worker,'run',packet,out/'host-hours.json')
        ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
          manifest_sha256=sha((packet/'manifest.json').read_bytes()),worker_id=worker,profile=profile,native_root=ticket['native_root'],
          runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
          stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
          stager_dependencies=[dict(path=str(ROOT/n),sha256=sha((ROOT/n).read_bytes())) for n in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    logical=dict(schema='gfn16-global-ticket-v1',id=IDS[mode],owner='p16-mlab',
       created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
       tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',allowed_hosts=['gfn16-pilot-c4d','aethia'],
       resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
       minimum_ram_rationale='N256 four-module paired canonical leaf; finite4GiB exploratory component, not whole-model claim.',
       est_minutes=5,promotion_bound=False,test_role=m['test_role'],rtl_readiness=m['rtl_readiness'],packages=variants)
    if mode!='normal':logical.update(after=[IDS['normal']],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',logical)
    return dict(id=logical['id'],ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_NATIVE')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=tuple(IDS),default='normal');a=p.parse_args()
    print(json.dumps(prepare(a.output,a.mode),indent=2))

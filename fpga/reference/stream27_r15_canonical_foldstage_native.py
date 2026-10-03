"""Source-owned paired small/full canonical normal first, Azure-only."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from . import stream27_r15_canonical_foldstage_bind as b

ROOT=b.ROOT;SELF='reference/stream27_r15_canonical_foldstage_native.py'
CPP='rtl/tb/stream27_r15_canonical_foldstage.cpp'
TOP='genefer_stream27_r15_canonical_foldstage_pair_v1'
BASE=ROOT/'results/throughput-20261003/trackS-r15-canonical-foldstage-v1'
READY='2026-10-03T11:01:50Z'
PACKAGE_PIN='03ff2d89cb40d36a170ddb239500f611b76b069aa31cf1ae18ac65caf1c6c2c6'
STAGER_PIN='4112106d59052af6cd432356287577f147ff5964e21768bf53960fd52bbf6eed'
PROFILE_PIN='c6d0dd6cc08f305492f7569eb0dfd08a855e1c75373917c3c971efae8fc871eb'
RUNTIME='rtl/tb/native_runtime_context_v1.h'
HEADERS={RUNTIME:'afd27444d1b4c991d11c84482db08f2fcef62757968e96ac83c5d44e55622f90',
 'rtl/tb/stream27_host_chain_full_reference_v1.h':'88849a77ad7c58fc99f6d56eeded2a772a78fbe2b2da03fabdf7ac71aaf12c54',
 'rtl/tb/stream27_shared_reference_ntt_v1.h':'c7837ba92829293131efda704dfdde347708641bf9aff46dccbcb87b825ba390'}

def sha(raw):return hashlib.sha256(raw).hexdigest()
def dump(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def identifier(aw,mode):return f's4-p16-r15-canonical-foldstage-aw{aw}-{mode}-q1-v1'

def wrapper():
    ports=['input logic clk,rst_n,load_valid,begin_canonical,read_req',
      'input logic [AW-5:0] load_row','input logic [511:0] load_data,c0,c1',
      'input logic [31:0] base','input logic [AW-1:0] read_address']
    instances=[]
    for label,module in [('parent',b.OLD),('local',b.NEW)]:
        ports+=['output logic '+','.join(label+'_'+x for x in ('busy','done','error','image_valid','read_valid')),
          f'output logic [7:0] {label}_error_code',f'output logic [63:0] {label}_cycles',
          f'output logic [AW-1:0] {label}_read_address_out',f'output logic signed [95:0] {label}_read_data']
        names=('busy','done','error','image_valid','read_valid','error_code','cycles','read_address_out','read_data')
        instances.append(module+f' #(.AW(AW),.P(16)) {label}_dut (\n .clk,.rst_n,.load_valid,.begin_canonical,.read_req,.load_row,.load_data,.c0,.c1,.base,.read_address,\n '+
          ','.join(f'.{n}({label}_{n})' for n in names)+'\n);\n')
    return '// State-free native-only paired observer.\nmodule '+TOP+' #(parameter int AW=8)(\n'+',\n'.join(ports)+'\n);\n'+''.join(instances)+'endmodule\n'

def expected(aw,mode):
    n=1<<aw
    if mode=='normal':return f'R15_FOLDSTAGE_NORMAL_PASS aw={aw} p=16 images=5 signed96_reads={5*n+4} delta_per_image={3*n} normal_parent={9*n} normal_candidate={12*n} special_parent={10*n} special_candidate={13*n} independent_integer=1 dirty_read=1 II1_read=1 runtime_threads=1\n'
    return f'R15_FOLDSTAGE_FAULT_PASS aw={aw} cases=12 phase_resets=8 recovery_reads={8*n} digit_internal_priority=1 parent_fault_age=3 candidate_fault_age=4 payload_zero_assumed=0 runtime_threads=1\n'

def role(aw=8,mode='normal'):
    b.need(aw in (8,16) and mode in ('normal','fault'),'ROLE')
    old=b.parent();new=b.bind_leaf(old,enabled=1)
    ram=ROOT/'rtl/kernel/genefer_sdp_ram32.sv'
    b.need(sha(ram.read_bytes())=='993567fb68fdc216b9ff04489d1810f743b86564434e4b48261ad606b25d53b0','RAM_PIN')
    files={'rtl/'+b.OLD+'.sv':old.encode(),'rtl/'+b.NEW+'.sv':new.encode(),
      'rtl/genefer_sdp_ram32.sv':ram.read_bytes(),'rtl/'+TOP+'.sv':wrapper().encode(),
      CPP:(ROOT/CPP).read_bytes(),SELF:(ROOT/SELF).read_bytes(),b.SELF:(ROOT/b.SELF).read_bytes()}
    for name,pin in HEADERS.items():
        raw=(ROOT/name).read_bytes();b.need(sha(raw)==pin,'HEADER_PIN:'+name);files[name]=raw
    snapshot={n:sha(raw) for n,raw in files.items() if n.endswith('.sv')}
    ready=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=identifier(aw,mode).removesuffix('-q1-v1'),
      source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),rtl_ready_at_utc=READY)
    steps=[dict(name='canonical-foldstage-'+mode,argv=['{exe}']+([] if mode=='normal' else ['--fault']),
      expected_returncode=0,expected_stdout=expected(aw,mode),expected_stderr='')]
    if mode=='fault':steps.append(dict(name='canonical-foldstage-comparator',argv=['{exe}','--wrong-word'],
      expected_returncode=1,expected_stdout='',expected_stderr='FOLDSTAGE_WRONG_WORD\n'))
    return dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='UNBOUND',output_parent='UNBOUND',
      sources={n:sha(raw) for n,raw in files.items()},build=dict(top=TOP,
        sv_sources=['rtl/'+n+'.sv' for n in ('genefer_sdp_ram32',b.OLD,b.NEW,TOP)],cpp_source=CPP,parameters=dict(AW=aw),
        cflags=['-std=c++17','-Werror=return-type','-DGFN16_RUNTIME_THREADS=1',f'-DGFN16_CANON_AW={aw}']),
      probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
      steps=steps,test_role='normal' if mode=='normal' else 'deliberate_fault',rtl_readiness=ready,
      foldstage=dict(parent_leaf_sha256=b.PARENT_SHA256,candidate_leaf_sha256=sha(new.encode()),
        exact_default_and_reverse=True,aw=aw,p=16,added_digit_edge=1,model_service_delta=3*(1<<aw),
        old_phase_fault_edges_preserved=False,PROCESS_fault_shifted_exactly_one_edge=True,
        no_public_ports_changed=True,accepted_BEGIN_snapshots_unchanged=True,no_warm_controller_instantiated=True,
        runtime_config_before_model=True,no_initial_payload_zero_assumption=True,promotion_allowed=False)),files

def prepare(output,aw=8,mode='normal',package_now=True):
    out=Path(output).resolve();b.need(out.is_relative_to(BASE) and not out.exists(),'FRESH_OUTPUT')
    m,files=role(aw,mode);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as f:f.write(raw)
    m['source_root']=str(source);dump(out/'manifest.json',m)
    if not package_now:return dict(id=identifier(aw,mode),manifest=str(out/'manifest.json'),status='SOURCE_PREPARED')
    return package(out,aw,mode)

def package(out,aw,mode,*,logical_id=None):
    from fpga.tools import native_class_package_v4 as pkg
    out=Path(out);manifest=json.loads((out/'manifest.json').read_bytes());source=Path(manifest['source_root'])
    b.need(sha((ROOT/'tools/native_class_package_v4.py').read_bytes())==PACKAGE_PIN,'PACKAGE_PIN')
    b.need(sha((ROOT/'tools/native_package_v6.py').read_bytes())==STAGER_PIN,'STAGER_PIN')
    from fpga.tools import global_queue_v1 as queue
    provider=queue.provider_capture_ref()
    budget=pkg.meter().make_budget('gfn16-azure-f16',3715,str(Path(provider['path']).relative_to(ROOT)),
      provider['sha256'],pkg.source_identity(manifest),PROFILE_PIN)
    dump(out/'azure-host-hours.json',budget);variants=[]
    native_id=logical_id or identifier(aw,mode)
    for pair in ('1213','1415'):
        profile='azure-f16-static'+pair+'-v1';worker=native_id.replace('-q1-','-'+pair+'-')
        packet=out/('packet-'+pair);r=pkg.prepare(out/'manifest.json',source,profile,worker,'run',packet,out/'azure-host-hours.json')
        ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
          manifest_sha256=sha((packet/'manifest.json').read_bytes()),worker_id=worker,profile=profile,native_root=ticket['native_root'],
          runner='tools/native_class_package_v4.py',runner_sha256=PACKAGE_PIN,stager=str(ROOT/'tools/native_package_v6.py'),
          stager_sha256=STAGER_PIN,stager_dependencies=[dict(path=str(ROOT/n),sha256=sha((ROOT/n).read_bytes()))
              for n in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    logical=dict(schema='gfn16-global-ticket-v1',id=native_id,owner='p16-mlab',
      created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
      tool_identity='azure-f16-verilator5032-gcc13-python312-v1',allowed_hosts=['gfn16-azure-f16'],
      resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,
      minimum_ram_rationale='Paired canonical component on admitted Azure2physical/model1/8GiB/j2, no whole model.',
      est_minutes=5,promotion_bound=False,test_role=manifest['test_role'],rtl_readiness=manifest['rtl_readiness'],packages=variants)
    if aw==16 or mode!='normal':logical.update(after=[identifier(aw if mode!='normal' else 8,'normal')],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',logical)
    return dict(id=logical['id'],ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_SUBMITTED')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--aw',type=int,choices=(8,16),default=8)
    p.add_argument('--mode',choices=('normal','fault'),default='normal');p.add_argument('--source-only',action='store_true');a=p.parse_args()
    print(json.dumps(prepare(a.output,a.aw,a.mode,not a.source_only),indent=2))

"""Private metadata-transport component, normal-first standing queue packets.

No whole arithmetic gate or fault authority inheritance; unit deliberately
retains malformed payload bits and checks reset masking/preeedge consumption.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from fpga.reference import stream27_crt_tag_delay_bind as binder

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_crt_tag_delay_native.py'
CPP = 'rtl/tb/stream27_crt_tag_delay_v1.cpp'
TOP = 'genefer_stream27_crt_tag_pair_v1'
BASE = ROOT / 'results/throughput-20260929/trackS-r11-crt-tag-delay-v1'
IDS = {'normal':'s4-r11-crt-tag-delay-normal-q1-v1', 'reset':'s4-r11-crt-tag-delay-reset-q1-v1'}
READY = '2026-10-02T19:30:27Z'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def wrapper():
    text = f'''module {TOP}(input logic clk,rst_n,joined,
 input logic [575:0] write_words,output wire [575:0] parent_head,candidate_head);
'''
    for g in range(9):
        w = 30+g
        for label, module in [('parent',binder.MODULE+'_parent'),('candidate',binder.MODULE)]:
            text += f''' {module} #(.WORD_W({w})) {label}{g} (
  .clk,.rst_n,.joined,.write_word(write_words[{64*g}+:{w}]),.head({label}_head[{64*g}+:{w}]));
 assign {label}_head[{64*g+w}+:{64-w}]='0;
'''
    return text + 'endmodule\n'


def expected(reset=False):
    """Count driver observations, not execute HDL or arithmetic reference."""
    mask = (1<<64)-1
    def token(c,g):
        x=((c+17)*0x9e3779b97f4a7c15+g)&mask
        x=((x^(x>>30))*0xbf58476d1ce4e5b9)&mask
        x=((x^(x>>27))*0x94d049bb133111eb)&mask
        return x^(x>>31)
    valid = [False]*16
    cycles = checks = 0
    def tick(joined,stop,rst=True):
        nonlocal cycles, checks, valid
        checks += 9*valid[-1]
        valid = [bool(joined and not stop)]+valid[:-1] if rst else [False]*16
        checks += 18*valid[-1]
        cycles += 1
    if not reset:
        for c in range(4096):
            tick(c<64 or token(c,0)%5!=0,c%97==11)
    else:
        for age in range(40):
            valid = [False]*16
            for _ in range(3):tick(True,False,False)
            for _ in range(age):tick(True,False)
            valid = [False]*16
            for i in range(3):tick(i%2==0,False,False)
            for i in range(128):tick(i<64 or token(cycles,1)%3!=0,i%31==17)
    return f'CRT_TAG_{"RESET" if reset else "NORMAL"}_PASS geometries=9 cycles={cycles} comparisons={checks} preedge=exact\n'


def role(mode='normal'):
    from fpga.reference.stream27_r11_density_audit import audit
    binder.need(mode in IDS,'UNIT_MODES_ONLY')
    files = {'rtl/'+binder.MODULE+'.sv':binder.bind_leaf().encode(),
             'rtl/'+binder.MODULE+'_parent.sv':binder.bind_leaf(0).replace(binder.MODULE,binder.MODULE+'_parent').encode(),
             'rtl/'+TOP+'.sv':wrapper().encode()}
    for name in (binder.P2,'rtl/kernel/genefer_stream27_mdc_fifo_smallreg_v1.sv',
                 'rtl/kernel/genefer_stream27_mdc_commutator_sync.sv',CPP,
                 'rtl/tb/native_runtime_context_v1.h',SELF,
                 'reference/stream27_crt_tag_delay_bind.py','reference/stream27_r11_density_audit.py'):
        files[name]=(ROOT/name).read_bytes()
    files['lineage/copied-root-density-audit.json']=(json.dumps(audit(),sort_keys=True)+'\n').encode()
    steps=[dict(name='crt-tag-'+mode,argv=['{exe}']+(['--reset-test'] if mode=='reset' else []),
                expected_returncode=0,expected_stdout=expected(mode=='reset'),expected_stderr='')]
    if mode=='reset':
        steps.append(dict(name='crt-tag-wrong-head-control',argv=['{exe}','--wrong-head'],
                          expected_returncode=1,expected_stdout='',expected_stderr='CRT_TAG_CANDIDATE_REFERENCE\n'))
    snapshot={name:sha(raw) for name,raw in files.items() if name.endswith('.sv')}
    readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-r11-crt-tag-delay-v1',
        source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),rtl_ready_at_utc=READY)
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='UNBOUND',output_parent='UNBOUND',
        sources={name:sha(raw) for name,raw in files.items()},
        build=dict(top=TOP,sv_sources=[name for name in files if name.endswith('.sv')],cpp_source=CPP,parameters={},
            cflags=['-std=c++17','-Werror=return-type','-DGFN16_RUNTIME_THREADS=1']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=steps,test_role='normal' if mode=='normal' else 'deliberate_fault',rtl_readiness=readiness,
        scope='Isolated W30..38 shared CRT metadata D16, joined-only stage0 hold, independent shift oracle; preedge tail bit exact. No whole numeric/fault/clock/LAB qualification.',
        promotion_allowed=False)
    return manifest,files


def dump(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2);stream.write('\n')


def prepare(output,mode='normal'):
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    out=Path(output).resolve()
    binder.need(out.is_relative_to(BASE) and not out.exists(),'FRESH_OWN_OUTPUT')
    binder.need(not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'PAUSE')
    manifest,files=role(mode);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    manifest['source_root']=str(source);dump(out/'manifest.json',manifest)
    dump(out/'host-hours.json',candidate_ladder.budget_from_hourly());variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-r11-crt-tag-delay-'+mode+'-'+pair+'-v1';packet=out/('packet-'+pair)
        r=package.prepare(out/'manifest.json',source,profile,worker,'run',packet,out/'host-hours.json')
        ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
            manifest_sha256=sha((packet/'manifest.json').read_bytes()),worker_id=worker,profile=profile,native_root=ticket['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/n),sha256=sha((ROOT/n).read_bytes())) for n in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    logical=dict(schema='gfn16-global-ticket-v1',id=IDS[mode],owner='p16-mlab',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P2',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        allowed_hosts=['gfn16-pilot-c4d','aethia'],resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=4,minimum_ram_rationale='Bounded small paired metadata-only leaf, no full arithmetic; exploration4GiB.',
        est_minutes=5,promotion_bound=False,test_role=manifest['test_role'],rtl_readiness=manifest['rtl_readiness'],packages=variants)
    if mode!='normal':logical.update(after=[IDS['normal']],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',logical)
    return dict(id=logical['id'],ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_NATIVE')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=tuple(IDS),default='normal');args=parser.parse_args()
    print(json.dumps(prepare(args.output,args.mode),indent=2))

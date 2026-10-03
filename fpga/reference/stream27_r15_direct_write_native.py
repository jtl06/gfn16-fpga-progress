"""AUTHOR core-clock direct-write/real-RAM fixture. No PCIe, CDC or whole core.

Only emits native-source-gate inputs. The dispatcher supplies the newly admitted
Azure-FIT package route; deleted Azure-SIM and non-Azure profiles are forbidden.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/throughput-20260929/trackS-r15-direct-write-native-v1'
SELF = 'reference/stream27_r15_direct_write_native.py'
TOP = 'stream27_r15_direct_write_guard'
CPP = 'rtl/tb/stream27_r15_direct_write_guard.cpp'
SV = 'rtl/tb/stream27_r15_direct_write_guard.sv'
RUNTIME = 'rtl/tb/native_runtime_context_v1.h'
PINS = {
 'rtl/kernel/genefer_stream27_r15_direct_write_guard_v1.sv': '49fe6d62a03979723598249d813d040c0e19e50db39a453bc51e955096df62c9',
 'rtl/kernel/genefer_stream27_r15_host_image_ack_v1.sv': '39c03859d05315d46bed95de016103ad5a1622588d16745943dedd2f5ed661b5',
 'rtl/kernel/genefer_sdp_ram32.sv': '993567fb68fdc216b9ff04489d1810f743b86564434e4b48261ad606b25d53b0',
 RUNTIME: 'afd27444d1b4c991d11c84482db08f2fcef62757968e96ac83c5d44e55622f90',
}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def need(ok, why):
    if not ok:
        raise ValueError('R15_DIRECT_WRITE_' + why)

def role(n=32, mode='normal'):
    need(n in (32,256) and mode in ('normal','fault'), 'BOUNDED_ROLE')
    files={p:(ROOT/p).read_bytes() for p in (*PINS,CPP,SV,SELF)}
    for p,pin in PINS.items():
        need(sha(files[p])==pin,'FROZEN_'+p)
    snapshot={p:sha(raw) for p,raw in files.items() if p.endswith('.sv')}
    aw=n.bit_length()-1
    counters=(f'cases=14 recovery_reads={n}' if mode=='fault' else
              f'writes={2*(n+32)} reads={4*n} peer_captures={2*n} port_stalls={2*((n+6)//7)}')
    expected=f'R15_DIRECT_WRITE_{mode.upper()}_PASS n={n} {counters} runtime_threads=1 core_clock_only=1\n'
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='UNBOUND',output_parent='UNBOUND',
      sources={p:sha(raw) for p,raw in files.items()},
      build=dict(top=TOP,sv_sources=[p for p in PINS if p.endswith('.sv')]+[SV],cpp_source=CPP,
                 parameters=dict(AW=aw),cflags=['-std=c++17','-Werror=return-type','-DGFN16_RUNTIME_THREADS=1',f'-DR15_N={n}']),
      probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
      steps=[dict(name='direct-write-'+mode,argv=['{exe}']+(['--fault'] if mode=='fault' else []),
                  expected_returncode=0,expected_stdout=expected,expected_stderr='')],
      test_role='normal' if mode=='normal' else 'deliberate_fault',
      rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-r15-direct-write-v1',source_snapshot=snapshot,
         candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
         rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')),
      direct_write=dict(n=n,fixture_version=2,production_pins={p:pin for p,pin in PINS.items() if p.endswith('.sv')},
         author='ram27_recovery',independent_review=False,core_clock_only=True,actual_shadow_ram=True,
         correction_registers=64,body_words=n,correction_words=32,registered_ack_before_commit=True,
         peer_capture_and_same_context_port_preemption=True,public_authority_fixture='guard one-edge publish pulse; begin/cancel/reset revoke transaction, no RAM rollback',
         pci_express=False,cdc=False,whole_core=False,physical_mapping=False,execution_host_policy='Azure-FIT only; no deleted Azure-SIM'))
    return manifest,files

def prepare(output,n=32,mode='normal'):
    out=Path(output).resolve()
    need(out.is_relative_to(BASE) and not out.exists(),'FRESH_OUTPUT')
    need(not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'PAUSE')
    manifest,files=role(n,mode)
    source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(raw)
    manifest['source_root']=str(source)
    with (out/'manifest.json').open('x') as stream:json.dump(manifest,stream,indent=2);stream.write('\n')
    return dict(status='SOURCE_PREPARED_NOT_SUBMITTED',manifest=str(out/'manifest.json'),source_root=str(source),
                proposed_id=f's4-r15-direct-write-n{n}-{mode}-q1-v2',execution='Azure-FIT package admission required')


def package_role(role):
    """Capture unchanged prepared role through the adopted ordinary Azure route."""
    from fpga.tools import native_class_package_v4 as package
    role=Path(role).resolve()
    direct_cold=role.is_relative_to(ROOT/'results/throughput-20260929/trackS-r15-direct-cold-native-v1')
    need(role.is_relative_to(BASE) or direct_cold,'OWN_ROLE')
    mr=(role/'manifest.json').read_bytes();m=json.loads(mr);source=Path(m['source_root'])
    need(source==role/'source/fpga','EXACT_ROLE_SOURCE')
    for name,pin in m['sources'].items():need(sha((source/name).read_bytes())==pin,'ROLE_PIN')
    runner='tools/native_class_package_v4.py';stager='tools/native_package_v6.py'
    rp='c2eb7148d89db89caec767ae876d399ef3f367562f1f1e177a100acf753d6e8c'
    sp='878138db412a83482b7959ae48fbd4e3199aad4a5edae77e79cd08c6a4bc8209'
    need(sha((ROOT/runner).read_bytes())==rp and sha((ROOT/stager).read_bytes())==sp,'ADOPTED_PACKET_PINS')
    ip='60581bfa5349c90a15179e93baa18fa7bbc2914b850b6b74d206cd92dc8faf89'
    provider='queue/provider-cost-status/azure-inputs-'+ip+'.json'
    budget=package.meter().make_budget('gfn16-azure-f16',3715,provider,ip,package.source_identity(m),package.F16_PROFILE_SHA)
    def dump(path,value):
        with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
    dump(role/'azure-host-hours.json',budget)
    n=256 if direct_cold else m['direct_write']['n'];mode='normal' if m['test_role']=='normal' else 'fault'
    version=m.get('r15_direct_native' if direct_cold else 'direct_write',{}).get('fixture_version',1)
    identifier=f's4-r15-direct-cold-aw8-{mode}-q1-v{version}' if direct_cold else f's4-r15-direct-write-n{n}-{mode}-q1-v{version}'
    variants=[]
    for pair in ('1213','1415'):
        profile='azure-f16-static'+pair+'-v1';worker=identifier.replace('-q1-','-'+pair+'-')
        out=role/('packet-'+pair)
        r=package.prepare(role/'manifest.json',source,profile,worker,'run',out,role/'azure-host-hours.json')
        ticket=json.loads((out/'ticket.json').read_bytes())
        variants.append(dict(archive=str(out/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
            manifest_sha256=sha((out/'manifest.json').read_bytes()),worker_id=worker,profile=profile,native_root=ticket['native_root'],
            runner=runner,runner_sha256=rp,stager=str(ROOT/stager),stager_sha256=sp,
            stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes())) for p in
                ('tools/native_package_v5.py','tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    logical=dict(schema='gfn16-global-ticket-v1',id=identifier,owner='ram27-recovery',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P1',kind='sim',needs='verilator',tool_identity='azure-f16-verilator5032-gcc13-python312-v1',
        allowed_hosts=['gfn16-azure-f16'],resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,
        est_minutes=25 if direct_cold else 5,promotion_bound=False,test_role=m['test_role'],rtl_readiness=m['rtl_readiness'],packages=variants)
    dependency=(f's4-r15-direct-cold-aw8-normal-q1-v{version}' if mode=='fault' else None) if direct_cold else (
        f's4-r15-direct-write-n{n}-normal-q1-v{version}' if mode=='fault' else (f's4-r15-direct-write-n32-normal-q1-v{version}' if n==256 else None))
    if dependency:logical.update(after=[dependency],on='PASS_expected_contracts')
    dump(role/'global-ticket.json',logical)
    need((role/'manifest.json').read_bytes()==mr,'UNCHANGED_CAPTURE')
    return dict(id=identifier,ticket=str(role/'global-ticket.json'),status='PREPARED_NOT_SUBMITTED')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--n',type=int,choices=(32,256),default=32);p.add_argument('--mode',choices=('normal','fault'),default='normal')
    args=p.parse_args();print(json.dumps(prepare(args.output,args.n,args.mode),indent=2))

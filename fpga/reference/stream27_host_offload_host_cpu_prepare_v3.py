"""Additive explicit-empty-stderr packet repair; v2 preparation is preserved.

One CPU-only host gate on the exact frozen R14 AW8 source capture.

Copies the 67 RTL/config bytes without re-emission. An unused single simulator
model retains the existing runtime probe; neither command evaluates that model.
Full-size linear host conversion/finalization executes only on admitted Linux.
No chip equivalence, FPGA time, transport or overlap claim follows this role.
"""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from fpga.reference import stream27_host_offload_host_benchmark_output_v2 as output

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_host_offload_host_cpu_prepare_v3.py'
CPP='rtl/tb/stream27_host_offload_host_cpu_v2.cpp'
HEADER='rtl/tb/stream27_host_offload_host_v2.h'
HELPER='rtl/tb/stream27_host_offload_host_benchmark_v2.h'
VALIDATOR='reference/stream27_host_offload_host_benchmark_output_v2.py'
PINS={HEADER:'7679e85713662635476124b0bad2e91954a08d8a27dd3f25db127b23da9d0720',
      HELPER:'8a6ddea9b4729ab9ce43533bb841f271ab66fa215f5f5916d83176306d3a49a8',
      VALIDATOR:'c330365f6d2c02285c63ad599c09e761106e8812bec9227a14ab73633db5cfac'}
DONOR=ROOT/'results/throughput-20260929/trackS-r14-host-offload-equivalence-v1/aw8-normal-v1'
DONOR_PIN='2334851647aebbfa2fcd6b70258af5325365c153e90f0e74d8a6f518724620cc'
BASE=ROOT/'results/throughput-20260929/trackS-r14-host-cpu-v3'
ID='s4-r14-host-cpu-q1-v3'


def need(ok,why):
    if not ok:raise ValueError('R14_HOST_CPU_PREP_'+why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def role():
    need(sha((DONOR/'manifest.json').read_bytes())==DONOR_PIN,'EXACT_DONOR_MANIFEST')
    donor=json.loads((DONOR/'manifest.json').read_bytes())
    files={name:(DONOR/'source/fpga'/name).read_bytes() for name in donor['sources']}
    need(all(sha(files[name])==pin for name,pin in donor['sources'].items()),'CAPTURED_CLOSURE')
    need(len(donor['build']['sv_sources'])==67 and donor['build']['runtime_threads']==1,
         'EXACT_67_RTL_RUNTIME_ONE')
    for name,pin in PINS.items():
        raw=(ROOT/name).read_bytes();need(sha(raw)==pin,'FROZEN_HOST_HELPER:'+name);files[name]=raw
    for name in (CPP,SELF):files[name]=(ROOT/name).read_bytes()
    text=files[CPP].decode()
    need(text.count('DUT model(&context)')==1 and
         text.index('gfn16_runtime::configure(context,argc,argv)')<text.index('DUT model(&context)') and
         '.eval(' not in text and 'r14_host_cpu_benchmark(3)' in text,'NO_DUT_EVALUATION')
    manifest=copy.deepcopy(donor)
    # Keep every top/parameter/cflag/ROM/config byte; only the host driver and
    # typed commands change. The donor's failed import-only gate is not a PASS.
    manifest['build']['cpp_source']=CPP
    manifest['steps']=[
        dict(name='r14-host-cpu-small-atomic-selfcheck',argv=['{exe}','--host-selfcheck'],
             expected_returncode=0,expected_stderr='',expected_stdout='R14_HOST_CPU_SELFCHECK_PASS checks=301 n=32 signed=-1 special=both atomic=1\n'),
        dict(name='r14-host-cpu-synthetic-full-timing',argv=['{exe}','--host-benchmark'],
             expected_returncode=0,validator=dict(source=VALIDATOR,function='validate',config=output.config(3),assets={}))]
    manifest['source_root']=manifest['output_parent']='UNBOUND'
    manifest['sources']={name:sha(raw) for name,raw in files.items()}
    need(all(files[name]==(DONOR/'source/fpga'/name).read_bytes()
             for name in donor['build']['sv_sources']),'RTL_BYTE_IDENTICAL')
    snapshot={name:manifest['sources'][name] for name in donor['build']['sv_sources']}
    manifest['test_role']='normal'
    manifest['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=ID,
        source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
        rtl_ready_at_utc='2026-10-03T00:05:00Z')
    manifest['r14_host_cpu']=dict(host_api_sha256=PINS[HEADER],benchmark_helper_sha256=PINS[HELPER],
        donor_manifest_sha256=DONOR_PIN,all_67_sv_and_build_config_retained=True,
        dut_linked_but_never_evaluated=True,synthetic_input=True,small_native_selfchecks=301,
        full_final_bytes_bound_to_frozen_worker_oracle=True,backend_transport_overlap_excluded=True,
        chip_equivalence=False,promotion_allowed=False)
    return manifest,files


def dump(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def prepare():
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    out=BASE/'cpu-q1-v3'
    need(not out.exists() and not any((ROOT/name).exists() for name in ('queue/PAUSE','docs/briefs/PAUSE')),
         'FRESH_UNPAUSED')
    manifest,files=role();source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
    manifest['source_root']=str(source.resolve());dump(out/'manifest.json',manifest)
    dump(out/'host-hours.json',candidate_ladder.budget_from_hourly());variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-r14-host-cpu-'+pair+'-v3';packet=out/('packet-'+pair)
        result=package.prepare(out/'manifest.json',source,profile,worker,'run',packet,out/'host-hours.json')
        ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
            worker_id=worker,profile=profile,native_root=ticket['native_root'],runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/name),sha256=sha((ROOT/name).read_bytes()))
                                 for name in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    logical=dict(schema='gfn16-global-ticket-v1',id=ID,owner='canonical-native-bench-r14-host',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',allowed_hosts=['gfn16-pilot-c4d','aethia'],
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
        minimum_ram_rationale='Captured bounded AW8 twin model is unused; 8GiB desired/4GiB exploratory minimum, no proven peak.',
        est_minutes=10,promotion_bound=False,test_role='normal',rtl_readiness=manifest['rtl_readiness'],packages=variants)
    dump(out/'global-ticket.json',logical)
    return dict(id=ID,ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_EXECUTED',compiled_sv=67,
                chip_equivalence=False,synthetic_host_timing_only=True)


if __name__=='__main__':print(json.dumps(prepare(),indent=2))


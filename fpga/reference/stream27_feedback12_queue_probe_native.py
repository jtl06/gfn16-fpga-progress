"""R12 retained queued descriptor guards; passive observer, simulated q-bit faults."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))
SELF='reference/stream27_feedback12_queue_probe_native.py'
CPP='rtl/tb/stream27_feedback12_queue_probe.cpp'
DRIVER='rtl/tb/stream27_feedback12_queue_driver.cpp'
HEADER='rtl/tb/r12_queue_probe_config.h'
PILOT=ROOT/'results/throughput-20260929/trackS-c2-feedback12-ownlong-v1/own100-serial-v1'
BASE=ROOT/'results/throughput-20260929/trackS-c2-feedback12-queue-native-v1'
NORMAL='s4-p16-c2-r12-queue-normal-q1-v1'
FAULTS='s4-p16-c2-r12-queue-faults-q1-v1'
NFOOTER='R12_QUEUE_NORMAL_PASS squares=200 signed96_reads=262144 independent_reference=1\n'
FFOOTER='R12_QUEUE_FAULT_PASS cases=2 index=1 generation=1 pre_accept_recheck=1 quiet_edges=16 recovered_signed96_reads=524288 simulation_only=1 host_gl_unimplemented=1\n'


def need(ok,label):
    if not ok:raise ValueError('R12_QUEUE_'+label)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def dump(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def role(faults=False):
    from fpga.reference import stream27_context_feedback12_native as normal
    from fpga.reference import stream27_context_feedback12_long_native as pilot
    need(type(faults) is bool,'BOOLEAN_ROLE')
    mr=(PILOT/'manifest.json').read_bytes();m=json.loads(mr)
    files={name:(PILOT/'source/fpga'/name).read_bytes() for name in m['sources']}
    need(all(sha(files[name])==pin for name,pin in m['sources'].items()),'OWN_PILOT_CLOSURE')
    production=json.loads((normal.ROOT/'results/throughput-20260929/trackS-c2-feedback12-native-v1/full-normal/production-bundle.json').read_bytes())
    need(len(production['files'])==58 and len(m['build']['sv_sources'])==59 and
         m['build']['parameters']==dict(production['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42) and
         all(files['rtl/'+name]==body.encode() for name,body in production['files'].items()),
         'EXACT58_PARAMETERS')
    observer='rtl/'+m['build']['top']+'.sv';before=files[observer].decode()
    anchor=' output logic [15:0] dbg_generation\n);'
    ports=' output logic [15:0] dbg_generation,\n output logic probe_queue_needed,probe_queue_bad,probe_stop\n);'
    monitor=(' assign probe_queue_needed=candidate.engine.command_needed;\n'
             ' assign probe_queue_bad=candidate.engine.queued_command_bad;\n'
             ' assign probe_stop=candidate.safety_error;\n')
    after=normal.once(normal.once(before,anchor,ports),'endmodule\n',monitor+'endmodule\n')
    need(normal.once(normal.once(after,monitor,''),ports,anchor)==before and
         not any(word in after for word in ('always_ff','always_comb','always @','initial begin')),
         'STATELESS_OBSERVER_REVERSE')
    files[observer]=after.encode()
    text=files[pilot.CPP].decode()
    pre='  d.clk=0;d.eval();const bool accepted_command=d.command_accept;'
    post='  need(!d.error,"R84_ACTUAL_C2_ERROR age="+std::to_string(age));'
    modified=normal.once(text,pre,'  d.clk=0;d.eval();queued_inject(d);const bool accepted_command=d.command_accept;')
    modified=normal.once(modified,post,'  queued_observe(d);\n'+post)
    need(normal.once(normal.once(modified,'  queued_observe(d);\n'+post,post),
         '  d.clk=0;d.eval();queued_inject(d);const bool accepted_command=d.command_accept;',pre)==text,
         'DRIVER_HOOK_REVERSE_ONLY')
    files[DRIVER]=modified.encode();files[CPP]=(ROOT/CPP).read_bytes()
    normal.runtime_before_model(files[CPP].decode())
    root=m['build']['top'];prefix=root+'__DOT__candidate__DOT__engine__DOT__'
    files[HEADER]=('#pragma once\n#include "V'+root+'___024root.h"\n'
       '#define QUEUED_INDEX d.rootp->'+prefix+'feedback_index_q\n'
       '#define QUEUED_GENERATION d.rootp->'+prefix+'feedback_command_generation_q\n').encode()
    need(b'#include "r12_queue_probe_config.h"' in files[CPP] and
         b'#include "stream27_feedback12_queue_driver.cpp"' in files[CPP],'GENERATED_INCLUDE_CLOSURE')
    files[SELF]=(ROOT/SELF).read_bytes();m['build']['cpp_source']=CPP
    m['steps']=([dict(name='r12-queued-index-generation-fault-recovery',argv=['{exe}','--faults'],
        expected_returncode=0,expected_stdout=FFOOTER,expected_stderr=''),
        dict(name='r12-queue-wrong-reference-sensitivity',argv=['{exe}','--wrong-reference'],
        expected_returncode=1,expected_stdout='',expected_stderr='R84_FULL_SIGNED96_REFERENCE ctx=0 address=0\n')]
        if faults else [dict(name='r12-queued-descriptor-normal',argv=['{exe}'],expected_returncode=0,
                             expected_stdout=NFOOTER,expected_stderr='')])
    m['sources']={name:sha(raw) for name,raw in files.items()}
    snapshot={name:pin for name,pin in m['sources'].items() if name.endswith('.sv')}
    m['rtl_readiness'].update(candidate_id=FAULTS if faults else NORMAL,source_snapshot=snapshot,
        candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()))
    m['test_role']='deliberate_fault' if faults else 'normal'
    m['r12_queued_guard']=dict(production58_unchanged=True,stateless_observer_only=True,
        driver_hooks_reversible=True,feed_mode_count100=True,actual_queued_row0_before_accept=True,
        forced_only='one feedback_index_q or feedback_command_generation_q bit; payload/owner/error not forced',
        pre_accept_queued_bad_and_zero_raw_operation_accept=True,
        expected_warm_local_error_and_host_public_fence_same_clock=True,
        reset_full_reference_recovery_words=524288,quiet_edges=16,
        raw_occupied_tails_allowed=True,host_GL_assumed_unimplemented=True,
        arbitrary_fault_or_RAM_config_protection_claim=False,promotion_allowed=False)
    return m,files


def prepare(output,faults=False):
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    out=Path(output).resolve();need(out.is_relative_to(BASE) and not out.exists() and
        not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'FRESH_UNPAUSED')
    m,files=role(faults);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    m['source_root']=str(source);dump(out/'manifest.json',m)
    dump(out/'host-hours.json',candidate_ladder.budget_from_hourly());variants=[]
    identifier=FAULTS if faults else NORMAL
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker=identifier.removesuffix('-q1-v1')+'-'+pair+'-v1';packet=out/('packet-'+pair)
        result=package.prepare(out/'manifest.json',source,profile,worker,'run',packet,out/'host-hours.json')
        ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
            worker_id=worker,profile=profile,native_root=ticket['native_root'],runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes())) for p in
                                 ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    ticket=dict(schema='gfn16-global-ticket-v1',id=identifier,owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',allowed_hosts=['gfn16-pilot-c4d','aethia'],
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
        minimum_ram_rationale='Bounded exploratory same58 scalar100 fixture/stateless observation; desiredGCP8 preserved, OOM/timeout retained.',
        est_minutes=35,promotion_bound=False,test_role=m['test_role'],rtl_readiness=m['rtl_readiness'],packages=variants,
        after=[NORMAL if faults else 's4-p16-c2-combo-r12-own100-serial-q1-v1'],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',ticket)
    return dict(id=identifier,ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_NATIVE')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--faults',action='store_true');a=p.parse_args()
    print(json.dumps(prepare(a.output,a.faults),indent=2))

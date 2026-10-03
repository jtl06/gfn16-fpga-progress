"""Own R11 LEAN reset/real watchdog-quarantine and full-image recovery.

The stateless observer exposes occupied/start control, never assumes zero
numeric payload. One simulation-only watchdog-age expiry is not a real stall,
an arbitrary fault-coverage claim, or protected host GL/rollback qualification.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))
SELF='reference/stream27_context_storage_combo_transport11_control.py'
CPP='rtl/tb/stream27_context_transport11_control.cpp'
HEADER='rtl/tb/r11_transport_control_config.h'
BASE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-transport11-control-v1/full-control-v2'
DONOR=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-transport11-native-v1/full-normal-v2'
MANIFEST_PIN='36841d192d274066d76f36930ccb9e537fbf86285e0c432367d6e235963bf9e3'
BUNDLE_PIN='5c795a3efe314d7b77b3508de56b5f0870708ed3ef145a23198ee9a477f5382e'
ID='s4-p16-c2-combo-r11-full-control-q1-v2'
NORMAL='s4-p16-c2-combo-r11-full-normal-q1-v1'
FOOTER='R11_TRANSPORT_CONTROL_PASS reset_events=3 watchdog_expiry=1 quiet_edges=32 recovered_reads=1048576 signed96=1 own_reference=1 payload_zero_assumed=0 host_gl_assumed=1 simulation_only=1\n'


def need(ok,why):
    if not ok:raise ValueError('R11_CONTROL_'+why)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def dump(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def role():
    from fpga.reference import stream27_context_storage_combo_transport11_native as normal
    raw=(DONOR/'manifest.json').read_bytes();br=(DONOR/'production-bundle.json').read_bytes()
    need(sha(raw)==MANIFEST_PIN and sha(br)==BUNDLE_PIN,'OWN_FROZEN_CAPTURE')
    m=json.loads(raw);production=json.loads(br)
    files={name:(DONOR/'source/fpga'/name).read_bytes() for name in m['sources']}
    need(all(sha(files[name])==pin for name,pin in m['sources'].items()),'ALL_SOURCE_PINS')
    need(len(production['files'])==58 and len(m['build']['sv_sources'])==59 and
         m['build']['parameters']==dict(production['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),
         'OWN_PRODUCTION_PARAMETERS')
    top=m['build']['top'];observer='rtl/'+top+'.sv';before=files[observer].decode()
    anchor=' output logic [15:0] dbg_generation\n);'
    ports=' output logic [15:0] dbg_generation,\n output logic [6:0] probe_slots,probe_starts,\n output logic probe_stop,probe_progress,probe_sent,probe_pending\n);'
    slots=[];starts=[]
    for f in range(3):
        field='candidate.engine.arithmetic.field'+str(f)
        slots.extend([field+'.pair_slot_q',field+'.inverse_slot_q'])
        starts.extend([field+'.pair_start_q',field+'.inverse_start_q'])
    slots.append('candidate.engine.arithmetic.crt_transport_slot')
    starts.append('candidate.engine.arithmetic.crt_transport_start')
    monitor=' assign probe_slots={'+','.join(reversed(slots))+'};\n'
    monitor+=' assign probe_starts={'+','.join(reversed(starts))+'};\n'
    for probe,actual in (('stop','safety_error'),('progress','lean_progress'),
                         ('sent','second_correction_sent'),('pending','second_correction_pending')):
        monitor+=' assign probe_'+probe+'=candidate.'+actual+';\n'
    text=normal.once(before,anchor,ports)
    text=normal.once(text,'endmodule\n',monitor+'endmodule\n')
    need(normal.once(normal.once(text,monitor,''),ports,anchor)==before,'EXACT_OBSERVER_REVERSE')
    need(not any(word in text for word in ('always_ff','always_comb','always @','initial begin')),
         'STATELESS_OBSERVER')
    files[observer]=text.encode()
    files[HEADER]=('#pragma once\n#include "V'+top+'___024root.h"\n'
        '#define WATCHDOG_AGE d.rootp->'+top+'__DOT__candidate__DOT__lean_watchdog_age\n').encode()
    files[CPP]=(ROOT/CPP).read_bytes();normal.runtime_before_model(files[CPP].decode())
    files[SELF]=(ROOT/SELF).read_bytes();m['build']['cpp_source']=CPP
    m['steps']=[dict(name='r11-full-transport-reset-watchdog-recovery',argv=['{exe}'],expected_returncode=0,
        expected_stdout=FOOTER,expected_stderr=''),
        dict(name='r11-full-transport-wrong-reference',argv=['{exe}','--wrong-reference'],expected_returncode=1,
        expected_stdout='',expected_stderr='R84_FULL_SIGNED96_REFERENCE ctx=0 address=0\n')]
    need(all(files['rtl/'+name]==body.encode() for name,body in production['files'].items()),
         'ALL58_PRODUCTION_BYTES_LITERAL')
    m['sources']={name:sha(body) for name,body in files.items()}
    snapshot={name:pin for name,pin in m['sources'].items() if name.endswith('.sv')}
    m['rtl_readiness'].update(candidate_id=ID,source_snapshot=snapshot,
        candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()))
    m['test_role']='deliberate_fault'
    m['transport11_control']=dict(actual_normal_dependency=NORMAL,production58_unchanged=True,
        observer_only_delta=observer,reset_actual_occupied_term_join_inverse_crt=True,
        numeric_payload_zero_not_assumed=True,watchdog_age_accelerated_only=True,
        watchdog_error_owner_payload_valid_not_forced=True,quiet_edges=32,
        full_recovery_signed96_words=1048576,full_count2_reset_does_not_epoch_wrap=True,
        public_busy_done_ready_read_admission_kill=True,private_phase_clear_not_claimed=True,
        no_public_cancel_port=True,host_GL_assumed_unimplemented=True,
        protected_fault_rollback_claim=False,promotion_allowed=False)
    return m,files


def prepare():
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    need(not BASE.exists() and not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),
         'FRESH_UNPAUSED')
    m,files=role();source=BASE/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    m['source_root']=str(source);dump(BASE/'manifest.json',m)
    dump(BASE/'host-hours.json',candidate_ladder.budget_from_hourly());variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-p16-c2-combo-r11-control-'+pair+'-v1'
        packet=BASE/('packet-'+pair)
        r=package.prepare(BASE/'manifest.json',source,profile,worker,'run',packet,BASE/'host-hours.json')
        ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],
            ticket_sha256=r['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
            worker_id=worker,profile=profile,native_root=ticket['native_root'],runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes())) for p in
                                 ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    ticket=dict(schema='gfn16-global-ticket-v1',id=ID,owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',allowed_hosts=['gfn16-pilot-c4d','aethia'],
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
        minimum_ram_rationale='Bounded4GiB exploratory fullcontrol: production58 unchanged/statelessobserver. Resource failures retained, no automatic retry or measured-control sufficiency.',
        est_minutes=35,promotion_bound=False,test_role='deliberate_fault',rtl_readiness=m['rtl_readiness'],
        packages=variants,after=[NORMAL],on='PASS_expected_contracts')
    dump(BASE/'global-ticket.json',ticket)
    return dict(id=ID,ticket=str(BASE/'global-ticket.json'),status='PREPARED_NOT_NATIVE')


if __name__=='__main__':print(json.dumps(prepare(),indent=2))

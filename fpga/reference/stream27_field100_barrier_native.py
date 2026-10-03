"""Isolated AUTHOR-owned protected FIELD100 raw-origin/publication fence fixture.

N256 only. Frozen58 production definitions remain byte-identical and retained.
Private diagnostic clones OR faults into raw predicates; no barrier/FF forces.
Normal and fault are separate roles. Each packet uses one executable for all
its steps; cross-ticket reuse is not qualified by the existing short runner.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
SELF = 'reference/stream27_field100_barrier_native.py'
SV = 'rtl/tb/stream27_field100_barrier_probe.sv'
CPP = 'rtl/tb/stream27_field100_barrier_probe.cpp'
DONOR = ROOT/'results/throughput-20260929/trackS-c2-protected-field100-native-v1/aw8-normal'
BASE = ROOT/'results/throughput-20260929/trackS-field100-barrier-native-v1'
MANIFEST_PIN = 'a396059b51146bb5daffd13cd4f5403f146805293651fa81f41510dcaa1970e0'
BUNDLE_PIN = 'dd8d9196a5ac79381b8e701d021d19a067dde4d319b15799b13f8d8f61441a00'
BINDER_PIN = '84b14c2ce04d37aec04d7eadb42eec04a9e34c0d1412ed927b8e1a0f60757ebd'
TOP = 'genefer_stream27_field100_barrier_probe_v1'
IDS = {mode: 's4-p16-c2-field100-barrier-'+mode+'-q1-v1' for mode in ('normal', 'faults')}
NORMAL_FOOTER = 'FIELD100_BARRIER_NORMAL_PASS production58=1 proposals=2 drains=2 signed96_reads=1024 full56=1 copy_n_plus4=1 runtime_before_dut=1\n'
FAULT_FOOTER = 'FIELD100_BARRIER_FAULT_PASS origins=4 proposal=4 drain=4 host_read_peer=4 admission=4 accepted_newjob=4 reset=4 recovered_signed96_reads=24576 field_report_lag1=15 arithmetic_report_lag2=15 host_report_lag1=20 stop_requalification_loss=0 quiet_edges=480 private_pulses_allowed=1\n'


def need(ok, label):
    if not ok:
        raise ValueError('FIELD100_BARRIER_'+label)


def sha(raw):
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def once(text, before, after):
    need(text.count(before)==1, 'ANCHOR:'+before[:70])
    return text.replace(before, after, 1)


def diagnostic(text, name, operations):
    """Every native-only clone has a mechanical byte-exact reversal."""
    original=text
    new=name+'_barrier_diag_v1'
    changes=[('module '+name+' #', 'module '+new+' #')]+operations
    for before, after in changes:
        text=once(text, before, after)
    reversed_text=text
    for before, after in reversed(changes):
        reversed_text=once(reversed_text, after, before)
    need(reversed_text==original, 'DIAGNOSTIC_LITERAL_REVERSE')
    return new, text, dict(parent=name, diagnostic=new, parent_sha256=sha(original),
                          diagnostic_sha256=sha(text), literal_reverse=True, changes=changes)


def port_connections(head):
    ports=head.split(') (',1)[1]
    names=[re.search(r'(\w+)\s*$', item.strip()).group(1) for item in ports.split(',')]
    need(len(names)==len(set(names)) and names[0]=='clk' and names[-1]=='final_image_rows', 'PORT_ABI')
    return names


def build_probe(production):
    files={name:text.encode() for name,text in production['files'].items()}
    original=dict(files)
    records=[]
    fields=[next(n[:-3] for n in files if n.startswith('genefer_stream27_shared_warm_aw8_p16_f'+str(f)))
            for f in range(3)]
    field_new=[]
    for name in fields:
        new,text,record=diagnostic(files[name+'.sv'].decode(),name,[
            (' input logic clk,rst_n,',' input logic diag_raw_fault,\n input logic clk,rst_n,'),
            (' end\n logic [LANES-1:0] digit_valid,digit_error,boundary_valid,boundary_error;',
             '  if(diag_raw_fault)admission_bad=1;\n end\n logic [LANES-1:0] digit_valid,digit_error,boundary_valid,boundary_error;')])
        files[new+'.sv']=text.encode();field_new.append(new);records.append(record)
    arith=next(n[:-3] for n in files if n.startswith('genefer_stream27_threefield_carry_aw8'))
    changes=[(' input logic clk,rst_n,',' input logic [3:0] diag_fault,\n input logic clk,rst_n,'),
             ('wire local_fault_now=setup_error || (|lane_error) || join_bad || carry_bad || admission_bad;',
              'wire local_fault_now=setup_error || (|lane_error) || join_bad || carry_bad || admission_bad || diag_fault[3];')]
    for f,(old,new) in enumerate(zip(fields,field_new)):
        changes.append((old+' #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) field'+str(f)+' (',
                        new+' #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) field'+str(f)+' (\n  .diag_raw_fault(diag_fault['+str(f)+']),'))
    new_arith,text,record=diagnostic(files[arith+'.sv'].decode(),arith,changes)
    files[new_arith+'.sv']=text.encode();records.append(record)
    warm=next(n[:-3] for n in files if n.startswith('genefer_stream27_warm_contexts_aw8'))
    new_warm,text,record=diagnostic(files[warm+'.sv'].decode(),warm,[
        (' input logic clk,rst_n,',' input logic [3:0] diag_fault,\n input logic clk,rst_n,'),
        (arith+' #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) arithmetic (',
         new_arith+' #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) arithmetic (\n  .diag_fault,')])
    files[new_warm+'.sv']=text.encode();records.append(record)
    host=production['top']
    new_host,text,record=diagnostic(files[host+'.sv'].decode(),host,[
        (' input logic clk,rst_n,',' input logic [3:0] diag_fault,input logic diag_missing_mask,\n input logic clk,rst_n,'),
        (warm+' #(.AW(AW),.P(P),.CONTEXTS(2)) engine (',
         new_warm+' #(.AW(AW),.P(P),.CONTEXTS(2)) engine (\n  .diag_fault,'),
        ('assign canonical_ready=published & {2{!safety_error}};assign done=done_q & {2{!safety_error}};',
         'assign canonical_ready=published & {2{!(safety_error && !diag_missing_mask)}};assign done=done_q & {2{!(safety_error && !diag_missing_mask)}};')])
    files[new_host+'.sv']=text.encode();records.append(record)
    head=production['files'][host+'.sv'].split(');\n',1)[0]
    ports=port_connections(head)
    head=once(head,'module '+host+' #','module '+TOP+' #')
    head+=',\n input logic [3:0] diag_fault,input logic diag_missing_mask,\n'
    head+=' output logic probe_barrier,probe_child_barrier,probe_local_q,probe_proposal,probe_pending,probe_owned,probe_newjob,\n'
    head+=' output logic [2:0] probe_field_q,probe_field_report,probe_field_stop,output logic [5:0] probe_field_copies,output logic probe_arith_report,output logic [1:0] probe_private_ready,probe_private_done,\n'
    head+=' output logic [55:0] probe_publish_owner,probe_live_owner,\n'
    head+=' output logic probe_publish_context,probe_canonical_owner,output logic [3*(AW+1)-1:0] probe_counts,\n'
    head+=' output logic [7:0] probe_host_controls,output logic [3:0] probe_arith_controls,\n'
    head+=' output logic [31:0] probe_proposals,probe_drains);'
    # Epoch seeds are build parameters, not entries in the production flag map.
    # The shell must forward them instead of silently using child defaults0.
    params=dict(production['parameters'],EPOCH_SEED0=0,EPOCH_SEED1=0)
    call=new_host+' #(\n '+',\n '.join('.'+p+'('+p+')' for p in params)+') candidate (\n '
    call+=',\n '.join('.'+p for p in ports+['diag_fault','diag_missing_mask'])+');'
    template=(ROOT/SV).read_text()
    need(template.count('@HEADER@')==template.count('@CANDIDATE@')==1,'PROBE_TEMPLATE')
    files['tb/'+Path(SV).name]=template.replace('@HEADER@',head).replace('@CANDIDATE@',call).encode()
    need(all(files[name]==raw for name,raw in original.items()) and len(records)==6 and len(files)==65,
         'PRODUCTION58_VERBATIM_AND_SIX_DIAGNOSTIC_CLONES')
    return files,records


def role(mode):
    need(mode in IDS,'MODE')
    raw=(DONOR/'manifest.json').read_bytes();bundle_raw=(DONOR/'production-bundle.json').read_bytes()
    need(sha(raw)==MANIFEST_PIN and sha(bundle_raw)==BUNDLE_PIN,'FROZEN_DONOR')
    manifest=json.loads(raw);production=json.loads(bundle_raw)
    need(len(production['files'])==58 and production['parameters']['ERROR_AGGREGATION_REGISTERED']==1 and\
         production['parameters']['FIELD_PROTOCOL_ORIGIN_FAST']==1 and 'LEAN_PRODUCTION' not in production['parameters'],
         'PROTECTED_FIELD100_ONLY')
    need(production['source_sha256']['reference/stream27_protected_field100_bind.py']==BINDER_PIN,
         'EXACT_FIELD100_BINDER')
    files={n:(DONOR/'source/fpga'/n).read_bytes() for n in manifest['sources']}
    need(all(sha(files[n])==pin for n,pin in manifest['sources'].items()),'DONOR_CAPTURE_BYTES')
    sv,records=build_probe(production)
    for name,body in sv.items():
        files['rtl/'+name]=body
    header='rtl/tb/s4_host_contexts_config_v1.h'
    text=files[header].decode();need(text.count(production['top'])==2,'NORMAL_TOP_ALIAS')
    files[header]=text.replace(production['top'],TOP).encode()
    files[CPP]=(ROOT/CPP).read_bytes()
    files[SELF]=(ROOT/SELF).read_bytes()
    files['lineage/'+SV]=(ROOT/SV).read_bytes()
    files['lineage/production-bundle.json']=bundle_raw
    manifest['build']['top']=TOP
    manifest['build']['cpp_source']=CPP
    manifest['build']['sv_sources']=['rtl/'+name for name in sv]
    # The first normal runs the existing actual two-chain numerical reference.
    if mode=='normal':
        manifest['steps']=[dict(name='field100-barrier-own-normal',argv=['{exe}','--normal'],expected_returncode=0,
            expected_stdout=manifest['steps'][0]['expected_stdout']+NORMAL_FOOTER,expected_stderr='')]
    else:
        manifest['steps']=[dict(name='field100-barrier-raw-origins',argv=['{exe}','--faults'],expected_returncode=0,
                              expected_stdout=FAULT_FOOTER,expected_stderr=''),
                           dict(name='field100-barrier-missing-mask-negative',argv=['{exe}','--missing-mask-negative'],
                                expected_returncode=1,expected_stdout='',expected_stderr='FIELD100_BARRIER_EXTERNAL_MASK\n')]
    manifest['test_role']='normal' if mode=='normal' else 'deliberate_fault'
    manifest['source_root']=manifest['output_parent']='UNBOUND'
    manifest['sources']={n:sha(body) for n,body in files.items()}
    snapshot={n:p for n,p in manifest['sources'].items() if n.endswith('.sv')}
    manifest['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='field100-barrier-native-only',
        source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':'))),
        rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))
    manifest['field100_barrier_fixture']=dict(author='p16_independent_reviewer',independent_review=False,
        donor_manifest_sha256=MANIFEST_PIN,production_bundle_sha256=BUNDLE_PIN,production58_unchanged=True,
        diagnostic_clones=records,registered_sources=['field0.epoch_protocol.out_error','field1.epoch_protocol.out_error',
            'field2.epoch_protocol.out_error','arithmetic.local_fault_q'],raw_OR_only=True,no_barrier_or_FF_force=True,
        protected_production_only=True,external_masks_tested=True,private_published_done_may_pulse=True,
        native_only_missing_FAST_mask_mutant=True,field_FAST_origin_lag=0,field_report_lag=1,
        arithmetic_report_lag=2,host_report_lag=1,report_never_rechecks_STOP=True,
        private_quarantine_numeric_tails_allowed=True,arbitrary_corruption_claim=False,clock_claim=False,promotion_allowed=False)
    return manifest,files


def dump(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2);stream.write('\n')


def prepare(mode):
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    out=BASE/(mode+'-v1')
    need(not out.exists() and not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'FRESH_UNPAUSED')
    manifest,files=role(mode)
    source=out/'source/fpga';source.mkdir(parents=True)
    for name,body in files.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(body)
    manifest['source_root']=str(source.resolve())
    dump(out/'manifest.json',manifest);dump(out/'host-hours.json',candidate_ladder.budget_from_hourly())
    variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-p16-c2-field100-barrier-'+mode+'-'+pair+'-v1'
        packet=out/('packet-'+pair)
        result=package.prepare(out/'manifest.json',source,profile,worker,'run',packet,out/'host-hours.json')
        ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
            worker_id=worker,profile=profile,native_root=ticket['native_root'],runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes()))
                for p in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    logical=dict(schema='gfn16-global-ticket-v1',id=IDS[mode],owner='p16-independent-reviewer-fixture-author',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',allowed_hosts=['gfn16-pilot-c4d','aethia'],
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
        minimum_ram_rationale='Bounded N256 fixture, desiredGCP8/minimum4; not measured resource sufficiency, retain failures.',
        est_minutes=15,promotion_bound=False,test_role=manifest['test_role'],rtl_readiness=manifest['rtl_readiness'],packages=variants)
    if mode=='faults':logical.update(after=[IDS['normal']],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',logical)
    return dict(id=IDS[mode],ticket=str(out/'global-ticket.json'),production_sv=58,compiled_sv=65,
                status='PREPARED_NOT_NATIVE',authorship='fixture author; not independent promotion reviewer')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=tuple(IDS),required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.mode),indent=2))

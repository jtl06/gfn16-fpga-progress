"""R95 replica-only C2 normal-first packaging; source writer remains stream_core.

Only graph/identifier replacement from frozen ORIGINAL storage2 normal donors.
No timing58 calendar/qualification, full-N numeric work, HDL or launcher here.
"""
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))
SELF='reference/stream27_context_storage_combo_quarantine_native.py'
BINDER='reference/stream27_context_storage_combo_quarantine_bind.py'
BINDER_PIN='a45413816ed3cccb112a0e0ec6947c20c22e3314e30e6eaed8be260f5ac25a28'
READY='2026-10-02T10:38:21Z'
BASE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-boundary-native-v1'
DONORS={'aw8':('aw8-normal','de4e736a67620a23809d28297fd9cb1ef0a5bf57997d17090b4e077296e46be1'),
        'full':('full-normal','15df847daa4f3857347b7208cff7328bda79e9b0f217670fd395c7b09b88f7b7')}
IDS={stage:'s4-p16-c2-combo-r3-'+stage+'-normal-q1-v1' for stage in DONORS}


def need(ok,why):
    if not ok:raise ValueError('C2_COMBO_NATIVE_'+why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def dump(path,value):
    with Path(path).open('x') as out:json.dump(value,out,indent=2);out.write('\n')


def capture(stage):
    need(stage in DONORS,'AW8_FULL_ONLY_NO_AW5')
    name,pin=DONORS[stage];directory=BASE/name;raw=(directory/'manifest.json').read_bytes()
    need(sha(raw)==pin,'IMMUTABLE_ORIGINAL_STORAGE2_DONOR')
    manifest=json.loads(raw);files={}
    for name,digest in manifest['sources'].items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts,'SOURCE_PATH')
        data=(directory/'source/fpga'/name).read_bytes();need(sha(data)==digest,'SOURCE_PIN:'+name);files[name]=data
    return manifest,files


def role(stage):
    from fpga.reference import stream27_context_storage_combo_quarantine_bind as core
    need(sha((ROOT/BINDER).read_bytes())==BINDER_PIN,'EXACT_CORE_FREEZE')
    manifest,files=capture(stage);before=copy.deepcopy(manifest);meta=before['context_storage_combo_boundary']
    production=core.prepare(256 if stage=='aw8' else 65536,enabled=1)
    need(production['geometry']==meta['geometry'] and production['parameters']==dict({
        k:v for k,v in before['build']['parameters'].items() if k not in ('EPOCH_SEED0','EPOCH_SEED1')},QUARANTINE_REPLICAS=1),'ONLY_REPLICA_PARAMETER_DELTA')
    need(len(production['files'])==55 and production['context_storage_combo']['roster']==[
        'storage2','packed_delays','root_weight_retime','term_payload_lookahead'],'EXACT_COMPOSITION53')
    need(production['context_storage_combo_quarantine']['same_origin_edge'] and
         production['context_storage_combo_quarantine']['commit_publication_barriers_unchanged'],'QUALIFIED_AUTHORITY')
    oldtop,newtop=meta['production_top'],production['top'];original_cpp=files[before['build']['cpp_source']]
    for name in meta['production_generated_sha256']:files.pop('rtl/'+name)
    files.update({'rtl/'+name:text.encode() for name,text in production['files'].items()})
    sv=['rtl/'+name for name in production['rtl_sources']]
    if stage=='aw8':
        header='rtl/tb/s4_host_contexts_config_v1.h';text=files[header].decode()
        need(text.count(oldtop)==2 and text.count('INTERVAL=213,FIRST_DIGIT=194,CARRY_DONE=213')==1,'AW8_HEADER_IDENTIFIER_CALENDAR')
        files[header]=text.replace(oldtop,newtop).encode()
        manifest['build']['top']=newtop
    else:
        observer=manifest['build']['top'];text=files['rtl/'+observer+'.sv'].decode()
        text,count=re.subn(r'\b'+re.escape(oldtop)+r'\b',newtop,text)
        need(count==1 and not re.search(r'\b(always|always_ff|always_comb|initial)\b',text),'STATELESS_OBSERVER')
        need(text.count('COMM_STAGE_SHARED_MLAB=1,')==1 and text.count('.CONTEXTS(CONTEXTS),')==1,'OBSERVER_PARAMETER_SEAM')
        text=text.replace('COMM_STAGE_SHARED_MLAB=1,','COMM_STAGE_SHARED_MLAB=1,QUARANTINE_REPLICAS=1,',1)
        text=text.replace('.CONTEXTS(CONTEXTS),','.CONTEXTS(CONTEXTS),\n  .QUARANTINE_REPLICAS(QUARANTINE_REPLICAS),',1)
        files['rtl/'+observer+'.sv']=text.encode();sv+=['rtl/'+observer+'.sv']
    manifest['build']['sv_sources']=sv
    manifest['build']['parameters']['QUARANTINE_REPLICAS']=1
    for name,digest in production['source_sha256'].items():
        data=(ROOT/name).read_bytes();need(sha(data)==digest,'CORE_DEPENDENCY:'+name);files['lineage/'+name]=data
    files['lineage/'+SELF]=(ROOT/SELF).read_bytes()
    manifest['sources']={name:sha(data) for name,data in files.items()}
    snapshot={name:pin for name,pin in manifest['sources'].items() if name.endswith('.sv')}
    manifest.update(source_root='UNBOUND',output_parent='UNBOUND',test_role='normal',
        rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=IDS[stage].removesuffix('-q1-v1'),
            source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),rtl_ready_at_utc=READY))
    manifest['context_storage_combo_boundary'].update(production_top=newtop,production_generated_sha256=production['generated_sha256'],geometry=production['geometry'])
    if stage=='aw8':
        manifest['r84_explicit_small'].update(generated_sha256=production['generated_sha256'])
        manifest['host_contexts'].update(generated_sha256=production['generated_sha256'])
    else:
        manifest['r84']['production_generated_sha256']=production['generated_sha256']
        manifest['r84']['native_observer'].update(production_top=newtop,production_root_sha256=production['generated_sha256'][newtop+'.sv'])
    manifest['context_storage_combo_quarantine']=dict(contract=production['context_storage_combo_quarantine'],production_top=newtop,
        production_generated_sha256=production['generated_sha256'],source_sha256=production['source_sha256'],
        geometry=production['geometry'],donor_manifest_sha256=DONORS[stage][1],source_freeze_utc=READY,
        unchanged_cpp_reference_probe_steps=True,donor_PASS_clock_pilot_not_inherited=True,full_N_numeric_locally_performed=False,promotion_allowed=False)
    need(manifest['steps']==before['steps'] and manifest['probe']==before['probe'] and
         manifest['build']['parameters']==dict(before['build']['parameters'],QUARANTINE_REPLICAS=1) and files[before['build']['cpp_source']]==original_cpp,'UNCHANGED_ORACLE_CONTRACT')
    from fpga.tools.native_source_gate_v1 import expand
    for step in [manifest['probe']]+manifest['steps']:expand(step['argv'],Path('/exe'),Path('/root'))
    return manifest,files,production


def prepare(output,stage):
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    out=Path(output).resolve();need(out.is_relative_to(ROOT) and not out.exists(),'FRESH_OUTPUT')
    need(not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'PAUSE')
    manifest,files,production=role(stage);source=out/'source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(data)
    manifest['source_root']=str(source);dump(out/'manifest.json',manifest);dump(out/'production-bundle.json',production)
    dump(out/'host-hours.json',candidate_ladder.budget_from_hourly());variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-p16-c2-combo-r3-'+stage+'-'+pair+'-v1';packet=out/('packet-'+pair)
        result=package.prepare(out/'manifest.json',source,profile,worker,'run',packet,out/'host-hours.json');ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],ticket_sha256=result['ticket_sha256'],
            manifest_sha256=sha((packet/'manifest.json').read_bytes()),worker_id=worker,profile=profile,native_root=ticket['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes())) for p in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    logical=dict(schema='gfn16-global-ticket-v1',id=IDS[stage],owner='merged-ntt-model',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4 if stage=='aw8' else 8,
        minimum_ram_rationale='AW8 bounded exploratory4GiB cap only; no measured composed peak inherited.' if stage=='aw8' else 'Own fullN8GiB source-exact normal; no old pilot/clock/runtime inheritance.',
        allowed_hosts=['gfn16-pilot-c4d','aethia'],est_minutes=25,promotion_bound=False,test_role='normal',rtl_readiness=manifest['rtl_readiness'],packages=variants)
    if stage=='full':logical.update(after=[IDS['aw8']],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',logical);return dict(id=logical['id'],ticket=str(out/'global-ticket.json'),compiled_rtl=len(manifest['build']['sv_sources']),status='PREPARED_NOT_NATIVE')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--stage',choices=('aw8','full'),required=True)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.stage),indent=2))


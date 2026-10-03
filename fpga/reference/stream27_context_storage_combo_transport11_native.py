"""R11 LEAN own normal-first native packaging; no ancestor results inherited."""
import argparse
from datetime import datetime, timezone
import importlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha, need, dump, once, runtime_before_model

SELF = 'reference/stream27_context_storage_combo_transport11_native.py'
BINDER = 'reference/stream27_context_storage_combo_transport11_source_v2.py'
BINDER_PIN = '792851152b0a637a83885a72fb33a972601547470ae377723228411a188c2262'
READY = '2026-10-02T19:30:30Z'
BASE = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-timing10-native-v1'
DONORS = {
    'aw8': ('63d58f4645eb55931c35aa4b72f034732eecced860125593036c76df7c70abd7',
            'f1c9f7cccd8303afd0c0ccdeca81aea7f8ccdfac1dbb04aa5b497774448f66cf'),
    'full': ('587e6357694733f071bad9a991b278bee1874965f10578315569f18f0848155a',
             'bbddffeb640ae8fde76a3c469f442552d8f4581128f33011cc21e2122fd4d962'),
}
IDS = {stage: 's4-p16-c2-combo-r11-' + stage + '-normal-q1-v1' for stage in DONORS}


def capture(stage):
    need(stage in DONORS, 'R11_AW8_FULL_ONLY')
    directory = BASE / (stage + '-normal')
    mr, br = (directory / 'manifest.json').read_bytes(), (directory / 'production-bundle.json').read_bytes()
    need((sha(mr), sha(br)) == DONORS[stage], 'R11_EXACT_DONOR_BYTES')
    manifest, bundle = json.loads(mr), json.loads(br)
    files = {}
    for name, pin in manifest['sources'].items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'R11_SOURCE_PATH')
        raw = (directory / 'source/fpga' / name).read_bytes()
        need(sha(raw) == pin, 'R11_SOURCE_CLOSURE:' + name)
        files[name] = raw
    need(len(bundle['files']) == 58 and all(files['rtl/'+n] == t.encode() for n,t in bundle['files'].items()),
         'R11_PRODUCTION_DONOR')
    runtime_before_model(files[manifest['build']['cpp_source']].decode())
    return manifest, files, bundle


def config():
    return dict(aw=16, p=16, contexts=2, bases=[604832956,999999937], count=2,
                interval=8463, publication_fence_edges=1, lean_production=True)


def validate(stdout, stderr, rc, config, assets):
    expected = dict(aw=16,p=16,contexts=2,bases=[604832956,999999937],count=2,
                    interval=8463,publication_fence_edges=1,lean_production=True)
    need(config == expected and assets == {}, 'R11_CONFIG')
    need(rc == 0 and type(rc) is int and stderr == '' and stdout.startswith('R84_C2_FULL_PASS ') and
         stdout.endswith('\n') and '\n' not in stdout[:-1], 'R11_EXACT_NORMAL_OUTPUT')
    value = json.loads(stdout.removeprefix('R84_C2_FULL_PASS '))
    fixed = dict(aw=16,p=16,contexts=2,bases=[604832956,999999937],squares=8,reads=393216,
                 signed96=True,context_alone_bit_identical=True,independent_reference=True,
                 interval=8463,pair_launch_cycles=8463,peer_live_reads=65536,model_threads=1)
    variable = {'launches','single_cycles','joint_cycles','overlap_edges','done_edges','warm_edges',
                'setup_edges','single_first','seconds'}
    need(set(value) == set(fixed)|variable and all(value[k] == v and type(value[k]) is type(v) for k,v in fixed.items()),
         'R11_COUNTS_AND_KEYS')
    need(value['launches'] == [[204,8667],[4435,12898]] and value['warm_edges'] == [21229,25460] and
         value['setup_edges'] == [99,199] and value['single_first'] == [104,104], 'R11_WARM_CALENDAR')
    need(value['done_edges'] == [680694,1340158] and value['joint_cycles'] == 1405694 and
         value['single_cycles'] == [746130,746130] and value['overlap_edges'] == 680693, 'R11_PUBLICATION_FENCE')
    need(type(value['seconds']) in (int,float) and math.isfinite(value['seconds']) and 0<value['seconds']<3700,
         'R11_FINITE_TIME')
    return dict(status='PASS_expected_contracts', measurements=value, promotion_allowed=False,
                scope='OWN R11 LEAN functional/cycle evidence only; host GL assumed/unimplemented; no protected fault/rollback or clock inheritance.')


def role(stage):
    need(sha((ROOT/BINDER).read_bytes()) == BINDER_PIN, 'R11_PRODUCER_PIN')
    manifest, files, parent = capture(stage)
    core = importlib.import_module('fpga.'+BINDER.removesuffix('.py').replace('/','.'))
    production = core.prepare(parent['geometry']['n'],p=16,contexts=2,enabled=1,lean_production=1,
        crt_transport_reg=1,inverse_ingress_reg=1,term_join_transport_reg=1,lean_progress_watchdog=1)
    contract = production['context_transport11']
    need(len(production['files']) == 58 and contract['source_ready'] and contract['lean_production'] and
         contract['field_protocol_sink_added_edges'] == 2 and contract['crt_ingress_added_edges'] == 1 and
         contract['term_recurrence_edges'] == 4 and contract['lean_progress_watchdog'] and contract['publication_fence_edges_per_job'] == 1 and
         production['parameters']['LEAN_PRODUCTION'] == 1, 'R11_EXACT_LEAN_RECIPE')
    g = production['geometry']; oldtop,newtop = parent['top'],production['top']
    need((g['warm_interval'],g['first_digit'],g['carry_done']) ==
         ((217,198,217) if stage == 'aw8' else (8463,8462,12561)), 'R11_SOURCE_GEOMETRY')
    for name in parent['generated_sha256']: files.pop('rtl/'+name)
    files.update({'rtl/'+name:text.encode() for name,text in production['files'].items()})
    sv = ['rtl/'+name for name in production['rtl_sources']]
    extra = {k:v for k,v in production['parameters'].items() if k not in parent['parameters']}
    need(all(production['parameters'][k] == v for k,v in parent['parameters'].items()), 'R11_PARENT_PARAMETERS')
    if stage == 'aw8':
        header='rtl/tb/s4_host_contexts_config_v1.h'; text=files[header].decode()
        need(text.count(oldtop)==2,'R11_SMALL_IDENTIFIER')
        text=text.replace(oldtop,newtop)
        text=once(text,'INTERVAL=214,FIRST_DIGIT=195,CARRY_DONE=214','INTERVAL=217,FIRST_DIGIT=198,CARRY_DONE=217')
        text=once(text,'FIRST[2]={204,311}','FIRST[2]={204,312}')
        files[header]=text.encode();manifest['build']['top']=newtop
    else:
        observer=manifest['build']['top']; path='rtl/'+observer+'.sv'; text=files[path].decode()
        text,count=re.subn(r'\b'+re.escape(oldtop)+r'\b',newtop,text)
        need(count==1 and not re.search(r'\b(always|always_ff|always_comb|initial)\b',text),'R11_STATELESS_OBSERVER')
        for parameter,default in extra.items():
            text=once(text,'COMM_OWNER_COMPARE_LOCAL=1,','COMM_OWNER_COMPARE_LOCAL=1,'+parameter+'='+str(default)+',')
            text=once(text,'.COMM_OWNER_COMPARE_LOCAL(COMM_OWNER_COMPARE_LOCAL),',
                      '.COMM_OWNER_COMPARE_LOCAL(COMM_OWNER_COMPARE_LOCAL),\n  .'+parameter+'('+parameter+'),')
        files[path]=text.encode();sv.append(path)
        header='rtl/tb/s4_p16_two_context_full_config.h'
        files[header]=once(files[header].decode(),'INTERVAL=8460,FIRST_DIGIT=8459,CARRY_DONE=12558',
                           'INTERVAL=8463,FIRST_DIGIT=8462,CARRY_DONE=12561').encode()
        manifest['steps'][0].update(name='normal-full-c2-r11-lean-alone-and-joint',
            validator=dict(source=SELF,function='validate',config=config(),assets={}))
    runtime_before_model(files[manifest['build']['cpp_source']].decode())
    manifest['build']['sv_sources']=sv;manifest['build']['parameters'].update(extra)
    for name,pin in production['source_sha256'].items():
        raw=(ROOT/name).read_bytes();need(sha(raw)==pin,'R11_IMPORT:'+name);files['lineage/'+name]=raw
    files[SELF]=(ROOT/SELF).read_bytes()
    utility='reference/stream27_context_storage_combo_registerederror_native.py'
    files[utility]=(ROOT/utility).read_bytes()
    manifest['sources']={name:sha(raw) for name,raw in files.items()}
    snapshot={name:pin for name,pin in manifest['sources'].items() if name.endswith('.sv')}
    manifest.update(source_root='UNBOUND',output_parent='UNBOUND',test_role='normal',
        rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=IDS[stage].removesuffix('-q1-v1'),
            source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
            rtl_ready_at_utc=READY))
    for value in manifest.values():
        if isinstance(value,dict) and 'production_generated_sha256' in value:
            value.update(production_top=newtop,production_generated_sha256=production['generated_sha256'])
    if stage=='aw8':
        for key in ('r84_explicit_small','host_contexts'):manifest[key]['generated_sha256']=production['generated_sha256']
    else:
        manifest['r84']['native_observer'].update(production_top=newtop,
            production_root_sha256=production['generated_sha256'][newtop+'.sv'])
    manifest['context_transport11']=dict(contract=contract,production_top=newtop,
        production_generated_sha256=production['generated_sha256'],source_sha256=production['source_sha256'],geometry=g,
        source_freeze_utc=READY,donor_manifest_sha256=DONORS[stage][0],donor_results_not_inherited=True,
        runtime_context_explicitly_configured_before_every_model=True,lean_production=True,
        host_GL_assumed_unimplemented=True,protected_fault_rollback_claim=False,
        progress_watchdog_repaired_source_only_no_prior_PRP_inheritance=True,promotion_allowed=False)
    return manifest,files,production


def prepare(output,stage):
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    out=Path(output).resolve();need(out.is_relative_to(ROOT) and not out.exists(),'R11_FRESH_OUTPUT')
    need(not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'R11_PAUSE')
    manifest,files,production=role(stage);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
    manifest['source_root']=str(source);dump(out/'manifest.json',manifest)
    dump(out/'production-bundle.json',production);dump(out/'host-hours.json',candidate_ladder.budget_from_hourly())
    variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-p16-c2-combo-r11-'+stage+'-'+pair+'-v1';packet=out/('packet-'+pair)
        result=package.prepare(out/'manifest.json',source,profile,worker,'run',packet,out/'host-hours.json')
        nt=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],ticket_sha256=result['ticket_sha256'],
            manifest_sha256=sha((packet/'manifest.json').read_bytes()),worker_id=worker,profile=profile,native_root=nt['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes())) for p in
                                 ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    ticket=dict(schema='gfn16-global-ticket-v1',id=IDS[stage],owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',allowed_hosts=['gfn16-pilot-c4d','aethia'],
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
        minimum_ram_rationale='Bounded exploratory4GiB normal; desiredGCP8 preserved, no measured R10 RAM sufficiency; OOM/timeout retained.',
        est_minutes=25,promotion_bound=False,test_role='normal',rtl_readiness=manifest['rtl_readiness'],packages=variants)
    if stage=='full':ticket.update(after=[IDS['aw8']],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',ticket)
    return dict(id=IDS[stage],ticket=str(out/'global-ticket.json'),production_sv=len(production['files']),
                compiled_sv=len(manifest['build']['sv_sources']),status='PREPARED_NOT_NATIVE')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--stage',choices=('aw8','full'),required=True);args=parser.parse_args()
    print(json.dumps(prepare(args.output,args.stage),indent=2))

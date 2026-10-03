"""R8 full-geometry wrap gate: genuine C2 arithmetic, host timestamp seam only."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_context_storage_combo_directbound_full_wrap.py'
BASE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-directbound-wrap-v1/full-normal'
ID='s4-p16-c2-combo-r8-full-wrap-normal-q1-v1'
CPP='rtl/tb/stream27_c2_directbound_full_wrap.cpp'
ORIGINAL_VALIDATOR='reference/stream27_p16_two_context_full_native.py'
ORIGINAL_PIN='0f6d7b05c1016ef098df0f3138bc29fa150e9a9fc630b3c6cf45f5162f72e5c6'
FOOTER='R8_FULL_WRAP_PASS aliases=3 cold_accepts=2 cache_events_per_field=4 reads=393216 masks=1/2/3 independent_reference=1 real_datapath_edges=1 simulation_only=1\n'


def sha(raw):return hashlib.sha256(raw).hexdigest()
def need(ok,why):
    if not ok:raise ValueError('R8_FULL_WRAP_'+why)


def validate(stdout,stderr,rc,config,assets):
    need(config==dict(aw=16,p=16,contexts=2,bases=[604832956,999999937],count=2,interval=8459), 'CONFIG')
    need(set(assets)=={'frozen_normal_validator'} and
         sha(assets['frozen_normal_validator'].encode())==ORIGINAL_PIN,'EXACT_UNCHANGED_NORMAL_VALIDATOR')
    need(stdout.endswith(FOOTER) and len(stdout.splitlines())==2,'FULL_NORMAL_PLUS_WRAP_FOOTER')
    # Reuse the exact captured stdlib-only normal validator, not its generator
    # or any full-N arithmetic. All underlying numeric work was on the worker.
    namespace={'__name__':'r84_frozen_normal_validator','__file__':str(ROOT/ORIGINAL_VALIDATOR)}
    exec(compile(assets['frozen_normal_validator'],ORIGINAL_VALIDATOR,'exec'),namespace)
    result=namespace['validate'](stdout.removesuffix(FOOTER),stderr,rc,config,{})
    need(result['status']=='PASS_expected_contracts','UNCHANGED_FULL_NORMAL_CONTRACT')
    result.update(scope='Own R8 full geometry context-alone/joint plus accelerated host timestamp aliases. Actual independent reference/owners/publication preserved; not real billions of protocol clock edges.',
                  wrap=dict(aliases=3,external_cold_accepts=2,table_events_per_field=4,
                            protocol_time_forced=False,arithmetic_or_owner_forced=False))
    return result


def role():
    sys.path.insert(0,str(ROOT.parent))
    from fpga.reference import stream27_context_storage_combo_directbound_native as normal
    from fpga.reference import stream27_context_storage_combo_oneshot_wrap as wrap
    captured=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-directbound-native-v1/full-normal'
    raw=(captured/'manifest.json').read_bytes()
    need(sha(raw)=='1ac1110a421f0e2b71d2d0596109f4707098e1aa3b43e78053b83886c23ec0c1','OWN_R8_FULL_CAPTURE')
    m=json.loads(raw);files={name:(captured/'source/fpga'/name).read_bytes() for name in m['sources']}
    need(all(sha(files[name])==pin for name,pin in m['sources'].items()),'OWN_CAPTURE_SOURCE_PINS')
    bundle_raw=(captured/'production-bundle.json').read_bytes()
    need(sha(bundle_raw)=='ebf08fffea9751e8ae7c9c12fe09fd4801f52ff74c5f642a29b192f994e5b543','OWN_R8_BUNDLE')
    production=json.loads(bundle_raw)
    need(m['build']['parameters']==dict(production['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),'OWN_COMPILED_PARAMETERS')
    before=json.loads(json.dumps(m))
    observer='rtl/'+m['build']['top']+'.sv'
    original=files[observer].decode()
    ports=wrap.PORT_NEW.split('final_image_rows,',1)[1]
    modified=normal.once(original,' output logic [15:0] dbg_generation\n);',
                         ' output logic [15:0] dbg_generation,'+ports.rstrip())
    monitor=wrap.MONITOR
    for name in ('cold_correction','child_correction_accept','cold_correction_context',
                 'cold_second_correction','second_correction_sent','second_correction_pending','anchor_cycle'):
        monitor=monitor.replace('='+name+';','=candidate.'+name+';')
    monitor=monitor.replace('engine.','candidate.engine.')
    modified=normal.once(modified,'endmodule\n',monitor+'endmodule\n')
    reverse=normal.once(modified,monitor,'')
    reverse=normal.once(reverse,' output logic [15:0] dbg_generation,'+ports.rstrip(),
                        ' output logic [15:0] dbg_generation\n);')
    need(reverse==original,'ONLY_CONTINUOUS_OBSERVER_PORT_DELTA')
    files[observer]=modified.encode()
    header='rtl/tb/s4_p16_two_context_full_config.h'
    host=production['files'][production['top']+'.sv']
    second=int(host.split('SECOND_CORRECTION=',1)[1].split(';',1)[0])
    files[header]+=f'constexpr unsigned SECOND_CORRECTION={second};\nconstexpr bool OLD_PROPOSAL=false;\n'.encode()
    cpp=files[m['build']['cpp_source']].decode()
    instrument=wrap.INSTRUMENT.replace('COUNTS[c]','COUNT')
    instrument=instrument.replace('600','20000').replace('604','20004').replace('608','20008')
    instrument=instrument.replace('601','20001').replace('605','20005').replace('609','20009')
    cpp=normal.once(cpp,'static Image initial(',instrument+'\nstatic Image initial(')
    cpp=normal.once(cpp,' Result result;for(unsigned ctx=0;ctx<2;ctx++)',
                    ' cold_accepts=aliases=0;cold_by_context={};cache_counts={};\n Result result;for(unsigned ctx=0;ctx<2;ctx++)')
    cpp=normal.once(cpp,'"R84_RESET_PUBLICATION");','"R84_RESET_PUBLICATION");need(!d.probe_sent&&!d.probe_pending,"R8_FULL_RESET_CLEARS");')
    cpp=normal.once(cpp,'"R84_START_EXACT_CONTEXTS");','"R84_START_EXACT_CONTEXTS");need(!d.probe_sent&&!d.probe_pending,"R8_FULL_NEWJOB_CLEARS");')
    cpp=normal.once(cpp,'  edge(d);need(!d.error,"R84_ACTUAL_C2_ERROR age="+std::to_string(age));',
                    '  if(mask==3)wrap_tick(d,unsigned(age));else edge(d);need(!d.error,"R84_ACTUAL_C2_ERROR age="+std::to_string(age));')
    cpp=normal.once(cpp,' if(mask==3){\n  need(first[1]-first[0]',
        ' if(mask==3){\n  need(aliases==3&&cold_accepts==2&&cold_by_context[0]==1&&cold_by_context[1]==1&&d.probe_sent&&!d.probe_pending,"R8_FULL_THREE_WRAP_STATE");\n'
        '  for(unsigned f=0;f<3;f++)for(unsigned c=0;c<2;c++)need(cache_counts[f][c]==COUNT,"R8_FULL_REAL_TABLE_OWNERS");\n'
        '  need(first[1]-first[0]')
    cpp=normal.once(cpp,' d.final();return 0;', ' std::cout<<'+json.dumps(FOOTER)+';\n d.final();return 0;')
    files[CPP]=cpp.encode();m['build']['cpp_source']=CPP
    need(sha(files[ORIGINAL_VALIDATOR])==ORIGINAL_PIN,'CAPTURED_VALIDATOR_PIN')
    files[SELF]=(ROOT/SELF).read_bytes()
    files['lineage/'+wrap.SELF]=(ROOT/wrap.SELF).read_bytes()
    m['steps']=[dict(name='oneshot-full-wrap-three-aliases',argv=['{exe}'],expected_returncode=0,
        validator=dict(source=SELF,function='validate',config=before['steps'][0]['validator']['config'],
                       assets={'frozen_normal_validator':ORIGINAL_VALIDATOR}))]
    m['sources']={name:sha(raw) for name,raw in files.items()}
    snapshot={name:pin for name,pin in m['sources'].items() if name.endswith('.sv')}
    m['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=ID,
        source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
        rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))
    m['test_role']='normal'
    m['directbound_full_wrap']=dict(production_source_unchanged=True,monitor_only_stateless_observer=True,
        real_full_reference=True,base_profiles=[604832956,999999937],three_counter_aliases=True,
        source_gate=normal.IDS['full'],private_runtime_normal_gate='s4-p16-c2-combo-r8-livepair-normal-q1-v3',
        forced_value='host cycles64 only',protocol_arithmetic_payload_owner_time_unchanged=True,
        billions_of_edges_simulated=False, no_R7_wrap_execution_inherited=True,promotion_allowed=False)
    return m,files


def prepare():
    sys.path.insert(0,str(ROOT.parent))
    from fpga.reference import stream27_context_storage_combo_directbound_native as normal
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    need(not BASE.exists() and not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'FRESH_UNPAUSED')
    m,files=role();source=BASE/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    m['source_root']=str(source)
    normal.dump(BASE/'manifest.json',m);normal.dump(BASE/'host-hours.json',candidate_ladder.budget_from_hourly())
    variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-p16-c2-combo-r8-full-wrap-'+pair+'-v1';packet=BASE/('packet-'+pair)
        r=package.prepare(BASE/'manifest.json',source,profile,worker,'run',packet,BASE/'host-hours.json')
        ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
            manifest_sha256=sha((packet/'manifest.json').read_bytes()),worker_id=worker,profile=profile,native_root=ticket['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes()))
                for p in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    logical=dict(schema='gfn16-global-ticket-v1',id=ID,owner='p16-mlab',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P2',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
        minimum_ram_rationale='Bounded exploratory4GiB fullN sameR8 normal arithmetic with stateless observation only; retain OOM/timeout. DesiredGCP8 unchanged.',
        allowed_hosts=['gfn16-pilot-c4d','aethia'],est_minutes=25,promotion_bound=False,test_role='normal',
        rtl_readiness=m['rtl_readiness'],packages=variants,
        after=[normal.IDS['full'],'s4-p16-c2-combo-r8-livepair-normal-q1-v3'],on='PASS_expected_contracts')
    normal.dump(BASE/'global-ticket.json',logical)
    return dict(id=ID,ticket=str(BASE/'global-ticket.json'),status='PREPARED_NOT_NATIVE')


if __name__=='__main__':print(json.dumps(prepare(),indent=2))



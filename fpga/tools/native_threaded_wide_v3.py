"""Fixed-wide short pilot with live allocation/tool rechecks at every poll.

Preserves both prepared predecessors. The frozen v1 adapter is specialized only
for its corrected callable, this SELF/source closure and two live guard calls;
the short source role, command/compile settings and all prior guards stay fixed.
"""
import hashlib
from pathlib import Path

PRESERVED_WIDE_V1_SHA = '75bd5bae7ffa549db530c02a46c527d5d996391980385e2a28c3d5c39adac9a1'
PRESERVED_WIDE_V2_SHA = '0342e1a85f70ec3ba0afe3612f408d9e2ccffb770ebcef7b2e4352f228ff7ff5'
_path = Path(__file__).with_name('native_threaded_wide_v1.py')
_raw = _path.read_bytes()
if hashlib.sha256(_raw).hexdigest() != PRESERVED_WIDE_V1_SHA or hashlib.sha256(Path(__file__).with_name('native_threaded_wide_v2.py').read_bytes()).hexdigest() != PRESERVED_WIDE_V2_SHA:
    raise ValueError('frozen prepared wide source identities')
_text = _raw.decode()
for _old, _new in (
    ("SELF = 'tools/native_threaded_wide_v1.py'", "SELF = 'tools/native_threaded_wide_v3.py'"),
    ("MeasuredPopen=inherited.load('native_child_usage_v1.py', inherited.USAGE_SHA), validate_threaded=validate_threaded)",
     "MeasuredPopen=inherited.load('native_child_usage_v1.py', inherited.USAGE_SHA).MeasuredPopen, validate_threaded=validate_threaded)"),
    ("return dict(base().PINS, **{'tools/native_threaded_class_v1.py': BASE_SHA,",
     "return dict(base().PINS, **{'tools/native_threaded_wide_v1.py': '" + PRESERVED_WIDE_V1_SHA + "', 'tools/native_threaded_wide_v2.py': '" + PRESERVED_WIDE_V2_SHA + "', 'tools/native_threaded_class_v1.py': BASE_SHA,"),
    ("'    def guard():\\n        guard_protected(profile)\\n'",
     "\"    def guard():\\n        execution_limits(profile['cpus'])\\n        tools_for(profile)\\n        guard_protected(profile)\\n\"")
):
    if _text.count(_old) != 1:
        raise ValueError('unique live-wide source adapter anchor')
    _text = _text.replace(_old, _new, 1)
exec(compile(_text, str(Path(__file__).resolve()) + '[live-allocation-and-tools]', 'exec'), globals())

# r75 uses the other observed cache-local eight-physical-core group while the
# serial qualification keeps running. Caps come from the existing immutable
# wide overlay; only the physical group is derived from the pinned topology.
P8_ROLE='artifacts/s4-p8-canon1-continuous100-role-v1/manifest.json'
P8_ROLE_SHA='0c663d582b8973bea1658068db567eaa046d1faca56a68f6afc77ee1b03b7b2f'
PINS[P8_ROLE]=P8_ROLE_SHA
SELECTIONS={name:name for name in ('azure-burst16-thread-wide07-v1','azure-burst16-thread-wide815-v1')}
legacy_validate_threaded=validate_threaded

def profile(profile_id):
    need(profile_id in SELECTIONS,'two source-bound observed eight-physical groups only')
    data=json.loads(pinned(PROFILE_SOURCE,PROFILE_SHA).read_text())
    observed=json.loads(pinned(OBSERVATION,OBSERVATION_SHA).read_text())
    first=0 if profile_id.endswith('wide07-v1') else 8
    cpus=list(range(first,first+8))
    pair_ids=['azure-burst16-static'+str(n)+str(n+1)+'-v1' for n in range(first,first+8,2)]
    parents=[base().profile(name) for name in pair_ids]
    inherited=parents[0];template=data['profiles'][PROFILE_ID]
    need(data['host']==observed['host']==inherited['host'] and observed['uid']==inherited['uid']
         and observed['online']=='0-15' and len(observed['cpus'])==16,'exact observed physical host')
    need(data['hardware_profile_sha256']==inherited['profile_sha256']
         and data['hardware_profile_source']==inherited['profile_source'],'unchanged admitted hardware')
    need(template['cpus']==list(range(8)) and template['memory_bytes']==8<<30
         and template['cpu_quota_percent']==800 and template['compile_workers']==2,'retained eight-core caps')
    need([cpu for item in parents for cpu in item['cpus']]==cpus,'all four constituent pair allocations')
    cache=observed['cpus'][str(first)]['l3']
    need(len(cache)==1 and cache[0]['shared_cpu_list']==str(first)+'-'+str(first+7)
         and all(observed['cpus'][str(cpu)]['l3']==cache and observed['cpus'][str(cpu)]['thread_siblings_list']==str(cpu)
                 for cpu in cpus),'one observed cache domain, no SMT inflation')
    for cpu,row in observed['cpus'].items():
        need([row['physical_package_id'],row['core_id']]==inherited['topology'][cpu],'full observed physical topology')
    selected=copy.deepcopy(inherited)
    selected.update(profile_id=profile_id,profile_source=PROFILE_SOURCE,profile_sha256=PROFILE_SHA,
        cpus=cpus,cpu_quota_percent=800,memory_bytes=8<<30,memory_bytes_per_lane=8<<30,
        compile_workers=2,model_thread_counts=[1,2,4,8],observed_l3=cache[0],
        hardware_profile_source=data['hardware_profile_source'],hardware_profile_sha256=data['hardware_profile_sha256'],
        topology_observation=OBSERVATION,topology_observation_sha256=OBSERVATION_SHA,
        shared_locks=list(dict.fromkeys(name for item in parents for name in item['shared_locks'])),
        constituent_pair_locks=[item['pair_lock'] for item in parents],
        physical_locks=[name for item in parents for name in item['physical_locks']],
        pair_lock=str(Path(inherited['base'])/('.thread-wide-'+str(first)+'-'+str(first+7)+'.lock')),
        fixed_placement=dict(id='burst16-wide'+('07' if first==0 else '815')+'-v1',lane_ids=pair_ids,cpus=cpus))
    selected['runtime_allocation']=dict(cpus=cpus,physical_cores=[selected['topology'][str(cpu)] for cpu in cpus],
        cpu_quota_percent=800,compile_workers=2,memory_bytes=8<<30)
    base().load('native_thread_config_v1.py',base().RUNTIME_SHA).validate_allocation(selected['runtime_allocation'],8)
    return selected

def validate_threaded(manifest):
    declared=manifest.get('wide_thread_pilot',{}).get('serial_contract')
    original=declared if declared is not None else json.loads(pinned(P8_ROLE,P8_ROLE_SHA).read_text())
    if declared is not None:
        need(type(declared) is dict and set(declared)=={'build','probe','steps','sources'},'closed owner-declared serial contract')
        digest=hashlib.sha256(json.dumps(declared,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        need(manifest['wide_thread_pilot'].get('serial_contract_sha256')==digest
             and declared['probe']['expected_json']==dict(context_threads=1,model_threads=1,expected_threads=1)
             and declared['build']['parameters'].get('AW')==16,'source-bound actual AW16 serial contract')
    config=base().load('native_thread_config_v1.py',base().RUNTIME_SHA)
    count=config.validate_build(manifest['build'],manifest['probe']['expected_json'])
    build=copy.deepcopy(manifest['build']);build.pop('runtime_threads',None)
    build['cflags']=[flag for flag in build['cflags'] if flag!=f'-DGFN16_RUNTIME_THREADS={count}']
    if build!=original['build'] or manifest['steps']!=original['steps']:
        return legacy_validate_threaded(manifest)
    need(count in (1,4,8) and manifest['probe']['argv']==original['probe']['argv'],
         'source-identical P8 continuous100 serial/four/eight pilot only')
    need(all(manifest['sources'].get(name)==pin for name,pin in original['sources'].items()),
         'unchanged complete arithmetic/cycles/reference source')
    if declared is None:need(manifest['sources'].get(P8_ROLE)==P8_ROLE_SHA,'known P8 donor source')
    return count

def guard_protected(selected):
    need(selected['profile_id'] in SELECTIONS and selected['burst_deadline_epoch']==DEADLINE,'exact fixed-wide deadline')
    need(time.time()+3715<DEADLINE-DRAIN_LEAD_SECONDS,'full finite bound before unchanged drain')
    return base().source_policy().host.guard_protected(selected)

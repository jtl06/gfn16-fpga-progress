"""Repair generated-function namespace identity; finite long policy unchanged."""
import copy
import ast
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import types

HERE = Path(__file__).resolve().parent
PARENT_SHA = 'ed9c3bbc8796862effc9409beff9a440cb2d13cd4b4cb55f822925ab5ecf1c4f'
SELF = 'tools/native_long_class_v2.py'


def previous():
    path = HERE / 'native_long_class_v1.py'
    if hashlib.sha256(path.read_bytes()).hexdigest() != PARENT_SHA:
        raise ValueError('frozen long runtime')
    spec = importlib.util.spec_from_file_location('_long_runtime_parent', path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


base = previous()
burst = base.load('native_class_burst8_v1.py','8c7234c341ad20823520761c429e030f26b8ed4e90cb4b171f3f91f328cfe767')
WIDE_PIN='71924875229a549fbcfb8cd52252406a8610d40946597e1d8b2470ae843466d7'
wide=base.load('native_threaded_wide_v3.py',WIDE_PIN)
PINS = dict(base.PINS, **burst.PINS, **{'tools/native_long_class_v1.py': PARENT_SHA,
    'tools/native_class_burst8_v1.py':'8c7234c341ad20823520761c429e030f26b8ed4e90cb4b171f3f91f328cfe767'})
PINS.update(wide.PINS,**{'tools/native_threaded_wide_v3.py':WIDE_PIN})
SELECTIONS = dict(base.SELECTIONS,**{name:name for name in burst.SELECTIONS if name.startswith('azure-burst16-static8g')},**wide.SELECTIONS)
def profile(name):
    if name in wide.SELECTIONS:return wide.profile(name)
    if name.startswith('azure-burst16-static8g'):return burst.profile(name)
    return base.profile(name)


def validate_allocation(allocation, threads):
    """Compiler parallelism is bounded by owned physical cores, not j2."""
    config=wide.base().load('native_thread_config_v1.py',wide.base().RUNTIME_SHA)
    legacy=copy.deepcopy(allocation);legacy['compile_workers']=2
    config.validate_allocation(legacy,threads)
    workers=allocation['compile_workers'];cores=len(allocation['physical_cores'])
    wide.need(type(workers) is int and 1<=workers<=cores
              and allocation['cpu_quota_percent']>=100*max(threads,workers),
              'compiler workers fit reserved physical cores/quota')
    return copy.deepcopy(allocation)


def compilation_bound(manifest, report, workers):
    """Source-bound wait4 compiler peak, 20% headroom plus 512MiB fixed reserve.

    This is a conservative sizing estimate, not a promise to avoid OOM. Default
    j2 needs no new measurement; explicit higher parallelism uses its own typed
    pilot's exact compiler child evidence and never raises the RAM ceiling.
    """
    allocation=manifest['fixed_execution']['runtime_allocation']
    validate_allocation(dict(allocation,compile_workers=workers),manifest['build']['runtime_threads'])
    rows=[row for row in report['steps'] if row['name']=='build']
    wide.need(len(rows)==1 and rows[0]['returncode']==0 and rows[0]['error'] is None,
              'successful own compiler measurement')
    usage=rows[0]['native_child_usage'];rss=usage.get('peak_rss_kib')
    wide.need(usage.get('schema')=='native-wait4-child-usage-v1' and usage.get('returncode')==0
              and type(rss) is int and rss>0,'own finite wait4 compiler RSS, not cumulative RSS')
    peak=rss*1024;estimate=(peak*workers*6+4)//5+(512<<20)
    wide.need(estimate<=allocation['memory_bytes'],'compiler RSS estimate plus headroom exceeds reserved RAM')
    return dict(schema='source-bound-compile-allocation-v1',compile_workers=workers,
                pilot_report_sha256=manifest['runtime_duration']['evidence']['pilot_report']['sha256'],
                compiler_peak_rss_bytes=peak,per_worker_margin_numerator=6,
                per_worker_margin_denominator=5,fixed_reserve_bytes=512<<20,
                estimated_peak_bytes=estimate,memory_ceiling_bytes=allocation['memory_bytes'],
                estimate_not_oom_guarantee=True)


def selected_for(manifest, selected=None):
    selected=copy.deepcopy(profile(manifest['cpu_profile']) if selected is None else selected)
    if not selected.get('runtime_allocation'):return selected
    actual=manifest['fixed_execution']['runtime_allocation']
    original=copy.deepcopy(actual);original['compile_workers']=2
    wide.need(original==selected['runtime_allocation']
              and manifest['fixed_execution']['placement']==selected['fixed_placement'],
              'real immutable physical/RAM/quota reservation; only compiler count may vary')
    validate_allocation(actual,manifest['build']['runtime_threads'])
    selected.update(runtime_allocation=copy.deepcopy(actual),compile_workers=actual['compile_workers'])
    return selected


def build_identity(manifest, selected):
    """Keep the captured old helper; record the actual allocation/build flags."""
    legacy=copy.deepcopy(selected);legacy['runtime_allocation']['compile_workers']=2
    value=wide.base().load('build_identity_v2.py',wide.base().IDENTITY_SHA).build_identity(manifest,legacy)
    allocation=validate_allocation(selected['runtime_allocation'],manifest['build']['runtime_threads'])
    identity=value['identity'];identity['runtime_allocation']=allocation
    identity['compile_workers']=allocation['compile_workers']
    flags=identity['verilator_flags'];flags[flags.index('-j')+1]=str(allocation['compile_workers'])
    return dict(identity=identity,build_key=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest())


def identity_module(original):
    value=types.ModuleType('_actual_owned_compile_build_identity')
    value.__dict__.update(original.__dict__,build_identity=build_identity)
    return value


def wide_parent(name, selected):
    """Same source/FD namespace with actual compilation configuration."""
    value=wide.parent(name)
    value.PROFILES={selected['host']:selected}
    value.identity=identity_module(value.identity)
    configuration=types.ModuleType('_owned_runtime_allocation')
    configuration.__dict__.update(value.runtime.__dict__,validate_allocation=validate_allocation)
    value.runtime=configuration
    return value


def execution_limits(selected):
    if selected.get('runtime_allocation'):
        # Validate only the job's owned subset and actual ceilings. Full online
        # topology/cache equality is performance metadata, not a launch gate.
        wide.need(wide.socket.gethostname()==selected['host'] and wide.os.geteuid()==selected['uid']
                  and wide.pwd.getpwuid(wide.os.geteuid()).pw_name==selected['user'],'approved wide host and own user')
        allocation=selected['runtime_allocation'];validate_allocation(allocation,len(allocation['cpus']))
        cpus=sorted(wide.os.sched_getaffinity(0));wide.need(cpus==allocation['cpus'],'owned physical CPU affinity')
        topology={};cache={}
        for cpu in cpus:
            directory=wide.Path('/sys/devices/system/cpu')/('cpu'+str(cpu))
            topology[str(cpu)]=[int((directory/'topology'/key).read_text()) for key in ('physical_package_id','core_id')]
            cache[str(cpu)]=[{key:(row/key).read_text().strip() for key in ('level','type','id','shared_cpu_list')}
                for row in (directory/'cache').glob('index*') if (row/'level').read_text().strip()=='3']
        wide.need([topology[str(cpu)] for cpu in cpus]==allocation['physical_cores']
                  and len(set(map(tuple,topology.values())))==len(cpus),'reserved distinct physical ownership')
        group=wide.Path('/proc/self/cgroup').read_text().strip()
        wide.need(group.startswith('0::/') and '\n' not in group,'unified own cgroup')
        directory=wide.Path('/sys/fs/cgroup')/group[3:].lstrip('/')
        memory=(directory/'memory.max').read_text().strip();quota=(directory/'cpu.max').read_text().split()
        wide.need(memory!='max' and 0<int(memory)<=allocation['memory_bytes']
                  and len(quota)==2 and quota[0]!='max' and int(quota[1])>0
                  and 0<int(quota[0])*100<=allocation['cpu_quota_percent']*int(quota[1]),
                  'finite actual memory and CPU caps within reservation')
        wide.need((directory/'memory.swap.max').read_text().strip()=='0','wide zero swap')
        available=int(next(row.split()[1] for row in wide.Path('/proc/meminfo').read_text().splitlines()
                          if row.startswith('MemAvailable:')))*1024
        wide.need(available>=allocation['memory_bytes']+selected['minimum_host_available_bytes'],
                  'owned job plus host memory reserve')
        return dict(cgroup=group[3:],memory_max_bytes=int(memory),swap_max_bytes=0,cpu_max=quota,
                    affinity=cpus,physical_cores=[topology[str(cpu)] for cpu in cpus],
                    observed_l3=cache,compile_workers=allocation['compile_workers'],
                    hardware_profile_sha256=selected['hardware_profile_sha256'])
    return base.execution_limits(selected)
raw_duration=(HERE/'native_long_duration_v1.py').read_bytes()
if hashlib.sha256(raw_duration).hexdigest()!=base.DURATION_SHA:raise ValueError('source-bound long duration')
text=raw_duration.decode()
old="need(host == 'gfn16-pilot-c4d', 'first long shape is GCP only')"
if text.count(old)!=1:raise ValueError('exact duration host anchor')
text=text.replace(old,"need(host in ('gfn16-pilot-c4d','gfn16-azure-sim-f32'), 'existing admitted serial long hosts')")
duration=types.ModuleType('_existing_long_host_duration')
exec(compile(text,'[existing finite duration on admitted serial hosts]','exec'),duration.__dict__)
PHASE_HELPER='reference/stream27_s4_continuous_duration_v1.py'
phase_path=HERE.parent/PHASE_HELPER
PHASE_PIN='d9a42c646cd43100e3ba2ded39fcf17fc32f87835b715234393df2ba26534ade'
P16_PHASE_PIN='5baef385edd5ae02e1b3ae24d735d525d1e700df9a62fba817e0d683d7f2ac97'
PREVIOUS_PHASE_PIN='87fd2011f7312216ad3a8d00dfe637698068e8670fd09c597fe8ae553f4981d9'
LEGACY_PHASE_PIN='9959897f37a10505ca4ff235647bfb70b0a607b8fc0dc911500ef93daca1d16e'
if hashlib.sha256(phase_path.read_bytes()).hexdigest()!=PHASE_PIN:raise ValueError('known source phase prediction helper')
PINS[PHASE_HELPER]=PHASE_PIN
spec=importlib.util.spec_from_file_location('_long_native_phase_prediction',phase_path)
phase=importlib.util.module_from_spec(spec);spec.loader.exec_module(phase)
prior_assess=duration.assess

C2_SCHEMA='stream27-p16-c2-measured-continuous-forecast-v1'
C2_HELPER='reference/stream27_p16_two_context_continuous.py'
C2_HELPER_PIN='8b13dd1885df71e9a365d35e346e541add6eddb1e34561f8e55c23197f491c34'
C2_HEADER='rtl/tb/s4_p16_two_context_full_config.h'
C2_HEADER_DELTA=dict(path=C2_HEADER,
    pilot_sha256='e06a350ca1ebf13fce1932533493e013d0686adb1383e233b09361cf49b6a300',
    full_sha256='1d7f8d98f13b6788e730c32465e7893a4c5660393afb69a40b6064120cab8701')
C2_CPP='rtl/tb/stream27_p16_two_context_threadpilot.cpp'
C2_CPP_PIN='0121cc93bb708e8ad2b40a3ca939aa9b2dee15393a5d7e23f49b9823ac8e8ade'
C2_PILOT_VALIDATOR='reference/stream27_p16_two_context_threadpilot.py'
C2_PILOT_VALIDATOR_PIN='b3131c33d271c36a70938620100f5e0818419733791166ba926cd154aa1c2659'
C2_PILOT_TYPED_PIN='0a383f6a31da809d34217854a4cd0db9d03fce61605c993b0b3a0237fa9a6aa6'
C2_EVIDENCE_PINS=dict(
    pilot_manifest='40367a8976063fa898d685b7f8341ada45316cb561d0b06280e60c3d70ed59b0',
    pilot_report='8e096af83df0773ef68b8d4d6f8ff4532558965bb286b440b848fdf27710d982',
    pilot_gate='32267640a6a61c0d38cdf5d3ea7565376deffb651cb64463637d5adfe467ba29')
C2_STEP='normal-full-c2-continuous1000-percontext'
C2_PILOT_STEP='normal-full-c2-own100-percontext-threadpilot'
C2_PARAMETERS=dict(AW=16,P=16,CONTEXTS=2,CORR_SERIAL_BFS=2,MONT_FACTORED=1,
    COMM_STAGE_SHARED_MLAB=1,COLD_LAUNCH_FENCE=1,EXPLICIT_NET_DECLARATIONS=1,EPOCH_SEED0=65534,EPOCH_SEED1=42)
C2_FAMILIES={C2_HELPER:dict(helper=C2_HELPER,helper_pin=C2_HELPER_PIN,
    header_delta=C2_HEADER_DELTA,cpp_pin=C2_CPP_PIN,validator=C2_PILOT_VALIDATOR,
    validator_pin=C2_PILOT_VALIDATOR_PIN,typed_pin=C2_PILOT_TYPED_PIN,
    evidence_pins=C2_EVIDENCE_PINS,pilot_step=C2_PILOT_STEP,full_step=C2_STEP,
    full_validator=C2_HELPER,full_validator_pin=C2_HELPER_PIN,
    parameters=C2_PARAMETERS,sv_count=54,interval=8459,carry_done=12557,
    first_edges=[204,4433],done_edges=[1509667,2169130],joint_cycles=2234666,
    overlap_edges=1509666,source_family='corrected53')}
C2_TIMING_HELPER='reference/stream27_context_timing_continuous.py'
C2_TIMING_VALIDATOR='reference/stream27_context_timing_long_native.py'
C2_FAMILIES[C2_TIMING_HELPER]=dict(helper=C2_TIMING_HELPER,
    helper_pin='212c06164822ca63d3af4fd8035aab51699f60704d5ce84208c8d0c6ff4209c6',
    header_delta=dict(path=C2_HEADER,
        pilot_sha256='00722f4d93b2daa164722b32a2f16473435bce2fa6f830596ea2fef972ca7738',
        full_sha256='2db65dc8d1cbc1f27475ecb00f866997fd1449b1bf8603dbac263bf5606441d0'),
    cpp_pin=C2_CPP_PIN,validator=C2_TIMING_VALIDATOR,full_validator=C2_TIMING_VALIDATOR,
    validator_pin='32fbb3a6c2456f4af5b73266400901be32719365c8b40b8b1c759b55a76117ff',
    full_validator_pin='32fbb3a6c2456f4af5b73266400901be32719365c8b40b8b1c759b55a76117ff',
    typed_pin='ac36e5c48fddce8f1fbade5850672a201433ceaf5d78e2e49929d3118be35fd2',
    evidence_pins=dict(
        pilot_manifest='3683a63299e52ef2f3b4936b9c61184ce43881e9284ccac08d9fa90e07c432c6',
        pilot_report='b338a30b99eaa539f1701caf5faff7305eaa4d0b024e180eda009bd9f1247bdd',
        pilot_gate='2e43631f4832f6cae4358bdb15e000f07962fba191ce8a818ece54eea5a00171'),
    pilot_step='normal-full-c2-timing-own100-percontext-threadpilot',
    full_step='normal-full-c2-timing-continuous1000-percontext',parameters=C2_PARAMETERS,
    sv_count=59,interval=8460,carry_done=12558,first_edges=[204,4434],
    done_edges=[1509767,2169230],joint_cycles=2234766,overlap_edges=1509766,source_family='timing58')
C2_STORAGE_HELPER='reference/stream27_context_storage2_continuous.py'
C2_STORAGE_VALIDATOR='reference/stream27_context_storage2_long_native.py'
C2_FAMILIES[C2_STORAGE_HELPER]=dict(helper=C2_STORAGE_HELPER,
    helper_pin='378e427a8b8af4208354ef9add9c1747fc718207013eff5f3f38e37c170348f3',
    header_delta=C2_HEADER_DELTA,cpp_pin=C2_CPP_PIN,
    validator=C2_STORAGE_VALIDATOR,full_validator=C2_STORAGE_VALIDATOR,
    validator_pin='5ff2a3060e0b799062f180dab7ef2547ea4bc298c73a7d8d5357871bdcfca25a',
    full_validator_pin='5ff2a3060e0b799062f180dab7ef2547ea4bc298c73a7d8d5357871bdcfca25a',
    typed_pin='2d4862c0638f14cd190d9ee5145b3445b58d4d3b1ecb9e2eaf9d2c5b6f4cd406',
    # Exact selected immutable serial pilot, never the old Azure donor.
    evidence_pins=dict(
        pilot_manifest='bd11949652b0e76f0bbb004ca1db6e171b7955061dfe4a2262413b1144add86b',
        pilot_report='989276798e7a2bdcc850eb4e0fea6f18a1bf922d18ff1824d083913c77124a4a',
        pilot_gate='60f581d9bad38a7f51e3f58c17f89ce30158e0ebbe76210ff30fcb14fb404148'),
    pilot_step='normal-full-c2-storage2-own100-percontext',
    full_step='normal-full-c2-storage2-continuous1000-percontext',parameters=C2_PARAMETERS,
    sv_count=54,interval=8459,carry_done=12557,first_edges=[204,4433],
    done_edges=[1509667,2169130],joint_cycles=2234666,overlap_edges=1509666,
    source_family='storage2-original53',threads=1,host='gfn16-pilot-c4d')


def c2_frame_calendar(geometry,count,interval):
    """Independent scalar ports/leases for each exact C2 source calendar."""
    need=duration.need
    need(type(interval) is int and interval in (8459,8460),'known source-specific C2 interval')
    delta=interval-8459;half=interval//2
    expected=dict(n=65536,p=16,rows=4096,contexts=2,pointwise_accept=4207,
        sink_accept=8416+delta,last_sink=12511+delta,first_digit=interval-1,carry_done=12557+delta,
        warm_interval=interval,feedback_delay=0,next_correction_accept=12557+delta,
        term_seed_first=70+delta,term_seed_last=73+delta,correction_cache_latency=77+delta,
        correction_pair_interval=60,lease_banks=4)
    need(type(count) is int and count in (100,1000) and
         all(type(geometry.get(k)) is int and geometry[k]==v for k,v in expected.items()),
         'exact own C2 scalar calendar geometry')
    frames=sorted((k*interval+context*half,context,k) for context in (0,1) for k in range(count))
    def disjoint(windows):
        ordered=sorted(windows)
        need(all(b[0]>a[1] for a,b in zip(ordered,ordered[1:])), 'C2 exclusive acceptance windows')
    for offset,width in ((0,4096),(4207,4096),(expected['sink_accept'],4096),
                         (interval-1,4096),(expected['sink_accept'],4142)):
        disjoint([(start+offset,start+offset+width-1) for start,_,_ in frames])
    pw=[(start+4207,start+8302) for start,_,_ in frames]
    previous={};correction=[];live={};leases=[];peak=0
    for start,context,k in frames:
        available=start if context not in previous else max(start,previous[context]+expected['next_correction_accept'])
        accept=available
        for lo,hi in pw:
            if accept+expected['term_seed_first']<=hi and accept+expected['term_seed_last']>=lo:
                accept=hi+1-expected['term_seed_first']
        cache=accept+expected['correction_cache_latency'];margin=start+4207-cache-1
        need(margin>=0,'C2 PRE-pointwise correction cache deadline')
        correction.append(dict(tag=[context,1,((65534,42)[context]+k)&65535,k],
            available=available,accept=accept,seed_first=accept+expected['term_seed_first'],seed_last=accept+expected['term_seed_last'],
            cache_capture=cache,pointwise_first=start+4207,margin=margin))
        previous[context]=start
        live={bank:old for bank,old in live.items() if old+expected['last_sink']>=start}
        free=[bank for bank in range(4) if bank not in live]
        need(bool(free),'C2 PRE-edge four-lease capacity')
        bank=free[0];live[bank]=start;peak=max(peak,len(live));leases.append([context,k,start,bank])
    disjoint([(row['accept'],row['accept']+1) for row in correction])
    disjoint([(row['accept']+9,row['accept']+68) for row in correction])
    seeds=[(row['seed_first'],row['seed_last']) for row in correction]
    disjoint(pw+seeds);disjoint([(lo,lo+4091) for lo,_ in pw]+seeds)
    for x in correction:
        need(all(x is y or not y['seed_first']<=x['accept']<=y['seed_last'] for y in correction),
             'C2 no correction accepted during another seed')
    return dict(status='PASS_SOURCE_EDGE_MODEL_ONLY',frames=2*count,per_context_interval=interval,
        launch_gaps=[half,interval-half],correction=correction,lease_allocation=leases,lease_peak=peak,
        feedback_peak_rows=[0,0],feedback_identity='previous_start+FIRST_DIGIT+1+r == next_start+r',
        full_N_numeric_performed=False,runtime_forecast=False)


def c2_timing_calendar(geometry,count):
    return c2_frame_calendar(geometry,count,8460)


def c2_publication_edges(warm_edges):
    """Exact shared finalizer: rows, ordinary9N, copyN+3 and control edges.

    Warm completion is not publication. Both final images pass the serialized
    canonical/copy owner, followed by the second image's full E0/E1 readback.
    """
    duration.need(type(warm_edges) is list and len(warm_edges)==2 and
                  all(type(edge) is int and edge>0 for edge in warm_edges),
                  'two positive own C2 warm completions')
    release=-1;done=[]
    for edge in warm_edges:
        release=max(edge+2,release+1)+4096+9*65536+(65536+3)+3
        done.append(release)
    return done,release+65536


def c2_source_family(forecast):
    family=C2_FAMILIES.get(forecast.get('generator'))
    duration.need(family is not None and forecast.get('generator_sha256')==family['helper_pin'],
                  'known exact C2 source-specific forecast generator')
    return family


def model_threads(manifest):
    """Known C2 serial capture declares1 and uses the header's actual default1.

    Keep its compiled bytes unchanged rather than adding a new macro solely
    for packaging. Wider or otherwise overridden declarations retain the
    existing exact macro/probe check.
    """
    build=manifest['build'];probe=manifest['probe']['expected_json']
    serial=any(family.get('threads')==1 and
        manifest['sources'].get(family['helper'])==family['helper_pin'] and
        manifest['steps'][0].get('validator',{}).get('source')==family['full_validator']
        for family in C2_FAMILIES.values())
    if (serial and type(build.get('runtime_threads')) is int and build['runtime_threads']==1 and
        not any('RUNTIME_THREADS' in flag for flag in build.get('cflags',[]))):
        original=copy.deepcopy(build);original.pop('runtime_threads')
        return phase.model_threads(original,probe)
    return phase.model_threads(build,probe)


def c2_scalar_functions(family=None):
    """Only four pinned scalar metadata ASTs; no C2 role/oracle module import."""
    family=C2_FAMILIES[C2_HELPER] if family is None else family
    path=HERE.parent/family['helper'];raw=path.read_bytes()
    duration.need(not path.is_symlink() and hashlib.sha256(raw).hexdigest()==family['helper_pin'],'exact private C2 scalar helper')
    wanted={'bits','config','header','predict'}
    nodes=[node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name in wanted]
    duration.need(len(nodes)==len(wanted) and {node.name for node in nodes}==wanted,'four exact C2 scalar functions')
    namespace=dict(COUNT=1000,THREADS=family.get('threads',8),BASES=[604832956,999999937],SHAPE=copy.deepcopy(phase.SHAPE),
        need=duration.need,math=math,re=re)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'[pinned C2 scalar metadata only]','exec'),namespace)
    return namespace


def c2_allocation(manifest,pilot,report,count):
    """Actual source/thread pilot allocation; existing serial pairs or wide."""
    need=duration.need;limits=report['limits']
    if count==1:
        selected=profile(pilot['cpu_profile'])
        full=profile(manifest.get('cpu_profile',pilot['cpu_profile']))
        need(report['host']==selected['host']==full['host']=='gfn16-pilot-c4d' and
             selected['model_threads']==full['model_threads']==1 and
             selected['compile_workers']==full['compile_workers']==report['compile_workers']==2 and
             selected['memory_bytes']==full['memory_bytes']==8<<30 and
             selected['cpu_quota_percent']==full['cpu_quota_percent']==200 and
             len(selected['cpus'])==len(full['cpus'])==2,
             'own GCP serial model1/two-physical8GiB/j2, not Azure or declared wide')
        actual=[selected['topology'][str(cpu)] for cpu in selected['cpus']]
        target=[full['topology'][str(cpu)] for cpu in full['cpus']]
        need(len(set(map(tuple,actual)))==len(set(map(tuple,target)))==2 and
             limits['affinity']==selected['cpus'] and limits['physical_cores']==actual and
             limits['memory_max_bytes']==8<<30 and limits['swap_max_bytes']==0 and
             list(map(int,limits['cpu_max']))==[200000,100000] and
             not any(k in manifest for k in ('fixed_execution','wide_thread_pilot','compile_allocation')),
             'actual serial physical/core/RAM/cgroup ownership, no inherited eight-thread metadata')
        return
    need(count==8,'known C2 eight-thread or own serial allocation only')
    execution=manifest['fixed_execution'];allocation=execution['runtime_allocation']
    original=copy.deepcopy(execution);original['runtime_allocation']['compile_workers']=pilot['fixed_execution']['runtime_allocation']['compile_workers']
    need(manifest.get('cpu_profile',execution['profile_id'])==execution['profile_id']==pilot['cpu_profile'] and
         execution['profile_id'] in wide.SELECTIONS and original==pilot['fixed_execution'] and
         len(allocation['cpus'])==len(set(map(tuple,allocation['physical_cores'])))==8 and
         allocation['memory_bytes']==8<<30 and allocation['cpu_quota_percent']==800 and
         limits['affinity']==allocation['cpus'] and limits['physical_cores']==allocation['physical_cores'] and
         limits['memory_max_bytes']==8<<30 and limits['swap_max_bytes']==0 and
         list(map(int,limits['cpu_max']))==[800000,100000] and
         report['exact_build_identity']['identity']['runtime_allocation']==pilot['fixed_execution']['runtime_allocation'],
         'own C2 same eight physical allocation/8GiB/800percent')
    validate_allocation(allocation,count)
    if allocation['compile_workers']!=2 or 'compile_allocation' in manifest:
        need(manifest.get('compile_allocation')==compilation_bound(manifest,report,allocation['compile_workers']),
             'C2 recomputed compiler memory bound')


def assess_c2(manifest,values,pins,host,policy=None):
    """A known frozen C2 family's OWN100→1000, sole private header delta."""
    policy=duration if policy is None else policy
    need=duration.need
    need(set(values)==set(pins)==set(duration.EVIDENCE),'four exact C2 evidence inputs')
    forecast,pilot,report,gate=(values[k] for k in ('forecast','pilot_manifest','pilot_report','pilot_gate'))
    family=c2_source_family(forecast)
    need(all(pins[k]==v for k,v in family['evidence_pins'].items()),'exact source-specific C2 selected pilot evidence')
    scalar=c2_scalar_functions(family);full_config=scalar['config']()
    need(host==family.get('host','gfn16-azure-sim-f32') and report['host']==host and forecast['compatible_hosts']==[host],
         'C2 actual own pilot host, no C1 or cross-host timing')
    count=model_threads(manifest)
    need(count==family.get('threads',8)==policy.SHAPE['model_threads']==forecast['model_threads']==report['model_threads'] and
         report['probe']==manifest['probe']['expected_json']==pilot['probe']['expected_json'],
         'own C2 exact actual model/context/probe count, no thread-rate borrowing')
    need(forecast['schema']==C2_SCHEMA and forecast['status']=='PASS_C2_own100_measured_continuous_forecast' and
         manifest['sources'].get(family['helper'])==family['helper_pin'] and
         manifest['sources'].get(family['full_validator'])==family['full_validator_pin'],
         'exact frozen C2 forecast/validator source')
    need(gate['status']=='PASS_expected_contracts' and gate['promotion_allowed'] is False and
         gate['manifest_sha256']==pins['pilot_manifest'] and gate['report_sha256']==pins['pilot_report'] and
         report['status']=='completed_native_commands_unreviewed' and report['manifest_sha256']==pins['pilot_manifest'] and
         all(forecast['short_'+k+'_sha256']==pins['pilot_'+k] for k in ('manifest','report','gate')),
         'actual C2 typed pilot raw bindings')
    need(manifest['build']==pilot['build']==forecast['source_model_build'] and manifest['probe']==pilot['probe'] and
         manifest['build']['parameters']==family['parameters'] and
         all(type(v) is int for v in manifest['build']['parameters'].values()) and
         manifest['build']['cpp_source']==C2_CPP and len(manifest['build']['sv_sources'])==family['sv_count'],
         'unchanged corrected C2 production/build/probe')
    c2_allocation(manifest,pilot,report,count)
    model_pins=forecast['source_model_pins']
    required=set(manifest['build']['sv_sources'])|{C2_CPP,'rtl/tb/native_runtime_context_v1.h',
        'rtl/tb/stream27_host_chain_full_reference_v1.h','rtl/tb/stream27_shared_reference_ntt_v1.h'}
    need(set(model_pins)==required and all(manifest['sources'].get(k)==pilot['sources'].get(k)==v
         for k,v in model_pins.items()) and model_pins[C2_CPP]==family['cpp_pin'],
         'complete own C2 RTL/CPP/independent references/runtime identical')
    delta=family['header_delta']
    need(forecast['allowed_compiled_delta']==delta and
         manifest['sources'].get(C2_HEADER)==delta['full_sha256'] and
         pilot['sources'].get(C2_HEADER)==delta['pilot_sha256'] and
         pilot['sources'].get(family['validator'])==family['validator_pin'],
         'sole frozen deterministic COUNT/BITS header change')
    need(len(manifest['steps'])==len(pilot['steps'])==1,'one C2 native command')
    wanted=dict(name=family['full_step'],argv=['{exe}'],expected_returncode=0,
        validator=dict(source=family['full_validator'],function='validate',config=full_config,assets={}))
    pilot_config=dict(full_config,count=100,doubles=101)
    wanted_pilot=dict(name=family['pilot_step'],argv=['{exe}'],expected_returncode=0,
        validator=dict(source=family['validator'],function='validate',config=pilot_config,assets={}))
    need(manifest['steps'][0]==wanted and pilot['steps'][0]==wanted_pilot and forecast['full_config']==full_config,
         'exact own C2 normal config/STEP/argv100 to1000')
    expected_continuity=dict(count_per_context=1000,model_threads=count,production_and_cpp_unchanged=True,
        compiled_source_delta=[C2_HEADER],original_header_sha256=delta['pilot_sha256'],
        full_header_sha256=delta['full_sha256'],deterministic_prefix_equal=True,
        initial_resets=1,initial_load_words=131072,descriptors=1998,bases=full_config['bases'],
        no_reload_or_checkpoint_barrier=True,full_N_numeric_locally_performed=False)
    need(manifest['r84']['continuous']==expected_continuity,'exact two dependent1000 chains, no reload/barrier')
    if family['source_family']=='timing58':
        full_context=manifest['context_timing'];pilot_context=pilot['context_timing']
        need({k:v for k,v in full_context.items() if k!='own_long'}==
             {k:v for k,v in pilot_context.items() if k!='own_long'},'unchanged timing58 production/calendar identity')
        for model,operations in ((manifest,1000),(pilot,100)):
            own=model['context_timing']['own_long']
            need(own['count_per_context']==operations and own['threads']==count and own['feed_mode'] is True and
                 own['initial_resets']==1 and own['initial_load_words']==131072 and
                 own['descriptors']==2*(operations-1) and own['no_reset_reload_barrier'] is True and
                 own['old_pilot_forecast_used'] is False and own['reference_phase_joins_checked'] is True and
                 own['normal_cpp_donor_pin']==family['cpp_pin'] and own['full_N_numeric_locally_performed'] is False,
                 'exact timing58 source-specific continuous ownership')
            need(own['own_calendar']==c2_timing_calendar(model['context_timing']['calendar']['geometry'],operations),
                 'independently recomputed own timing58 full calendar/ports/leases')
    if family['source_family']=='storage2-original53':
        full_context=manifest['storage2'];pilot_context=pilot['storage2']
        need({k:v for k,v in full_context.items() if k!='own_long'}==
             {k:v for k,v in pilot_context.items() if k!='own_long'},
             'unchanged original storage2 production/calendar identity')
        production=full_context['production_generated_sha256']
        need(len(production)==53 and
             {Path(name).name:manifest['sources'][name] for name in manifest['build']['sv_sources']
              if Path(name).name in production}==production,
             'original53 production plus sole observer, no timing58 source inheritance')
        for model,operations in ((manifest,1000),(pilot,100)):
            own=model['storage2']['own_long']
            need(own['count_per_context']==operations and own['threads']==count and own['feed_mode'] is True and
                 own['initial_resets']==1 and own['initial_load_words']==131072 and
                 own['descriptors']==2*(operations-1) and own['no_reset_reload_barrier'] is True and
                 own['prior_forecast_used'] is False and own['reference_phase_joins_checked'] is True and
                 own['normal_cpp_donor_pin']==family['cpp_pin'] and own['full_N_numeric_locally_performed'] is False,
                 'exact original storage2 own-source continuous ownership')
            need(own['own_calendar']==c2_frame_calendar(model['storage2']['geometry'],operations,family['interval']),
                 'independently recomputed original8459 full calendar/ports/leases')
    rows=[v for v in report['steps'] if v['name']==family['pilot_step']]
    gates=[v for v in gate['steps'] if v['name']==family['pilot_step']]
    need(len(rows)==len(gates)==1 and rows[0]['returncode']==gates[0]['actual_returncode']==0 and
         rows[0]['error'] is None and gates[0]['stdout_sha256']==rows[0]['sha256'],
         'actual unique successful C2 model command')
    need(gates[0]['typed_validator_sha256']==family['typed_pin'],'exact source-specific C2 typed validator digest')
    native=gates[0]['validation']
    need(native==report['validations'][family['pilot_step']]==forecast['pilot_native_validation'] and
         native['status']=='PASS_expected_contracts' and native['promotion_allowed'] is False,
         'C2 typed validation equality')
    measured=native['measurements']
    expected=dict(aw=16,p=16,contexts=2,bases=full_config['bases'],count_per_context=100,
        squares=200,descriptors=198,doubles=101,reads=262144,signed96=True,independent_reference=True,
        initial_resets=1,initial_load_words=131072,interval=family['interval'],peer_live_reads=65536,model_threads=count)
    launches=[[first+k*family['interval'] for k in range(100)] for first in family['first_edges']]
    warm=[row[-1]+family['carry_done']+1 for row in launches]
    done,joint=c2_publication_edges(warm)
    need(done==family['done_edges'] and joint==family['joint_cycles'],
         'independent own C2 ordinary final publication ledger')
    need(all(measured[k]==v and type(measured[k]) is type(v) for k,v in expected.items()) and
         measured['launches']==launches and measured['setup_edges']==[99,199] and
         measured['warm_edges']==warm and measured['done_edges']==done and measured['joint_cycles']==joint and
         measured['overlap_edges']==family['overlap_edges'],
         'own200 operations/4N signed96/calendar/ownership, not C1')
    phase.positive(rows[0]['seconds']);phase.positive(report['seconds'])
    for key in ('reference_seconds','model_seconds','seconds'):phase.positive(measured[key])
    need(abs(measured['reference_seconds']+measured['model_seconds']-measured['seconds'])<.05 and
         abs(measured['seconds']-rows[0]['seconds'])<1,'own C2 model/reference phase sum')
    prediction=scalar['predict'](rows[0]['seconds'],report['seconds'])
    need(prediction==forecast['forecast'] and prediction['fits_finite_shape'] is True,
         'recomputed own C2 ratio/margin/overhead/reserve within finite shape')
    return dict(status='PASS_C2_own_measured_finite_duration_only',shape=policy.SHAPE,
        model_seconds_estimate=prediction['continuous_command_seconds_estimate'],
        overall_seconds_estimate=prediction['overall_seconds_estimate'],host=host,
        contract_sha256=duration.contract(manifest),model_step=family['full_step'],promotion_allowed=False,
        no_reset_reload_or_thread_change=True,forecast_method=prediction['method'],contexts=2,count_per_context=1000)

def assess(manifest,values,pins,host):
    forecast=values['forecast']
    if forecast.get('schema')==C2_SCHEMA:return assess_c2(manifest,values,pins,host,duration)
    if forecast.get('schema')!='stream27-s4-continuous-phase-forecast-v1':
        duration.need(duration.SHAPE['model_threads']==1,'non-phase legacy proofs are serial only')
        return prior_assess(manifest,values,pins,host)
    need=duration.need
    pilot,report,gate=(values[k] for k in ('pilot_manifest','pilot_report','pilot_gate'))
    need(host in ('gfn16-pilot-c4d','gfn16-azure-sim-f32')
         and report['host']==host and forecast['compatible_hosts']==[host],'actual pilot host, not borrowed timing')
    count=phase.model_threads(manifest['build'],manifest['probe']['expected_json'])
    selected=phase.source_selection(manifest)
    need(phase.source_selection(pilot)==selected,'exact same source/calendar selection in own pilot and full')
    need(count==duration.SHAPE['model_threads'] and forecast.get('model_threads',1)==count
         and report['probe']==manifest['probe']['expected_json'] and report['model_threads']==count,
         'actual pilot thread count, never borrow serial timing')
    need((forecast['generator_sha256']==PHASE_PIN or forecast['generator_sha256']==P16_PHASE_PIN and not selected.get('p8_r75',0)
          or forecast['generator_sha256']==PREVIOUS_PHASE_PIN and not selected['p16_diet'] and not selected.get('p8_r75',0)
          or forecast['generator_sha256']==LEGACY_PHASE_PIN and count==1 and not selected['p16_diet'] and not selected.get('p8_r75',0))
         and forecast['status']=='PASS_S4_measured_phase_forecast'
         and gate['status']=='PASS_expected_contracts' and gate['promotion_allowed'] is False
         and gate['manifest_sha256']==pins['pilot_manifest'] and gate['report_sha256']==pins['pilot_report']
         and report['status']=='completed_native_commands_unreviewed'
         and report['manifest_sha256']==pins['pilot_manifest'],'closed actual typed pilot/phase proof')
    need(all(forecast['short_'+name+'_sha256']==pins['pilot_'+name] for name in ('manifest','report','gate')),'raw pilot evidence bindings')
    need(manifest['build']==pilot['build']==forecast['source_model_build']
         and manifest['probe']==pilot['probe'], 'unchanged actual compiled model/probe')
    if count>1:
        execution=manifest['fixed_execution'];allocation=execution['runtime_allocation'];limits=report['limits']
        pilot_execution=pilot['fixed_execution'];same_model_execution=copy.deepcopy(execution)
        same_model_execution['runtime_allocation']['compile_workers']=pilot_execution['runtime_allocation']['compile_workers']
        need(host=='gfn16-azure-sim-f32' and manifest['cpu_profile'] in wide.SELECTIONS
             and same_model_execution==pilot_execution and len(allocation['cpus'])==8
             and len(set(map(tuple,allocation['physical_cores'])))==8 and allocation['memory_bytes']==8<<30
             and allocation['cpu_quota_percent']==800
             and limits['affinity']==allocation['cpus'] and limits['physical_cores']==allocation['physical_cores']
             and limits['memory_max_bytes']==8<<30 and limits['swap_max_bytes']==0
             and list(map(int,limits['cpu_max']))==[800000,100000]
             and report['exact_build_identity']['identity']['runtime_allocation']==pilot_execution['runtime_allocation'],
             'actual same eight-physical model allocation/8GiB/800percent; no logical-core inflation')
        validate_allocation(allocation,count)
        if allocation['compile_workers']!=2 or 'compile_allocation' in manifest:
            need(manifest.get('compile_allocation')==compilation_bound(manifest,report,allocation['compile_workers']),
                 'recomputed source-bound compiler RAM estimate')
    model_pins=forecast['source_model_pins']
    compiled=set(manifest['build']['sv_sources'])|{manifest['build']['cpp_source']}
    validator=manifest['steps'][0]['validator']
    mandatory=compiled|{validator['source'],*validator['assets'].values(),
        'rtl/tb/stream27_s4_continuous_config_v1.h','rtl/tb/native_runtime_context_v1.h',
        'rtl/tb/stream27_host_chain_full_reference_v1.h','rtl/tb/stream27_shared_reference_ntt_v1.h'}
    need(mandatory<=set(model_pins) and all(manifest['sources'].get(k)==pilot['sources'].get(k)==v
         for k,v in model_pins.items()),'compiled/harness/validator/plan source identity')
    need(len(manifest['steps'])==len(pilot['steps'])==1
         and manifest['steps'][0]['name']==pilot['steps'][0]['name']==phase.STEP
         and manifest['steps'][0]['argv']==['{exe}','1000'] and pilot['steps'][0]['argv']==['{exe}','100']
         and manifest['steps'][0].get('expected_returncode',0)==0,'one exact100→1000 normal command')
    stages=selected['stages'];boundary=selected['boundary']
    need(forecast['canonical_pipe_stages']==stages and forecast.get('boundary_inputreg',0)==boundary
         and forecast.get('p16_diet',0)==selected['p16_diet'] and forecast.get('p16_timing',0)==selected['p16_timing'] and
         forecast.get('p8_r75',0)==selected.get('p8_r75',0),
         'explicit source-bound forecast selection')
    for model,operations in ((manifest,1000),(pilot,100)):
        config=phase.normal_config(operations,selected)
        need(model['steps'][0]['validator']['config']==config and model['continuous'].get('boundary_inputreg',0)==boundary
             and model['continuous'].get('p8_r75',0)==selected.get('p8_r75',0)
             and model['continuous']['operations']==operations
             and model['continuous']['plan']==manifest['continuous']['plan'],'exact normal plan/initial state')
    rows=[r for r in report['steps'] if r['name']==phase.STEP]
    gates=[r for r in gate['steps'] if r['name']==phase.STEP]
    need(len(rows)==len(gates)==1 and rows[0]['returncode']==gates[0]['actual_returncode']==0
         and rows[0]['error'] is None and gates[0]['stdout_sha256']==rows[0]['sha256'],'successful actual phase output')
    native=gates[0]['validation']
    need(native==report['validations'][phase.STEP]==forecast['pilot_native_validation']
         and native['status']=='PASS_expected_contracts' and native['canonical_pipe_stages']==stages
         and native.get('boundary_inputreg',0)==boundary
         and native.get('p16_diet',0)==selected['p16_diet'] and native.get('p16_timing',0)==selected['p16_timing']
         and native.get('p8_r75',0)==selected.get('p8_r75',0)
         and native['base']==604832956 and native['operations']==100 and native['independent_reference_equal'] is True
         and native['candidate_root_sha256']==manifest['continuous']['plan']['candidate_root_sha256']
         and native['final_actual_sha256']==native['final_expected_sha256'],'actual typed target/full reference equality')
    observed=native['counts'];wanted=pilot['continuous']['counts_ordinary_source_projection']
    special=observed['special'];need(type(special) is int and special in (0,1),'actual special case')
    expected=dict(wanted,special=special,canonical_cycles=wanted['canonical_cycles']+special*65536,
                  candidate_cycles=wanted['candidate_cycles']+special*65536)
    need(observed==expected,'all actual100 source counters')
    full=manifest['continuous']['counts_ordinary_source_projection']
    need(full['operations']==1000 and full['doubles']==500 and full['case_id']==observed['case_id']
         and all(full[k]==1 for k in ('resets','loads','starts','readbacks'))
         and full['candidate_cycles']==102+999*selected['geometry']['interval']+selected['geometry']['carry_done']+2+(7+3*stages)*65536+4,
         'source-bound1000 cycle ledger')
    prediction=phase.predict(observed['candidate_cycles'],full['candidate_cycles']+65536,
                             native['phase_wall_ms'],rows[0]['seconds'],report['seconds'])
    need(prediction==forecast['forecast'] and prediction['fits_finite_shape'] is True,'recomputed phase forecast fits unchanged finite shape')
    return dict(status='PASS_measured_native_phase_finite_duration_only',shape=duration.SHAPE,
                model_seconds_estimate=prediction['continuous_command_seconds_estimate'],
                overall_seconds_estimate=prediction['overall_seconds_estimate'],host=host,
                contract_sha256=duration.contract(manifest),model_step=phase.STEP,promotion_allowed=False,
                no_reset_reload_or_thread_change=True,forecast_method=prediction['method'])

duration.assess=assess


def duration_for(count):
    """Same hard10800 envelope, bound to its OWN actual thread-count pilot."""
    if type(count) is not int or count not in (1,4,8):raise ValueError('explicit serial/four/eight finite shape')
    if count==1:return duration
    selected=types.ModuleType('_measured_wide_long_duration');selected.__dict__.update(duration.__dict__)
    selected.SHAPE=dict(duration.SHAPE,id=f'continuous-model-10800-thread{count}-v1',model_threads=count)
    selected.assess=types.FunctionType(assess.__code__,dict(assess.__globals__,duration=selected),assess.__name__)
    selected.validate=types.FunctionType(duration.validate.__code__,dict(duration.validate.__globals__,SHAPE=selected.SHAPE,assess=selected.assess),duration.validate.__name__)
    return selected


def parent(name, receipt=None, selected=None):
    # Package run calls this source-only parent before execute(). Wide profiles
    # are not serial pairs; use the same admitted wide selector as execute().
    if name in wide.SELECTIONS:
        return wide_parent(name,profile(name) if selected is None else selected)
    selected = profile(name)
    original = burst.parent(name) if name.startswith('azure-burst16-static8g') else base.base.parent(name)
    result = types.ModuleType('_long_namespace_parent')
    result.__dict__.update(original.__dict__, LONG_RECEIPT=receipt,
                           __file__=str(Path(__file__).resolve()))
    raw = base.base.policy.policy.host.static_module().pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
    text = base.adapted_source(raw, selected)
    anchor = 'SELF = ' + repr(base.SELF)
    if text.count(anchor) != 1: raise ValueError('unique long SELF source anchor')
    text = text.replace(anchor, 'SELF = ' + repr(SELF), 1)
    # Execute directly in the module dictionary: later host and FD updates must
    # be the very same namespace used by load_manifest()/execute().
    exec(compile(text, '[finite long namespace repair]', 'exec'), result.__dict__)
    result.PROFILES = {selected['host']: selected}
    return result


def execute(manifest_path, pin, out):
    path = Path(manifest_path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != pin:
        raise ValueError('long manifest identity')
    manifest = json.loads(path.read_text()); selected = selected_for(manifest)
    if manifest['cpu_profile'] in wide.SELECTIONS:
        count=wide.validate_threaded(manifest)
        if count not in (4,8):raise ValueError('measured wide long is four/eight only')
        policy=duration_for(count);receipt=policy.validate(manifest,Path(manifest['source_root']),selected['host'])
        def long_parent(name):
            value=wide_parent(name,selected);shape=policy.SHAPE
            raw=wide.base().source_policy().host.static_module().pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
            text=wide.adapted_source(raw,selected)
            changes=[('SELF = '+repr(wide.SELF),'SELF = '+repr(SELF)),
                ("'-j', '2', '--threads'","'-j', str(profile['compile_workers']), '--threads'"),
                ('compile_workers=2, model_threads=',"compile_workers=profile['compile_workers'], model_threads="),
                ('bounds=dict(command_seconds=1800, overall_seconds=3600, lock_wait_seconds=1800,',
                 'duration_admission=LONG_RECEIPT, bounds=dict(command_seconds=10450, ancillary_command_seconds=1800, overall_seconds=10700, outer_seconds=10800, stop_grace_seconds=15, lock_wait_seconds=1800,'),
                ("time.monotonic() - started < 3600, 'overall timeout'","time.monotonic() - started < 10700, 'overall timeout'"),
                ("time.monotonic()-begin < 1800, 'command timeout'","time.monotonic()-begin < (10450 if name == LONG_RECEIPT['model_step'] else 1800), 'command timeout'")]
            for old,new in changes:
                if text.count(old)!=1:raise ValueError('unique wide long finite source anchor')
                text=text.replace(old,new,1)
            def guarded(profile):
                if not wide.time.time()+10815<wide.DEADLINE-wide.DRAIN_LEAD_SECONDS:raise ValueError('full wide10815 before unchanged drain')
                return wide.guard_protected(profile)
            value.__dict__.update(__file__=str(Path(__file__).resolve()),LONG_RECEIPT=receipt,guard_protected=guarded)
            exec(compile(text,'[same10800 measured physical-wide long]','exec'),value.__dict__)
            value.PROFILES={selected['host']:selected}
            return value
        function=types.FunctionType(wide.execute.__code__,dict(wide.execute.__globals__,parent=long_parent,PINS=PINS,
            profile=lambda name:selected,execution_limits=execution_limits),wide.execute.__name__)
        return function(path,pin,out)
    receipt = duration.validate(manifest, Path(manifest['source_root']), selected['host'])
    host_adapter = burst.policy.policy.host if manifest['cpu_profile'].startswith('azure-burst16-static8g') else base.base.policy.policy.host
    return host_adapter.execute_with_parent(lambda name: parent(name, receipt), PINS, path, pin, out)

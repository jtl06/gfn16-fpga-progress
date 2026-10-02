"""Measured T5b/Burst23 two-thread continuous1000 duration, no execution.

This is not a generic timeout override: the exact completed100-square model,
source, probe, allocation, independent reference bridge and continuous corpus
are bound. Only this new finite shape changes; frozen serial proofs stay separate.
The envelope is an estimate with hard runtime termination, not a time guarantee.
"""
import copy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath

SHAPE = dict(id='t5b-burst23-thread2-continuous5000-v1', model_command_seconds=4500,
    ancillary_command_seconds=1800, overall_seconds=4800, outer_seconds=5000,
    stop_grace_seconds=15, lock_wait_seconds=1800, model_threads=2)
EVIDENCE = ('forecast', 'pilot_manifest', 'pilot_report', 'pilot_gate')
PILOT_PINS = dict(
    pilot_manifest='2cb61b0e75d012d1fba8077e98217630b7d9f98cb035909040d4faa90bac6ce2',
    pilot_report='05150744d22dd63afb497e2f1534fa5b7057a8f58f9e50f98fdcaf571519f7a1',
    pilot_gate='41dd39731bce0978b97be7e6929fa3df62b8df08ac2e7386989edbe9287b7f2e')
HOST, PROFILE = 'gfn16-azure-sim-f32', 'azure-burst16-static23-v1'
HEADER = 'rtl/tb/native_runtime_context_v1.h'
BENCH = 'rtl/tb/core27_t5b_soak_v1.cpp'
CORPUS = {'soak/continuous.txt':'f20f5acb34603b31b242fdec6c214fc8bf44f0d7a108d814175fa521b5e11f1a',
          'soak/continuous.json':'f9091c7fb7943295312e7206c1a11dacfd03999d898f150115909a6d73359851'}
CASE_ID = '2730e05de298ecbf5d7125acb7d6859b581b21ed8c84fb1bbfd7d3aaccd007ba'
PROBE = dict(context_threads=2, model_threads=2, expected_threads=2)
ALLOCATION = dict(cpus=[2,3], physical_cores=[[0,2],[0,3]], cpu_quota_percent=200,
                  compile_workers=2, memory_bytes=4294967296)
MARGIN, REPLAY_RESERVE = 1.75, 600


def need(ok, why):
    if not ok:
        raise ValueError('threaded duration: '+why)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def number(value):
    need(type(value) in (int,float) and math.isfinite(value) and value > 0, 'positive finite measurement')
    return value


def ticks(operations, readbacks):
    # Exact frozen bench: two reset ticks + one load-clear; n load ticks;
    # one start tick/op; reported completion cycles; n+1 ticks/readback.
    return 3 + 65536 + operations + 41674 + (operations-1)*28826 + readbacks*(65536+1)


def model_pins(pilot):
    pins=pilot['budget_source_members']
    need(len(pins)==59, 'exact original59-member pilot role')
    return {name:pin for name,pin in pins.items() if name not in ('soak/chunk-00.txt','soak/chunk-00.json')}


def forecast(pilot, report, gate):
    """Scalar metadata/timing only; no role import, GMP or reference generation."""
    step=next(row for row in report['steps'] if row['name']=='soak-normal')
    upper=number(step['seconds'])/ticks(100,2)
    overhead=max(0,number(report['seconds'])-step['seconds'])*MARGIN
    return copy.deepcopy(dict(schema='T5b-thread2-continuous-forecast-v1', status='PASS_measured_forecast_estimate_only',
        pilot_pins=PILOT_PINS, host=HOST, profile=PROFILE, source_model_build=pilot['build'],
        source_model_pins=model_pins(pilot), model_step='soak-normal', measured_operations=100,
        measured_readbacks=2, measured_ticks=ticks(100,2), model_seconds_per_tick_upper_observed=upper,
        continuous_operations=1000, continuous_readbacks=11, continuous_ticks=ticks(1000,11),
        margin=MARGIN, continuous_command_seconds_estimate=upper*ticks(1000,11)*MARGIN,
        nonmodel_seconds_estimate=overhead, reference_replay_reserve_seconds=REPLAY_RESERVE,
        overall_seconds_estimate=upper*ticks(1000,11)*MARGIN+overhead+REPLAY_RESERVE,
        continuous_corpus_sha256=CORPUS,
        scope='One measured100-square sample plus1.75 margin and600s reference reserve; not guaranteed or native1000 evidence.',
        promotion_allowed=False, higher_thread_admission=False))


def contract(manifest):
    names=set(manifest['build']['sv_sources'])|{manifest['build']['cpp_source'],HEADER}
    for step in manifest['steps']:
        validator=step['validator']; names.add(validator['source']);names.update(validator['assets'].values())
        names.update(arg[len('{root}/'):] for arg in step['argv'] if arg.startswith('{root}/'))
    return digest(dict(build=manifest['build'],probe=manifest['probe'],steps=manifest['steps'],
                       pins={name:manifest['sources'][name] for name in sorted(names)}))


def assess(manifest, values, raw_pins, host):
    need(set(values)==set(raw_pins)==set(EVIDENCE), 'four closed evidence inputs')
    need(host==manifest['host']==HOST and manifest['cpu_profile']==PROFILE, 'exact already-qualified physical pair/host')
    need(all(raw_pins[name]==pin for name,pin in PILOT_PINS.items()), 'actual completed100 pilot raw identities')
    f,pilot,report,gate=(values[name] for name in EVIDENCE)
    need(gate['status']=='PASS_expected_contracts' and gate['promotion_allowed'] is False
         and gate['manifest_sha256']==raw_pins['pilot_manifest'] and gate['report_sha256']==raw_pins['pilot_report'],
         'actual typed pilot PASS/raw bindings')
    need(report['status']=='completed_native_commands_unreviewed' and report['host']==HOST
         and report['manifest_sha256']==raw_pins['pilot_manifest'], 'completed same-host pilot')
    need(manifest['build']==pilot['build'] and manifest['build']['parameters']==dict(AW=16,NTT_LANES=64)
         and manifest['build']['cpp_source']==BENCH and type(manifest['build']['runtime_threads']) is int
         and manifest['build']['runtime_threads']==2, 'identical exact two-thread AW16 model')
    need(manifest['probe']==pilot['probe'] and report['probe']==manifest['probe']['expected_json']==PROBE
         and all(type(v) is int for v in manifest['probe']['expected_json'].values()), 'exact typed two-thread probe')
    need(report['model_threads']==report['context_threads']==report['compile_workers']==2
         and report['exact_build_identity']['identity']['runtime_allocation']==ALLOCATION,
         'actual distinct physical cores/compiler/memory allocation')
    limits=report['limits']
    need(limits['affinity']==[2,3] and limits['physical_cores']==[[0,2],[0,3]]
         and limits['memory_max_bytes']==4294967296 and limits['swap_max_bytes']==0
         and limits['cpu_max']==['200000','100000'], 'actual pair/cgroup limits')
    validation=report['validations']['soak-normal']
    need(validation['operations']==100 and validation['cycles']==2895448 and validation['readbacks']==2
         and validation['independent_gmpy2_boundary_replay'] is True
         and validation['native_qualification_allowed'] is True and validation['case_id']==CASE_ID,
         'actual100 exact reference/cycle/boundary replay')
    need(digest(f)==digest(forecast(pilot,report,gate)), 'recomputed closed typed scalar forecast')
    need(all(manifest['sources'].get(name)==pin for name,pin in f['source_model_pins'].items()),
         'unchanged compiled/harness/context/reference/provenance lineage')
    need(all(manifest['sources'].get(name)==pin for name,pin in CORPUS.items()), 'exact qualified continuous1000 corpus')
    need(manifest['soak']['case_id']==CASE_ID and manifest['soak']['segment']=='continuous'
         and manifest['soak']['requested_gate']=='uninterrupted_1000_square_rtl', 'separate continuous role, not chunk aggregation')
    need(len(manifest['steps'])==1, 'one uninterrupted model command')
    step=manifest['steps'][0];old=pilot['steps'][0]
    need(step['name']==old['name']=='soak-normal' and step['argv']==['{exe}','{root}/soak/continuous.txt']
         and type(step.get('expected_returncode',0)) is int and step.get('expected_returncode',0)==0,
         'normal one-context continuous executable contract')
    validator=dict(old['validator']);validator['assets']=dict(validator['assets'],oracle='soak/continuous.json')
    need(step['validator']==validator, 'unchanged validator/reference bridge except exact corpus')
    need(f['continuous_command_seconds_estimate']<=SHAPE['model_command_seconds']
         and f['overall_seconds_estimate']<=SHAPE['overall_seconds'], 'measured envelope fits finite new shape')
    return dict(status='PASS_measured_two_thread_finite_duration_only',shape=copy.deepcopy(SHAPE),host=HOST,profile=PROFILE,
        contract_sha256=contract(manifest),model_step='soak-normal',forecast=f,
        promotion_allowed=False, native_1000_evidence=False, higher_thread_admission=False,
        no_reset_reload_or_thread_change=True)


def validate(manifest, root, host):
    value=manifest['runtime_duration']
    need(set(value)=={'shape','contract_sha256','evidence'}
         and digest(value['shape'])==digest(SHAPE) and value['contract_sha256']==contract(manifest), 'exact typed closed shape/role contract')
    need(set(value['evidence'])==set(EVIDENCE), 'closed duration evidence set')
    values,pins={},{}
    for key,item in value['evidence'].items():
        name=item['path'];need(type(name) is str and name==str(PurePosixPath(name))
            and not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts, 'contained relative evidence')
        path=Path(root)/name
        need(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(Path(root).resolve()), 'regular contained evidence')
        raw=path.read_bytes();pin=hashlib.sha256(raw).hexdigest()
        need(pin==item['sha256']==manifest['sources'][name], 'source-closed duration evidence')
        values[key],pins[key]=json.loads(raw),pin
    return assess(manifest,values,pins,host)

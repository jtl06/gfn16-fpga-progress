"""Source-only R14 count1000 and own measured-pilot forecast. No dispatch."""
import copy
import hashlib
import json
import math
from pathlib import Path
from fpga.reference import stream27_r14_host_offload_long_v1 as own

ROOT=own.ROOT
SELF='reference/stream27_r14_host_offload_continuous_v1.py'
BASE=own.BASE
PILOT=BASE/'own100-v1'
PILOT_ID=own.ID
ID='s4-r14-host-offload-continuous1000-q1-v1'
SHAPE=dict(model_command_seconds=10450,overall_seconds=10700,outer_seconds=10800,stop_grace_seconds=15)
def need(ok,why):
    if not ok:raise ValueError('R14_CONTINUOUS_'+why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def role():
    old=json.loads((PILOT/'manifest.json').read_bytes());m,files=own.role(1000)
    prior={n:(PILOT/'source/fpga'/n).read_bytes() for n in old['sources']}
    need(set(prior)==set(files) and [n for n in prior if prior[n]!=files[n]]==[own.HEADER],'ONLY_COUNT_BITS_HEADER')
    need(old['build']==m['build'] and len(m['build']['sv_sources'])==66,'EXACT_ON66_CPP_BUILD')
    files[SELF]=(ROOT/SELF).read_bytes();m['sources'][SELF]=sha(files[SELF]);m['rtl_readiness']['candidate_id']=ID
    m['r14_own_long'].update(pilot_id=PILOT_ID,allowed_compiled_delta=[own.HEADER],
        old_header_sha256=old['sources'][own.HEADER],new_header_sha256=m['sources'][own.HEADER],
        forecast_pending=True,own_runtime_unmeasured=True)
    return m,files
def predict(command_seconds,overall_seconds):
    need(all(type(x) in (int,float) and math.isfinite(x) and x>0 for x in (command_seconds,overall_seconds)) and overall_seconds>=command_seconds,'ACTUAL_FINITE_TIMES')
    command=command_seconds*10*1.75;ancillary=(overall_seconds-command_seconds)*1.75;total=command+ancillary+600
    return dict(method='own_ON_only_command_operation_ratio_including_reference_host_staging_final',
        measured_command_seconds=command_seconds,measured_overall_seconds=overall_seconds,operation_ratio=10,margin=1.75,
        additional_replay_and_uncertainty_reserve_seconds=600,continuous_command_seconds_estimate=command,
        nonmodel_seconds_estimate=ancillary,overall_seconds_estimate=total,finite_shape=SHAPE,
        fits_finite_shape=command<=SHAPE['model_command_seconds'] and total<=SHAPE['overall_seconds'])
def forecast(manifest):
    root=ROOT/'queue/evidence'/PILOT_ID;gatepath=root/'gate-receipt.json'
    gate=json.loads(gatepath.read_bytes());need(gate['status']=='PASS_expected_contracts' and gate['id']==PILOT_ID,'OWN_TYPED_PILOT')
    matched=[p for p in root.glob('attempt-*/collected/output/native/report.json') if sha(p.read_bytes())==gate['report_sha256']]
    need(len(matched)==1,'ONE_ACTUAL_REPORT');reportpath=matched[0];report=json.loads(reportpath.read_bytes())
    approvedpath=reportpath.parent/'approved-manifest.json';approved=json.loads(approvedpath.read_bytes())
    need(sha(approvedpath.read_bytes())==gate['manifest_sha256']==report['manifest_sha256'] and report['host']=='gfn16-pilot-c4d' and report['model_threads']==1,'OWN_APPROVED_ALLOCATION')
    name='r14-host-offload-own100-continuous';steps=[s for s in report['steps'] if s['name']==name];checks=[s for s in gate['steps'] if s['name']==name]
    need(len(steps)==len(checks)==1 and steps[0]['returncode']==checks[0]['actual_returncode']==0 and not steps[0]['error'],'OWN_STEP')
    validation=checks[0]['validation'];need(validation['status']=='PASS_expected_contracts' and validation['measurements']['count']==100,'OWN100')
    sources=set(manifest['build']['sv_sources'])|{own.CPP,'rtl/tb/native_runtime_context_v1.h','rtl/tb/stream27_host_offload_host_v2.h','rtl/tb/stream27_host_chain_full_reference_v1.h','rtl/tb/stream27_shared_reference_ntt_v1.h'}
    need(all(manifest['sources'][n]==approved['sources'][n] for n in sources),'EXACT_CPP_RTL_REFERENCE_HOST')
    return dict(schema='stream27-r14-own-measured-continuous-forecast-v1',status='PASS_R14_own100_measured_forecast',
        generator=SELF,generator_sha256=sha((ROOT/SELF).read_bytes()),compatible_hosts=[report['host']],model_threads=1,
        short_manifest_sha256=gate['manifest_sha256'],short_report_sha256=gate['report_sha256'],short_gate_sha256=sha(gatepath.read_bytes()),
        source_model_build=manifest['build'],source_model_pins={n:manifest['sources'][n] for n in sorted(sources)},
        allowed_compiled_delta=dict(path=own.HEADER,pilot_sha256=approved['sources'][own.HEADER],full_sha256=manifest['sources'][own.HEADER]),
        pilot_native_validation=validation,full_config=own.config(1000),forecast=predict(steps[0]['seconds'],report['seconds']),
        FPGA_throughput_or_clock_claim=False,parent_forecast_inherited=False)
def prepare_source():
    out=BASE/'continuous1000-source-v1';need(not out.exists(),'FRESH_SOURCE');m,files=role();source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    m['source_root']=str(source);own.dump(out/'manifest.json',m)
    return dict(id=ID,manifest=str(out/'manifest.json'),status='SOURCE_ONLY_NOT_BOUND_NOT_SUBMITTED',forecast_requires=PILOT_ID)
if __name__=='__main__':print(json.dumps(prepare_source(),indent=2))

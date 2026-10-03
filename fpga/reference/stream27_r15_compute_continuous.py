"""Own AzureFIT R15 measured serial100 -> finite1000 source/forecast only.

Four scalar functions match existing long assessment mechanics. Actual new
source/allocated pilot is mandatory; no GCP/SIM/FIELD100 duration or outcome.
"""
import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import re
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_compute_continuous.py'
BASE=ROOT/'results/throughput-20260929/trackS-r15-compute-ownlong-v1'
PILOT=BASE/'own100-source-v1'
FULL=BASE/'continuous1000-source-v1'
PILOT_PIN='75ac12da932dbea9daf5a620ae8a497348d27dc4b627e4515692f245d94c610f'
PILOT_ID='s4-p16-c2-r15-compute-own100-serial-q1-v1'
PILOT_STEP='normal-full-r15-compute-own100-percontext'
PILOT_VALIDATOR='reference/stream27_r15_compute_pilot_native.py'
PILOT_EVIDENCE=ROOT/'queue/evidence'/PILOT_ID
PILOT_MANIFEST=PILOT_EVIDENCE/'attempt-0/collected/output/native/approved-manifest.json'
PILOT_REPORT=PILOT_MANIFEST.with_name('report.json')
PILOT_GATE=PILOT_EVIDENCE/'gate-receipt.json'
HEADER='rtl/tb/s4_p16_two_context_full_config.h'
CPP='rtl/tb/stream27_p16_two_context_protected_field100_pilot.cpp'
STEP='normal-full-r15-compute-own1000-percontext'
BASES=[604832956,999999937]
COUNT=1000
THREADS=1
SCHEMA='stream27-p16-c2-measured-continuous-forecast-v1'
SHAPE=dict(model_command_seconds=10450,overall_seconds=10700,outer_seconds=10800,stop_grace_seconds=15)


def bits(count=COUNT):
    need(type(count) is int and count in (100,1000),'R15_CONTINUOUS_FINITE_COUNT')
    result=[]
    for ctx,seed in enumerate((0x1732f5a9,0x7b28c361)):
        row,state=[ctx],seed
        for _ in range(1,count):
            state^=(state<<13)&0xffffffff;state^=state>>17;state^=(state<<5)&0xffffffff
            row.append(state&1)
        result.append(row)
    return result


def config():
    return dict(aw=16,p=16,contexts=2,bases=BASES,count=COUNT,threads=THREADS,doubles=sum(map(sum,bits())),
      interval=8461,carry_done=12558,joint_first_edges=[204,4434],publication_fence_edges=1,lean_production=False,
      r15_flags=dict(FIXED_SCHEDULE=1,LEAN_BUILD=1,PROGRESS_WATCHDOG=1,STORAGE_TO_RAM=1,DIRECT_COLD=0,PCIE_SHELL=0),
      allocation_family='AzureFIT-serial1-2physical-8GiB-j2')


def header(pilot_header):
    text=pilot_header.decode()
    need(text.count('COUNT=100,INTERVAL=8461')==1 and
         'MAX_EDGES=COUNT*uint64_t(INTERVAL)+3*11ull*N+100000;' in text,'R15_CONTINUOUS_PILOT_HEADER')
    match=re.search(r'BITS\[2\]\[COUNT\]=\{(.*)\};\n\Z',text)
    need(match is not None,'R15_CONTINUOUS_BITS_EXTENT')
    expected=','.join('{'+','.join(map(str,row))+'}' for row in bits(100))
    need(match.group(1)==expected,'R15_CONTINUOUS_DETERMINISTIC_PREFIX')
    value=text[:match.start(1)]+','.join('{'+','.join(map(str,row))+'}' for row in bits())+text[match.end(1):]
    return value.replace('COUNT=100,INTERVAL=8461','COUNT=1000,INTERVAL=8461',1).encode()


def predict(command_seconds,overall_seconds,margin=1.75,reserve_seconds=600):
    need(all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in
         (command_seconds,overall_seconds,margin,reserve_seconds)),'R15_CONTINUOUS_FINITE_FORECAST')
    need(overall_seconds>=command_seconds and margin>=1.75 and reserve_seconds>=600,'R15_CONTINUOUS_FIXED_MARGIN')
    command=command_seconds*10*margin;ancillary=(overall_seconds-command_seconds)*margin
    overall=command+ancillary+reserve_seconds
    return dict(method='own_C2_command_operation_ratio_with_fixed_overhead_and_reference_included',
      pilot_count_per_context=100,continuous_count_per_context=1000,operation_ratio=10,margin=margin,
      measured_command_seconds=command_seconds,measured_overall_seconds=overall_seconds,
      continuous_command_seconds_estimate=command,nonmodel_seconds_estimate=ancillary,
      additional_replay_and_uncertainty_reserve_seconds=reserve_seconds,overall_seconds_estimate=overall,
      finite_shape=SHAPE,fits_finite_shape=command<=SHAPE['model_command_seconds'] and overall<=SHAPE['overall_seconds'],
      scope='Own AzureFIT R15 source/allocation planning only; lean build, host GL assumed (unimplemented). No1000 outcome, clock/throughput, OOM, protected-fault/PCIe/CDC/GL or old provider time credit.')


def role():
    raw=(PILOT/'manifest.json').read_bytes();need(sha(raw)==PILOT_PIN,'R15_CONTINUOUS_OWN_PILOT_SOURCE')
    p=json.loads(raw);m=json.loads((FULL/'manifest.json').read_bytes())
    f={n:(FULL/'source/fpga'/n).read_bytes() for n in m['sources']}
    need(all(sha(f[n])==pin for n,pin in m['sources'].items()),'R15_CONTINUOUS_CLOSED_FULL_SOURCE')
    previous=(PILOT/'source/fpga'/HEADER).read_bytes()
    need(f[HEADER]==header(previous) and m['steps'][0]['name']==STEP and
         m['steps'][0]['validator']==dict(source=PILOT_VALIDATOR,function='validate',config=config(),assets={}),
         'R15_CONTINUOUS_ONLY_HEADER_CONFIG_DELTA')
    compiled=set(m['build']['sv_sources'])|{CPP,'rtl/tb/native_runtime_context_v1.h',
      'rtl/tb/stream27_host_chain_full_reference_v1.h','rtl/tb/stream27_shared_reference_ntt_v1.h'}
    need(len(m['build']['sv_sources'])==61 and m['build']==p['build'] and
         all(m['sources'][n]==p['sources'][n] for n in compiled),'R15_CONTINUOUS_ALL_COMPILED_BYTES_UNCHANGED')
    f[SELF]=(ROOT/SELF).read_bytes();m['sources']={n:sha(v) for n,v in f.items()}
    m['r15_compute']['own_long'].update(actual_Azure_pilot_measurement_pending=False,
      measured_source_allocation_required=True,allowed_compiled_delta=[HEADER],forecaster_sha256=sha(f[SELF]))
    m['source_root']=m['output_parent']='UNBOUND'
    return m,f


def forecast(m):
    p,r,g=[json.loads(path.read_bytes()) for path in (PILOT_MANIFEST,PILOT_REPORT,PILOT_GATE)]
    pins={k:sha(path.read_bytes()) for k,path in (('pilot_manifest',PILOT_MANIFEST),('pilot_report',PILOT_REPORT),('pilot_gate',PILOT_GATE))}
    need(g['status']=='PASS_expected_contracts' and g['manifest_sha256']==pins['pilot_manifest']==r['manifest_sha256'] and
         g['report_sha256']==pins['pilot_report'] and r['host']=='gfn16-azure-f16' and r['model_threads']==1,
         'R15_CONTINUOUS_ACTUAL_AZURE_PILOT')
    rows=[v for v in r['steps'] if v['name']==PILOT_STEP];gates=[v for v in g['steps'] if v['name']==PILOT_STEP]
    need(len(rows)==len(gates)==1 and rows[0]['returncode']==gates[0]['actual_returncode']==0 and
         rows[0]['error'] is None and rows[0]['command'][:3]==['/usr/bin/taskset','-c','12,13'],
         'R15_CONTINUOUS_ACTUAL_SINGLE_PAIR_COMMAND')
    v=gates[0]['validation'];measure=v['measurements']
    need(measure['count_per_context']==100 and measure['interval']==8461 and
         v['r15_flags']==config()['r15_flags'] and v['allocation_family']==config()['allocation_family'],
         'R15_CONTINUOUS_SOURCE_OWN_TYPED_COUNT')
    names=set(m['build']['sv_sources'])|{CPP,'rtl/tb/native_runtime_context_v1.h',
      'rtl/tb/stream27_host_chain_full_reference_v1.h','rtl/tb/stream27_shared_reference_ntt_v1.h'}
    need(m['build']==p['build'] and all(m['sources'][n]==p['sources'][n] for n in names),
         'R15_CONTINUOUS_ACTUAL_SOURCE_MATCH')
    return dict(schema=SCHEMA,status='PASS_C2_own100_measured_continuous_forecast',generator=SELF,
      generator_sha256=sha((ROOT/SELF).read_bytes()),compatible_hosts=[r['host']],model_threads=1,
      short_manifest_sha256=pins['pilot_manifest'],short_report_sha256=pins['pilot_report'],short_gate_sha256=pins['pilot_gate'],
      source_model_build=m['build'],source_model_pins={n:m['sources'][n] for n in sorted(names)},
      pilot_native_validation=v,allowed_compiled_delta=dict(path=HEADER,pilot_sha256=p['sources'][HEADER],full_sha256=m['sources'][HEADER]),
      full_config=config(),forecast=predict(rows[0]['seconds'],r['seconds']))


def prepare(output):
    out=Path(output).resolve();need(out.is_relative_to(BASE) and not out.exists(),'R15_CONTINUOUS_FRESH_MEASURED_ROLE')
    m,f=role();value=forecast(m);need(value['forecast']['fits_finite_shape'],'R15_CONTINUOUS_SHAPE')
    source=out/'source/fpga';source.mkdir(parents=True)
    for n,v in f.items():
        path=source/n;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(v)
    m['source_root']=str(source);dump(out/'manifest.json',m);dump(out/'forecast.json',value)
    dump(out/'production-bundle.json',json.loads((FULL/'production-bundle.json').read_bytes()))
    return dict(manifest=str(out/'manifest.json'),source_root=str(source),forecast=str(out/'forecast.json'),
      forecast_sha256=sha((out/'forecast.json').read_bytes()),command_estimate=value['forecast']['continuous_command_seconds_estimate'],
      overall_estimate=value['forecast']['overall_seconds_estimate'],status='OWN_AZURE_PILOT_BOUND_NOT_SUBMITTED')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output),indent=2))

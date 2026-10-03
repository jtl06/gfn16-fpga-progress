"""Own R15 compute serial100 and source1000 role, AzureFIT allocation only.

Unchanged deterministic descriptor/reference assertions are reused as scalar
contracts only. No FIELD100/GCP/old lean runtime or native evidence is borrowed.
"""
import argparse
import json
from pathlib import Path
from fpga.reference import stream27_protected_field100_long_native as scalar
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump,runtime_before_model

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_compute_pilot_native.py'
SCALAR='reference/stream27_protected_field100_long_native.py'
SCALAR_PIN='aa15e4c9c02333d3f661c8135a69a979e2283a6469e6cdd0f59dbe04dba3d000'
CAPTURE=ROOT/'results/throughput-20260929/trackS-r15-compute-native-v1/full-normal-v2'
CAPTURE_PIN='022cd0ccceee77227e38a13f50584262da747ab60f187a459e265dbf711422d9'
RECIPE=ROOT/'results/throughput-20260929/trackS-c2-protected-field100-ownlong-v1/own100-serial-v1'
RECIPE_PIN='5ff23f61e9cda73e47f91c09e253d362e4c03581d3dcdfe8b65e556d9cd2aa91'
CPP='rtl/tb/stream27_p16_two_context_protected_field100_pilot.cpp'
CPP_PIN='150b5ba4ca07c23babfc64bc2667791626412e98300a6b21476cdf964958efb0'
HEADER='rtl/tb/s4_p16_two_context_full_config.h'
HEADER_PIN='0218e598dfd04b12df1d652b8e9fed2f3101602d38f465dcaba37f435ec8bb04'
FLAGS=dict(FIXED_SCHEDULE=1,LEAN_BUILD=1,PROGRESS_WATCHDOG=1,STORAGE_TO_RAM=1,DIRECT_COLD=0,PCIE_SHELL=0)
FULL_ID='s4-p16-c2-r15-compute-full-normal-q1-v1'
PILOT_ID='s4-p16-c2-r15-compute-own100-serial-q1-v1'


def config(count=100):
    need(type(count) is int and count in (100,1000),'R15_PILOT_FINITE_COUNT')
    return dict(scalar.config(count,1),r15_flags=FLAGS,allocation_family='AzureFIT-serial1-2physical-8GiB-j2')


def validate(stdout,stderr,rc,config,assets):
    count=config.get('count')
    need(config==globals()['config'](count) and assets=={},'R15_PILOT_OWN_CONFIG')
    value=scalar.validate(stdout,stderr,rc,scalar.config(count,1),{})
    value.update(scope='Own R15 compute continuous/source allocation only; lean build; host GL assumed (unimplemented). No FIELD100/GCP/native/clock/fault/runtime inheritance.',
                 r15_flags=FLAGS,allocation_family=config['allocation_family'],promotion_allowed=False)
    return value


def role(count=100):
    ownconfig=config(count)
    need(sha((ROOT/SCALAR).read_bytes())==SCALAR_PIN,'R15_PILOT_SCALAR_PIN')
    raw=(CAPTURE/'manifest.json').read_bytes();need(sha(raw)==CAPTURE_PIN,'R15_PILOT_FROZEN_OWN_FULL')
    manifest=json.loads(raw);bundle=json.loads((CAPTURE/'production-bundle.json').read_bytes())
    need(len(bundle['files'])==60 and bundle['r15_all']['flags']==FLAGS and
         manifest['build']['parameters']==dict(bundle['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),
         'R15_PILOT_OWN_SOURCE_AND_COMPILED_PARAMS')
    files={n:(CAPTURE/'source/fpga'/n).read_bytes() for n in manifest['sources']}
    need(all(sha(files[n])==pin for n,pin in manifest['sources'].items()),'R15_PILOT_OWN_INPUT_CLOSURE')
    need(sha((RECIPE/'manifest.json').read_bytes())==RECIPE_PIN,'R15_PILOT_CPP_RECIPE')
    cpp=(RECIPE/'source/fpga'/CPP).read_bytes();header=(RECIPE/'source/fpga'/HEADER).read_bytes()
    need(sha(cpp)==CPP_PIN and sha(header)==HEADER_PIN,'R15_PILOT_IMMUTABLE_CPP_HEADER')
    runtime_before_model(cpp.decode());text=header.decode()
    if count==1000:
        need(text.count('COUNT=100,INTERVAL')==1,'R15_PILOT_HEADER_COUNT')
        text=text.replace('COUNT=100,INTERVAL','COUNT=1000,INTERVAL',1)
        text=text[:text.index('BITS[2][COUNT]=')]+'BITS[2][COUNT]={'+','.join(
            '{'+','.join(map(str,row))+'}' for row in scalar.bits(count))+'};\n'
    files.update({CPP:cpp,HEADER:text.encode(),SELF:(ROOT/SELF).read_bytes(),SCALAR:(ROOT/SCALAR).read_bytes()})
    manifest['build'].update(cpp_source=CPP,runtime_threads=1)
    manifest['steps']=[dict(name=f'normal-full-r15-compute-own{count}-percontext',argv=['{exe}'],
      expected_returncode=0,validator=dict(source=SELF,function='validate',config=ownconfig,assets={}))]
    manifest['r15_compute']['own_long']=dict(count_per_context=count,threads=1,normal_dependency=FULL_ID,
      own_calendar=scalar.calendar(bundle['geometry'],count),scalar_calendar_reuse_only=True,
      descriptors=2*(count-1),initial_resets=1,initial_load_words=131072,copy_edges=65540,
      no_midchain_reset_reload=True,actual_Azure_pilot_measurement_pending=True,forecast_inherited=False,
      host_GL_implemented=False,protected_fault_credit=False)
    manifest['sources']={n:sha(raw) for n,raw in files.items()}
    manifest['source_root']=manifest['output_parent']='UNBOUND'
    manifest['rtl_readiness']['candidate_id']=f's4-p16-c2-r15-compute-own{count}-v1'
    return manifest,files,bundle


def freeze(count=100):
    manifest,files,bundle=role(count)
    out=ROOT/'results/throughput-20260929/trackS-r15-compute-ownlong-v1'/('own100-source-v1' if count==100 else 'continuous1000-source-v1')
    need(not out.exists(),'R15_PILOT_FRESH_OUTPUT');source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    manifest['source_root']=str(source);dump(out/'manifest.json',manifest);dump(out/'production-bundle.json',bundle)
    return dict(manifest=str(out/'manifest.json'),status='SOURCE_NOT_NATIVE_NO_FORECAST',count=count)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--count',type=int,choices=(100,1000),default=100);args=p.parse_args()
    print(json.dumps(freeze(args.count),indent=2))

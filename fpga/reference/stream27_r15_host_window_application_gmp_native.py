"""Private graph-only copy of the qualified application70 AW8 capture.

No generator or arithmetic re-emission, native run, or vendor HIP model.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'results/throughput-20260929/trackS-r15-shell-application-native-v4/aw8-normal'
PARENT_PIN='3248784f38814d8200a8a6bafe4ee9188b7ddd29f29193b95995c95918e6ef8d'
SELF='reference/stream27_r15_host_window_application_gmp_native.py'
CPP='rtl/tb/stream27_r15_host_window_application_gmp.cpp'
VALIDATOR='reference/stream27_r15_host_window_application_gmp_output.py'
ORACLE='reference/stream27_r15_host_window_gmp_output.py'
INVENTORY='results/throughput-20261003/r15-azure-gmp-link-observation-v1.json'
INVENTORY_PIN='25bda4f71841fa05e1946e92c88a85216c9f68903a6083fbbb2d1d75a362b27d'
BASE=ROOT/'results/throughput-20261003/r15-host-window-application-gmp-native-v1'


def sha(raw):return hashlib.sha256(raw).hexdigest()
def need(ok,tag):
    if not ok:raise ValueError('R15_APP_WINDOW_'+tag)


def identity(m):
    value={key:m[key] for key in ('build','probe','steps')};value['sources']=m['sources']
    return sha(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode())


def role(mode='normal'):
    from .stream27_r15_host_window_application_gmp_output import expected
    need(mode in ('normal','faults'),'MODE')
    raw=(PARENT/'manifest.json').read_bytes();need(sha(raw)==PARENT_PIN,'IMMUTABLE_PARENT')
    old=json.loads(raw);bundle=json.loads((PARENT/'production-bundle.json').read_bytes())
    files={name:(PARENT/'source/fpga'/name).read_bytes() for name in old['sources']}
    need(all(sha(files[name])==pin for name,pin in old['sources'].items()),'PARENT_CLOSURE')
    need(len(bundle['files'])==70 and all(files['rtl/'+n]==t.encode() for n,t in bundle['files'].items()),
         'ALL70_PRODUCTION_LITERAL')
    m={k:old[k] for k in ('schema','status','source_root','output_parent','build','probe',
                          'promotion_allowed','rtl_readiness','test_role')}
    for name in (SELF,CPP,VALIDATOR,ORACLE,INVENTORY):files[name]=(ROOT/name).read_bytes()
    need(sha(files[INVENTORY])==INVENTORY_PIN,'INVENTORY')
    cpp=files[CPP].decode()
    need(cpp.count('DUT d(&context)')==1 and
         cpp.index('gfn16_runtime::configure(context,argc,argv)')<cpp.index('DUT d(&context)'),
         'RUNTIME_BEFORE_ONLY_DUT')
    m['build'].update(cpp_source=CPP,ldflags=['-lgmpxx','-lgmp'])
    normal=dict(name='application-host-window-normal',argv=['{exe}'],expected_returncode=0,
                expected_stdout=expected(),expected_stderr='')
    m['steps']=[normal] if mode=='normal' else [
        dict(name='application-host-corrupt-rollback',argv=['{exe}','--host-corrupt-rollback'],
             expected_returncode=0,expected_stdout=expected('rollback'),expected_stderr=''),
        dict(name='application-host-oracle-negative',argv=['{exe}','--oracle-negative'],
             expected_returncode=1,expected_stdout=expected(),
             expected_stderr='R15_APP_WINDOW_SIGNED96_ORACLE_WITNESS\n')]
    m['sources']={n:sha(v) for n,v in files.items()}
    m['metadata']=dict(r15_native_gmp=dict(schema='r15-application70-gmp-link-v1',
        inventory=dict(path=INVENTORY,sha256=INVENTORY_PIN),fixture_sha256=identity(m)))
    m['r15_application_host_window']=dict(parent_manifest_sha256=PARENT_PIN,
        production_top=bundle['top'],production_generated_sha256=bundle['generated_sha256'],
        parent_gate='s4-p16-c2-r15-shell-application-aw8-normal-q1-v5',mode=mode,
        actual_application_core_CDC_required=True,actual_host_GMP_required=True,
        fresh_prospective_owner_every_BEGIN=True,latest_global_BEGIN_lease_before_START=True,
        raw_COMMIT_then_admitted_busy_generation=True,PROFILE_internal_no_ACK=True,
        all_owned_A32_signed96_then_final_fence=True,global_ordinal_separate=True,
        vendor_HIP=False,VFIO=False,board=False,hardware_reset_delivery=False,
        arbitrary_in_job_checkpoints=False,full_N_PRP=False,promotion=False)
    m['test_role']='normal' if mode=='normal' else 'deliberate_fault'
    m['source_root']=m['output_parent']='UNBOUND'
    m['rtl_readiness']['candidate_id']='r15-application-host-window-'+mode
    return m,files,bundle


def freeze(mode='normal'):
    m,files,bundle=role(mode);out=BASE/mode;need(not out.exists(),'FRESH_OUTPUT')
    source=out/'source/fpga';source.mkdir(parents=True)
    m['r15_application_host_window']['source_freeze_utc']=datetime.now(timezone.utc).isoformat()
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    m['source_root']=str(source)
    for name,value in (('manifest.json',m),('production-bundle.json',bundle)):
        with (out/name).open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    return dict(manifest=str(out/'manifest.json'),status='SOURCE_ONLY_NOT_NATIVE',
                fixture_sha256=m['metadata']['r15_native_gmp']['fixture_sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=('normal','faults'),default='normal')
    print(json.dumps(freeze(p.parse_args().mode),sort_keys=True))

"""Private source-bound DIRECT65/GMP window fixture, normal first.

No generator, native execution, or full-N math occurs during preparation.
Core-clock lease/ACK/reset simulation is NOT a PCIe/CDC/VFIO endpoint.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_host_window_gmp_native.py'
CPP='rtl/tb/stream27_r15_host_window_gmp.cpp'
VALIDATOR='reference/stream27_r15_host_window_gmp_output.py'
PARENT=ROOT/'results/throughput-20260929/trackS-r15-direct-compute-native-v1/aw8-normal-v2'
PARENT_MANIFEST='821a7bacd206c7bf485fdeb75fd8d8f32188ae4b0e0f718bede104c41ad25f3b'
PARENT_BUNDLE='7c90d8e0a4c8bf4377068b716feeef52455fb668cf06e5de13f409d36eb9c6ce'
INVENTORY='results/throughput-20261003/r15-azure-gmp-link-observation-v1.json'
INVENTORY_PIN='25bda4f71841fa05e1946e92c88a85216c9f68903a6083fbbb2d1d75a362b27d'
BASE=ROOT/'results/throughput-20261003/r15-host-window-gmp-native-v1'


def sha(raw):return hashlib.sha256(raw).hexdigest()
def need(ok,tag):
    if not ok:raise ValueError('R15_HOST_WINDOW_'+tag)


def role(mode='normal'):
    from fpga.reference.stream27_r15_host_window_gmp_output import expected
    from fpga.tools.native_class_package_v4 import source_identity
    need(mode in ('normal','faults'),'MODE')
    mraw=(PARENT/'manifest.json').read_bytes();braw=(PARENT/'production-bundle.json').read_bytes()
    need((sha(mraw),sha(braw))==(PARENT_MANIFEST,PARENT_BUNDLE),'FROZEN_DIRECT65_CAPTURE')
    original,bundle=json.loads(mraw),json.loads(braw)
    manifest={k:original[k] for k in ('schema','status','source_root','output_parent',
        'build','probe','promotion_allowed','rtl_readiness','test_role')}
    files={name:(PARENT/'source/fpga'/name).read_bytes() for name in original['sources']}
    need(all(sha(files[n])==pin for n,pin in original['sources'].items()),'EXACT_PARENT_CLOSURE')
    need(len(bundle['files'])==65 and all(files['rtl/'+n]==t.encode() for n,t in bundle['files'].items()),
         'ALL65_LITERAL')
    need(bundle['geometry']['n']==256 and bundle['geometry']['p']==16 and
         bundle['geometry']['warm_interval']==215,'OWN_CALENDAR')
    for name in (SELF,CPP,VALIDATOR,INVENTORY):files[name]=(ROOT/name).read_bytes()
    need(sha(files[INVENTORY])==INVENTORY_PIN,'GMP_INVENTORY')
    cpp=files[CPP].decode()
    need(cpp.index('gfn16_runtime::configure(context,argc,argv)')<cpp.index('DUT d(&context)'),
         'RUNTIME_BEFORE_DUT')
    manifest['build'].update(cpp_source=CPP,ldflags=['-lgmpxx','-lgmp'])
    normal=dict(name='host-window-normal',argv=['{exe}'],expected_returncode=0,
                expected_stdout=expected('normal'),expected_stderr='')
    manifest['steps']=[normal] if mode=='normal' else [
        dict(name='host-window-corrupt-rollback',argv=['{exe}','--host-corrupt-rollback'],
             expected_returncode=0,expected_stdout=expected('rollback'),expected_stderr=''),
        dict(name='host-window-oracle-negative',argv=['{exe}','--oracle-negative'],
             expected_returncode=1,expected_stdout=expected('normal'),
             expected_stderr='R15_WINDOW_SIGNED96_ORACLE_WITNESS\n')]
    manifest['sources']={n:sha(raw) for n,raw in files.items()}
    manifest.pop('budget_source_members',None)
    manifest.setdefault('metadata',{})['r15_native_gmp']=dict(schema='r15-direct65-gmp-link-v1',
        inventory=dict(path=INVENTORY,sha256=INVENTORY_PIN),fixture_sha256=source_identity(manifest))
    manifest['r15_host_window_gmp']=dict(mode=mode,parent_manifest_sha256=PARENT_MANIFEST,
        production_top=bundle['top'],production_generated_sha256=bundle['generated_sha256'],
        source_freeze_utc=None,normal_gate='s4-p16-c2-r15-direct-compute-aw8-normal-q1-v2',
        actual_DUT_required=True,host_GMP_required=True,python_independent_case_checks=True,
        raw_ACK_COMMIT_then_START_busy_generation=True,profile_internal_no_ACK=True,
        signed96_owned_final_fence=True,per_job_owner_distinct_from_global_ordinal=True,
        physical_reset_delivery=False,actual_DMA_or_CDC=False,VFIO=False,board=False,
        full_N_or_full_PRP=False,upstream_proof_format=False,promotion_allowed=False)
    manifest['test_role']='normal' if mode=='normal' else 'diagnostic'
    manifest['source_root']=manifest['output_parent']='UNBOUND'
    manifest['rtl_readiness']['candidate_id']='r15-host-window-gmp-'+mode
    return manifest,files,bundle


def freeze(mode='normal'):
    manifest,files,bundle=role(mode);out=BASE/mode
    need(not out.exists(),'FRESH_CAPTURE');source=out/'source/fpga';source.mkdir(parents=True)
    manifest['r15_host_window_gmp']['source_freeze_utc']=datetime.now(timezone.utc).isoformat()
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    manifest['source_root']=str(source)
    for name,value in (('manifest.json',manifest),('production-bundle.json',bundle)):
        with (out/name).open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    return dict(manifest=str(out/'manifest.json'),status='SOURCE_ONLY_NOT_NATIVE')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=('normal','faults'),default='normal')
    print(json.dumps(freeze(p.parse_args().mode),sort_keys=True))

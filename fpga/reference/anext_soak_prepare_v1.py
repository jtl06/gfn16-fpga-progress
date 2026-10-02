"""Source-only short A-next soak using an isolated, immutable native donor tree.

This copies preserved full-size numeric assets; it never generates or evaluates
full-size integers. The actual validator admits its Linux GMP runtime first.
"""
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE='artifacts/anext-representative-aw16-role-v1'
BASE_SHA='9cb1ca7056cc774e6d02d955f74549ee95b6df950a720856d4580765cd779524'
DONOR='queue/evidence/soak-t5b-aw16-short-reference-q3-v1/attempt-0/collected'
REPORT_SHA='ec528027b82c3560ad1ab7109ec1ade3a87e7a32ec782a821449ca8993509018'
GENERATION_SHA='70a67b08378f66d4d65178643f7b9ead78dd0d76e0327145f38d8face1fccc9e'
RUNTIME_SHA='84fb40c8e6452d4b660d9302e83584dd3c4761aa6219495e57f2df582401cf0b'

def sha(data):return hashlib.sha256(data).hexdigest()
def need(ok,message):
    if not ok:raise ValueError(message)
def pinned(path,pin):
    need(not path.is_symlink(),'no source symlinks')
    data=path.read_bytes();need(sha(data)==pin,'source drift '+str(path));return data
def prepare(output):
    output=Path(output).resolve()
    need(not output.exists() and not (ROOT/'docs/briefs/PAUSE').exists(),'fresh output/no PAUSE')
    base=json.loads(pinned(ROOT/BASE/'manifest.json',BASE_SHA));files={}
    for name,pin in base['sources'].items():files[name]=pinned(ROOT/BASE/'source/fpga'/name,pin)
    donor=ROOT/DONOR
    report_raw=pinned(donor/'output/command-report.json',REPORT_SHA);report=json.loads(report_raw)
    generation_raw=pinned(donor/'output/reference/generation.json',GENERATION_SHA);generation=json.loads(generation_raw)
    need(report['returncode']==0 and report['HDL_executed'] is False,'successful numeric-only donor')
    for name,pin in report['sources'].items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts,'closed donor path')
        files['donor/fpga/'+name]=pinned(donor/'source/fpga'/name,pin)
    files['donor/reference/command-report.json']=report_raw
    files['donor/reference/generation.json']=generation_raw
    for name,pin in generation['files'].items():
        need(Path(name).name==name,'flat preserved reference files')
        files['donor/reference/'+name]=pinned(donor/'output/reference'/name,pin)
    admission=(donor/'output/reference/auxiliary-runtime-admission.json').read_bytes()
    # The command report, not a guessed generation-file entry, binds this output.
    output_pins=report['outputs']
    need(output_pins['reference/auxiliary-runtime-admission.json']['sha256']==sha(admission),'native auxiliary admission output binding')
    files['donor/reference/auxiliary-runtime-admission.json']=admission
    need(sha(files['donor/fpga/soak/runtime.json'])==RUNTIME_SHA,'exact GCP reference runtime')
    plan=json.loads(files['donor/reference/plan.json'])
    need(plan['profile']['aw']==16 and plan['profile']['base']==604832956 and plan['squares']==2,'short donor recipe')
    for name in ('rtl/tb/anext_soak_v1.cpp','reference/anext_soak_source_v1.py',
                 'reference/anext_soak_output_v1.py','reference/anext_soak_prepare_v1.py',
                 'tests/test_anext_soak_v1.py','tests/test_anext_soak_prepare_v1.py'):
        files[name]=(ROOT/name).read_bytes()
    # Pure small-N tests and exact driver-delta guard only; native numeric
    # validation loads the separately preserved donor tree, never these aliases.
    for name in ('reference/core27_t5b_soak_v1.py','reference/core27_crtmont_soak_v1.py',
                 'rtl/tb/core27_t5b_soak_v1.cpp','rtl/tb/native_runtime_context_v1.h'):
        need('donor/fpga/'+name in files,'closed donor test/driver dependency')
        need(name not in files or files[name]==files['donor/fpga/'+name],'no conflicting candidate source alias')
        files[name]=files['donor/fpga/'+name]
    base['build']['cpp_source']='rtl/tb/anext_soak_v1.cpp'
    base['build']['cflags']=['-std=c++17','-Werror=return-type','-DGFN16_SOAK_AW=16']
    need(len(base['build']['sv_sources'])==30 and all(not x.startswith('donor/') for x in base['build']['sv_sources']),'candidate-only compile closure')
    base['steps']=[]
    for negative in ('none','boundary','loaded-state'):
        base['steps'].append(dict(name='anext-soak-'+negative,
            argv=['{exe}','{root}/donor/reference/continuous.txt']+([] if negative=='none' else ['--negative-'+negative]),
            expected_returncode=0 if negative=='none' else 1,
            expected_stderr='' if negative=='none' else 'SOAK_BOUNDARY_MISMATCH step='+('1' if negative=='boundary' else '0')+' digit=0\n',
            validator=dict(source='reference/anext_soak_output_v1.py',function='validate',config=dict(negative=negative),
                assets=dict(oracle='donor/reference/continuous.json',runtime='donor/fpga/soak/runtime.json'))))
    base['sources']={name:sha(data) for name,data in files.items()}
    base['source_root']='/home/jtl/gfn-fpga-lab/agent-work/anext-soak-short/source/fpga'
    base['output_parent']='/home/jtl/gfn-fpga-lab/agent-work/anext-soak-short/output'
    base['auxiliary_reference_runtime_manifest_sha256']=RUNTIME_SHA
    source=output/'source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    (output/'manifest.json').write_text(json.dumps(base,indent=2)+'\n')
    return dict(status='prepared_not_executed',manifest_sha256=sha((output/'manifest.json').read_bytes()),
        sources=len(files),candidate_sv_count=30,donor_generation_sha256=GENERATION_SHA,
        donor_report_sha256=REPORT_SHA,runtime_sha256=RUNTIME_SHA,host_restriction='gfn16-pilot-c4d',
        operations=2,checkpoint_read_invalidates_prefill=True,expected_prefill_cold=2,
        expected_cache_loads=1,expected_cache_hits=1,promotion_allowed=False)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    print(json.dumps(prepare(p.parse_args().output),indent=2))

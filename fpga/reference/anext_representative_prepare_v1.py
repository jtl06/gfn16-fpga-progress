"""Capture AW16 representative native role, scalar/event preparation only."""
import hashlib,json,shutil
from pathlib import Path
from fpga.reference.anext_representative_source_v1 import verify,CHILD,PARENT
from fpga.reference.anext_core_source_v1 import verify as core_verify
from fpga.reference.anext_a10_block_engine_source_v1 import verify as block_verify
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def prepare(output):
    output=Path(output).resolve()
    if output.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('fresh output/no PAUSE')
    verify();core_verify();block_verify()
    base=ROOT/'artifacts/anext-whole-aw8-role-v2'
    a10=ROOT/'results/throughput-20260929/a10-batch-v1/aw16-f0/input'
    manifest=json.loads((base/'manifest.json').read_text());files={}
    for directory,m in ((base,manifest),(a10,json.loads((a10/'manifest.json').read_text()))):
        for name,pin in m['sources'].items():
            p=directory/'source/fpga'/name
            if sha(p)!=pin:raise ValueError('ancestor source drift '+name)
            if name in files and files[name][1]!=pin:raise ValueError('conflicting source '+name)
            files[name]=(p,pin)
    extra=[CHILD,PARENT,'rtl/tb/track_a4_representative_recipe_v1.hpp',
           'reference/track_a4_representative_recipe_v1.py','reference/anext_representative_source_v1.py',
           'reference/anext_representative_output_v1.py','reference/anext_representative_prepare_v1.py',
           'tests/test_anext_representative_v1.py']
    for name in extra:files[name]=(ROOT/name,sha(ROOT/name))
    source=output/'source/fpga';source.mkdir(parents=True)
    for name,(p,pin) in files.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        if sha(target)!=pin:raise ValueError('copy drift')
    manifest['sources']={name:pin for name,(_,pin) in files.items()}
    b=manifest['build'];b['cpp_source']=CHILD;b['parameters']={'AW':16}
    b['cflags']=['-std=c++17','-Werror=return-type','-DA4_CORE_AW=16']
    b['sv_sources']=[p.replace('a10_packed_lookup_aw8_lint_bound_v2.sv','a10_packed_lookup_aw16_lint_bound_v2.sv') for p in b['sv_sources']]
    if not set(b['sv_sources'])<=set(files):raise ValueError('compiled closure')
    manifest['source_root']='/home/jtl/gfn-fpga-lab/agent-work/anext-representative-aw16/source/fpga'
    manifest['output_parent']='/home/jtl/gfn-fpga-lab/agent-work/anext-representative-aw16/output'
    manifest['steps']=[dict(name='anext-representative-aw16',argv=['{exe}','--representative'],expected_returncode=0,expected_stderr='',
        validator=dict(source='reference/anext_representative_output_v1.py',function='validate',config=dict(mode='representative',aw=16),assets={}))]
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return dict(status='prepared_not_executed',manifest_sha256=sha(output/'manifest.json'),sources=len(files),compiled_sv=len(b['sv_sources']),local_full_n_numeric=False,promotion_allowed=False)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output),indent=2))

"""Command branches on the shared selector; existing native contracts retained."""
import hashlib,json,shutil
from pathlib import Path
from fpga.reference.track_a_trunk_contract_v1 import verify
ROOT=Path(__file__).resolve().parents[1]
PARENTS={
 'block':('rtl/tb/track_a4_core_v4.cpp','85a4598a4437cd7afd7d7cb2090ad00859cd6e99ca5586c95326f3cb577d2384','genefer_track_a4_core_v4','artifacts/track-a4b-normal-aw5-role-v1'),
 'merged':('rtl/tb/track_anext_core_v1.cpp','5519d47876f47fc626af751809094ccf45fa6cba058b142d64ea1755ddf46b7c','genefer_anext_core_v1','artifacts/anext-whole-aw5-role-v2')}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def expected(mode):
    name,pin,old,_=PARENTS[mode]
    if sha(ROOT/name)!=pin:raise ValueError('frozen command harness drift')
    return (ROOT/name).read_text().replace(old,'genefer_track_a_trunk_v1')
def cpp(mode):return 'rtl/tb/track_a_trunk_'+mode+'_v1.cpp'

def prepare(output,mode):
    verify();output=Path(output).resolve()
    if output.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('fresh output/no PAUSE')
    if (ROOT/cpp(mode)).read_text()!=expected(mode):raise ValueError('exact header/model rename only')
    directory=ROOT/PARENTS[mode][3];manifest=json.loads((directory/'manifest.json').read_text());files={}
    for name,pin in manifest['sources'].items():
        p=directory/'source/fpga'/name
        if sha(p)!=pin:raise ValueError('frozen role drift')
        files[name]=(p,pin)
    for name in (cpp(mode),'rtl/kernel/genefer_track_a_trunk_v1.sv','reference/track_a_trunk_contract_v1.py',
                 'reference/track_a_trunk_command_prepare_v1.py','tests/test_track_a_trunk_command_v1.py',
                 'docs/INTEGRATION-CONFLICTS.md',PARENTS[mode][0],
                 'rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1.sv'):
        files[name]=(ROOT/name,sha(ROOT/name))
    source=output/'source/fpga';source.mkdir(parents=True)
    for name,(p,pin) in files.items():
        dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
        if sha(dest)!=pin:raise ValueError('copy drift')
    manifest['sources']={name:pin for name,(_,pin) in files.items()}
    b=manifest['build'];b['top']='genefer_track_a_trunk_v1';b['cpp_source']=cpp(mode)
    b['sv_sources'].append('rtl/kernel/genefer_track_a_trunk_v1.sv')
    b['parameters'].update(USE_BLOCKCARRY=1,USE_MERGED_TWIST=int(mode=='merged'),USE_ROOT_LOOKAHEAD=0)
    manifest['source_root']=f'/home/jtl/gfn-fpga-lab/agent-work/track-a-trunk-{mode}/source/fpga'
    manifest['output_parent']=f'/home/jtl/gfn-fpga-lab/agent-work/track-a-trunk-{mode}/output'
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return dict(status='prepared_not_executed',mode=mode,manifest_sha256=sha(output/'manifest.json'),sources=len(files),unchanged_command_contract=True,promotion_allowed=False)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',choices=PARENTS,required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output,a.mode),indent=2))

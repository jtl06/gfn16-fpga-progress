"""Fresh native roles for the narrow integer-flag binding repair."""
import hashlib,json,shutil
from pathlib import Path
from fpga.reference.track_a_trunk_v2_source import ROOT,PINS,verify,expected
ROLES={
 'flags-off':('artifacts/track-a-trunk-flags-off-aw5-role-v1','900e39685080093d1c1361441fa535cd0ad5074d9dc4b629c479483a4b87241e'),
 'block':('artifacts/track-a-trunk-block-aw5-role-v2','f92af553fc6cb324f829eae79969f115a6fe48fcc43629d1b3e9ef311d983912'),
 'merged':('artifacts/track-a-trunk-merged-aw5-role-v2','3b09c6a3f4e4d29bfe7ff7b91c7ffbeab884dff38eed1810cb6e12db6af815e1')}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def prepare(output,mode):
    output=Path(output).resolve();directory,pin=ROLES[mode];directory=ROOT/directory
    if output.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('fresh output/no PAUSE')
    verify()
    if sha(directory/'manifest.json')!=pin:raise ValueError('predecessor role identity')
    m=json.loads((directory/'manifest.json').read_text());files={}
    for name,p in m['sources'].items():
        src=directory/'source/fpga'/name
        if sha(src)!=p:raise ValueError('frozen source drift')
        files[name]=(src,p)
    for name in [*PINS,*expected(),'reference/track_a_trunk_v2_source.py','reference/track_a_trunk_v2_prepare.py','tests/test_track_a_trunk_v2_source.py']:
        files[name]=(ROOT/name,sha(ROOT/name))
    source=output/'source/fpga';source.mkdir(parents=True)
    for name,(src,p) in files.items():
        dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
        if sha(dest)!=p:raise ValueError('snapshot drift')
    m['sources']={n:p for n,(_,p) in files.items()};b=m['build']
    mapping={name:name.replace('_v1.','_v2.') for name in PINS}
    b['sv_sources']=[mapping.get(n,n) for n in b['sv_sources']];b['cpp_source']=mapping[b['cpp_source']]
    b['top']=b['top'][:-2]+'v2'
    m['source_root']=f'/home/jtl/gfn-fpga-lab/agent-work/track-a-trunk-v2-{mode}/source/fpga'
    m['output_parent']=f'/home/jtl/gfn-fpga-lab/agent-work/track-a-trunk-v2-{mode}/output'
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    return dict(status='prepared_not_executed',mode=mode,manifest_sha256=sha(output/'manifest.json'),sources=len(files),native_steps_changed=False)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',choices=ROLES,required=True);a=p.parse_args();print(json.dumps(prepare(a.output,a.mode),indent=2))

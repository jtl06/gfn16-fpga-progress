"""Source-bound AW16 point successor; scalar/event preparation only."""
import json
import shutil
from pathlib import Path
from fpga.reference import anext_point_source_v1 as parent
from fpga.reference import anext_representative_source_v1 as bench
ROOT=parent.ROOT
ROLE='artifacts/anext-representative-aw16-role-v1'
PIN='9cb1ca7056cc774e6d02d955f74549ee95b6df950a720856d4580765cd779524'
CPP='rtl/tb/track_anext_point_representative_v1.cpp'
OUTPUT='reference/anext_point_representative_output_v1.py'
OUTPUT_PARENT='reference/anext_representative_output_v1.py'
OUTPUT_PIN='bd019754e553c9f0f824e9c9e7b10f1ae9e22cfa7d7760692890bf2cd2c02739'

def expected():
    bench.verify();parent.verify()
    if parent.sha(ROOT/OUTPUT_PARENT)!=OUTPUT_PIN:raise ValueError('point representative output parent')
    cpp=(ROOT/bench.CHILD).read_text().replace('genefer_anext_core_v1','genefer_anext_point_core_v1')
    out=(ROOT/OUTPUT_PARENT).read_text().replace('from fpga.reference.anext_composition_contract_v1 import schedule',
                                              'from fpga.reference.anext_point_contract_v1 import schedule')
    out=out.replace("candidate='A-next-v1'","candidate='A-next-point-v1'")
    return {CPP:cpp,OUTPUT:out}

def prepare(output):
    output=Path(output).resolve()
    if output.exists() or (ROOT/'docs/briefs/PAUSE').exists() or parent.sha(ROOT/ROLE/'manifest.json')!=PIN:
        raise ValueError('fresh exact representative parent/no PAUSE')
    generated=parent.verify()
    for path,text in expected().items():
        if (ROOT/path).read_text()!=text:raise ValueError('point representative guarded derivative')
    m=json.loads((ROOT/ROLE/'manifest.json').read_text())
    for name,pin in m['sources'].items():
        if parent.sha(ROOT/ROLE/'source/fpga'/name)!=pin:raise ValueError('point representative ancestor drift')
    shutil.copytree(ROOT/ROLE/'source',output/'source')
    extras=[*generated,*expected(),'reference/anext_point_source_v1.py','reference/anext_point_contract_v1.py',
            'reference/anext_point_representative_v1.py','tests/test_anext_point_representative_v1.py',parent.GEN,parent.POINT]
    for name in extras:
        dest=output/'source/fpga'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,dest);m['sources'][name]=parent.sha(dest)
    compiled=[]
    for name in m['build']['sv_sources']:
        for old,new in parent.NAMES.items():name=name.replace(old,new)
        compiled.append(name)
    m['build'].update(top='genefer_anext_point_core_v1',cpp_source=CPP,sv_sources=compiled)
    m['steps'][0]['name']='anext-point-representative-aw16';m['steps'][0]['validator']['source']=OUTPUT
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    return dict(manifest_sha256=parent.sha(output/'manifest.json'),sources=len(m['sources']),compiled_sv=len(compiled),local_full_n_numeric=False)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output),indent=2))

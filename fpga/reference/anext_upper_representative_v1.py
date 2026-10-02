"""Unchanged AW16 recipe/cycles, upper-prereg whole-core binding only."""
import json,shutil
from pathlib import Path
from fpga.reference import anext_upper_source_v1 as upper
from fpga.reference import anext_point_representative_v1 as parent
ROOT=upper.ROOT
ROLE='artifacts/anext-point-representative-aw16-role-v1'
PIN='98ae80e62e95f70d08acf1d03af9bb9fdf84003852d900afaecce769d358c84a'
CPP='rtl/tb/track_anext_upper_representative_v1.cpp'
OUTPUT='reference/anext_upper_representative_output_v1.py'
def expected():
    upper.verify();p=parent.expected()
    return {CPP:upper.renames(p[parent.CPP]),OUTPUT:upper.renames(p[parent.OUTPUT])}
def prepare(output):
    output=Path(output).resolve()
    if output.exists() or (ROOT/'docs/briefs/PAUSE').exists() or upper.point.sha(ROOT/ROLE/'manifest.json')!=PIN:raise ValueError('fresh exact upper representative role')
    generated=upper.verify()
    for path,text in expected().items():
        if (ROOT/path).read_text()!=text:raise ValueError('upper representative derivative')
    m=json.loads((ROOT/ROLE/'manifest.json').read_text())
    for name,pin in m['sources'].items():
        if upper.point.sha(ROOT/ROLE/'source/fpga'/name)!=pin:raise ValueError('point source closure')
    shutil.copytree(ROOT/ROLE/'source',output/'source')
    for name in [*generated,*expected(),upper.GEN,upper.CELL,upper.ENGINE,'reference/anext_upper_source_v1.py','reference/anext_upper_representative_v1.py','tests/test_anext_upper_representative_v1.py']:
        d=output/'source/fpga'/name;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,d);m['sources'][name]=upper.point.sha(d)
    m['build'].update(top='genefer_anext_upper_core_v1',cpp_source=CPP)
    m['build']['sv_sources']=[upper.CELL if name==upper.OLD_CELL else upper.renames(name) for name in m['build']['sv_sources']]
    m['steps'][0]['name']='anext-upper-representative-aw16';m['steps'][0]['validator']['source']=OUTPUT
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    return dict(manifest_sha256=upper.point.sha(output/'manifest.json'),sources=len(m['sources']),compiled_sv=30,cycle_delta_from_point=0,local_full_N_numeric=False)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(prepare(a.output),indent=2))

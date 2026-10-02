"""Source-only point-launch whole integration; unchanged exact small corpus."""
import json
import shutil
from pathlib import Path
from fpga.reference import anext_point_source_v1 as source

ROOT=source.ROOT
PARENTS={5:'0e51a47a61a9860a9a3937deedb47d54c554b158d721b6906db4d4ba47637505',
         8:'247af49b1e6991192f0884372a2281139d032fe72e44f992147932e64f64303e'}
EXTRA=['reference/anext_point_source_v1.py','reference/anext_point_contract_v1.py',
       'reference/anext_point_prepare_v1.py','tests/test_anext_point_v1.py',source.GEN,source.POINT]

def prepare(output,aw):
    output=Path(output).resolve()
    if aw not in PARENTS or output.exists() or (ROOT/'docs/briefs/PAUSE').exists():
        raise ValueError('ANEXT_POINT_FRESH_SMALL_ROLE_NO_PAUSE')
    generated=source.verify()
    ancestor=ROOT/f'artifacts/anext-whole-aw{aw}-role-v2'
    if source.sha(ancestor/'manifest.json')!=PARENTS[aw]:raise ValueError('ANEXT_POINT_ROLE_PARENT_PIN')
    manifest=json.loads((ancestor/'manifest.json').read_text());pins=manifest['sources']
    for name,pin in pins.items():
        if source.sha(ancestor/'source/fpga'/name)!=pin:raise ValueError('ANEXT_POINT_ANCESTOR_CLOSURE '+name)
    shutil.copytree(ancestor/'source',output/'source')
    for name in [*generated,*EXTRA]:
        dest=output/'source/fpga'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,dest);pins[name]=source.sha(dest)
    compiled=[]
    for name in manifest['build']['sv_sources']:
        for old,new in source.NAMES.items():name=name.replace(old,new)
        compiled.append(name)
    manifest['build'].update(top='genefer_anext_point_core_v1',sv_sources=compiled,
                             cpp_source='rtl/tb/track_anext_point_core_v1.cpp')
    for step in manifest['steps']:
        step['name']=f'anext-point-normal-aw{aw}'
        step['validator']['source']='reference/anext_point_output_v1.py'
    manifest['source_root']=f'/home/jtl/gfn-fpga-lab/agent-work/anext-point-aw{aw}/source/fpga'
    manifest['output_parent']=f'/home/jtl/gfn-fpga-lab/agent-work/anext-point-aw{aw}/output'
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    result=dict(status='source_prepared_not_executed',aw=aw,manifest_sha256=source.sha(output/'manifest.json'),
                compiled_sv=len(compiled),sources=len(pins),point_component_sha256=source.POINT_SHA,
                block_response_edges=1,normal_total_cycle_delta=1,promotion_allowed=False)
    (output/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--aw',type=int,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.aw),indent=2))

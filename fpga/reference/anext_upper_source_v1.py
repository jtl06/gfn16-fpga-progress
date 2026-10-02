"""Latency-neutral upper prereg composition on frozen point-only A-next."""
import ast,json,shutil
from pathlib import Path
from fpga.reference import anext_point_source_v1 as point
ROOT=point.ROOT
GEN='reference/a10_upper_sum_generate_v2.py'
GEN_SHA='9e36bc24e947637b070395621fb83ace275dd8c95684960f7815770490769d74'
CELL='rtl/kernel/genefer_a10_canonical_butterfly_sumlaunch_v2.sv'
CELL_SHA='6e6688e37df413b2506c03bd27a3c8eb7962ae45a94d9935150d2175afad6f8b'
ENGINE='rtl/kernel/genefer_a10_banked27_engine_sumlaunch_v4.sv'
ENGINE_SHA='03f3e395cccac6e17979f7990bc12095675e264afa08a884a77100aa3f3cb273'
OLD_CELL='rtl/kernel/genefer_a10_canonical_butterfly_v1.sv'
OLD_CELL_SHA='c05f64749b333bbdedee8e470fb9f468f6123cd7d2f0f3b0c725cbfc41c120fc'
OLD_BIND='genefer_a10_canonical_butterfly_v1 #'
NEW_BIND='genefer_a10_canonical_butterfly_sumlaunch_v2 #'
ROLES={5:'11340a6819c863139bff8b50564d44a0b5d1df3b2eaa8b154f969a0e42d7aeeb',
       8:'5e688cbd1de473b445a216642a6b63d79b3ca676b6821dab317802ef8e29a7ef'}

def renames(text):
    return text.replace('genefer_anext_point_','genefer_anext_upper_').replace('track_anext_point_','track_anext_upper_').replace('anext_point_output_v1','anext_upper_output_v1').replace("candidate='A-next-point-v1'","candidate='A-next-upper-v1'")

def component_guard():
    for path,pin in ((GEN,GEN_SHA),(CELL,CELL_SHA),(ENGINE,ENGINE_SHA),(OLD_CELL,OLD_CELL_SHA)):
        if point.sha(ROOT/path)!=pin:raise ValueError('ANEXT_UPPER_COMPONENT_PIN '+path)
    tree=ast.parse((ROOT/GEN).read_text());f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='changes')
    if len(f.body)!=1 or not isinstance(f.body[0],ast.Return):raise ValueError('literal cell delta only')
    changes=ast.literal_eval(f.body[0].value);cell=(ROOT/OLD_CELL).read_text()
    for before,after in changes:cell=point.core.once(cell,before,after)
    if cell!=(ROOT/CELL).read_text():raise ValueError('upper exact cell delta')
    back=cell
    for before,after in reversed(changes):back=point.core.once(back,after,before)
    if back!=(ROOT/OLD_CELL).read_text():raise ValueError('upper reversible cell delta')
    raw=point.core.once((ROOT/point.POINT).read_text(),OLD_BIND,NEW_BIND)
    if raw!=(ROOT/ENGINE).read_text():raise ValueError('upper raw engine binding-only delta')

def expected():
    point.verify();component_guard();files=point.expected();result={}
    for path,text in files.items():
        if path.endswith('genefer_anext_point_block_engine_v1.sv'):text=point.core.once(text,OLD_BIND,NEW_BIND)
        result[renames(path)]=renames(text)
    return result

def verify():
    result=expected()
    for path,text in result.items():
        if (ROOT/path).read_text()!=text:raise ValueError('upper exact composition '+path)
    return {path:point.sha(ROOT/path) for path in result}

def prepare(output,aw):
    output=Path(output).resolve()
    if aw not in ROLES or output.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('fresh bounded role/no PAUSE')
    generated=verify();base=ROOT/f'artifacts/anext-point-whole-aw{aw}-role-v1'
    if point.sha(base/'manifest.json')!=ROLES[aw]:raise ValueError('point whole role pin')
    m=json.loads((base/'manifest.json').read_text())
    for name,pin in m['sources'].items():
        if point.sha(base/'source/fpga'/name)!=pin:raise ValueError('point parent closure')
    shutil.copytree(base/'source',output/'source')
    for name in [*generated,GEN,CELL,ENGINE,'reference/anext_upper_source_v1.py','tests/test_anext_upper_v1.py']:
        dest=output/'source/fpga'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest);m['sources'][name]=point.sha(dest)
    m['build']['top']='genefer_anext_upper_core_v1';m['build']['cpp_source']=renames(m['build']['cpp_source'])
    m['build']['sv_sources']=[CELL if name==OLD_CELL else renames(name) for name in m['build']['sv_sources']]
    for s in m['steps']:
        s['name']=f'anext-upper-normal-aw{aw}';s['validator']['source']='reference/anext_upper_output_v1.py'
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    return dict(manifest_sha256=point.sha(output/'manifest.json'),sources=len(m['sources']),compiled_sv=len(m['build']['sv_sources']),
        engine_cycle_delta=0,external_block_latency_delta=0,native_executed=False,promotion_allowed=False)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--aw',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(prepare(a.output,a.aw),indent=2))

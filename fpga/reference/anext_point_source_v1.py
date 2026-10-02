"""Additive measured A10 point-launch delta in the frozen A-next block ABI.

No arithmetic/root/profile/host logic change: eight exact point launch/tag sites,
then unique module bindings. External independent block RAM E0/E1 is unchanged.
"""
import ast
import hashlib
from pathlib import Path
from fpga.reference import anext_core_source_v1 as core
from fpga.reference import anext_a10_block_engine_source_v1 as block

ROOT=Path(__file__).resolve().parents[1]
GEN='reference/a10_point_launch_generate_v3.py'
GEN_SHA='d77e514da011a0a4c1a4711a714fc173415a9d1728654bf86ffbde1643cd22c8'
POINT='rtl/kernel/genefer_a10_banked27_engine_pointlaunch_v3.sv'
POINT_SHA='087bb158c0f493e22ed8e49372e233928979ed2161eff11f21f4510d2888c646'
OUTPUT='reference/anext_native_output_v1.py'
OUTPUT_SHA='fb8e447fdb6cf697450b2a9d867ddc514a25b0af67b28a2a71015922655cf0be'
NAMES={
 'genefer_anext_a10_block_engine_v1':'genefer_anext_point_block_engine_v1',
 'genefer_anext_ntt_sequencer_v1':'genefer_anext_point_ntt_sequencer_v1',
 'genefer_anext_square_backend_v1':'genefer_anext_point_square_backend_v1',
 'genefer_anext_core_v1':'genefer_anext_point_core_v1',
}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def changes():
    if sha(ROOT/GEN)!=GEN_SHA or sha(ROOT/POINT)!=POINT_SHA:
        raise ValueError('ANEXT_POINT_COMPONENT_SOURCE_PIN')
    tree=ast.parse((ROOT/GEN).read_text())
    function=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='changes')
    if len(function.body)!=1 or not isinstance(function.body[0],ast.Return):
        raise ValueError('ANEXT_POINT_LITERAL_DELTA')
    result=ast.literal_eval(function.body[0].value)
    if len(result)!=8:raise ValueError('ANEXT_POINT_EIGHT_SITES')
    return result

def apply_delta(text):
    original=text
    for before,after in changes():text=core.once(text,before,after)
    restored=text
    for before,after in reversed(changes()):restored=core.once(restored,after,before)
    if restored!=original:raise ValueError('ANEXT_POINT_REVERSIBLE_DELTA')
    return text

def expected():
    core.verify();block.verify()
    raw=(ROOT/block.PARENT).read_text()
    if apply_delta(raw).rstrip()+'\n'!=(ROOT/POINT).read_text():
        raise ValueError('ANEXT_POINT_RAW_COMPONENT_EQUIVALENCE')
    engine=apply_delta((ROOT/block.TARGET).read_text())
    files={block.TARGET:engine,**core.expected()}
    result={}
    for path,text in files.items():
        for old,new in NAMES.items():
            text=text.replace(old,new);path=path.replace(old,new)
        if path=='rtl/tb/track_anext_core_v1.cpp':path='rtl/tb/track_anext_point_core_v1.cpp'
        result[path]=text.rstrip()+'\n'  # Only normalize the spare parent EOF blank.
    if sha(ROOT/OUTPUT)!=OUTPUT_SHA:raise ValueError('ANEXT_POINT_OUTPUT_PARENT_PIN')
    output=(ROOT/OUTPUT).read_text()
    output=core.once(output,'from fpga.reference.anext_composition_contract_v1 import schedule',
                     'from fpga.reference.anext_point_contract_v1 import schedule')
    output=core.once(output,"candidate='A-next-v1'","candidate='A-next-point-v1'")
    result['reference/anext_point_output_v1.py']=output
    return result

def verify():
    result=expected()
    for path,text in result.items():
        if (ROOT/path).read_text()!=text:raise ValueError('ANEXT_POINT_COMPOSITION_DRIFT '+path)
    return {path:sha(ROOT/path) for path in result}

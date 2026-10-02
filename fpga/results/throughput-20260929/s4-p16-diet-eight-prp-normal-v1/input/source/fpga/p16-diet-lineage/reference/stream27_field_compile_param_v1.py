"""Additive P8/P16 canonical27 baseline compiler, exact frozen ancestry.

No lazy input is legal here. S-M2 supplies a separately proved CT/GS topology
and roots later; this baseline is the original DIF/DIT twisted construction.
"""
import ast
import hashlib
from pathlib import Path
from . import stream27_field_plan as original_plan
from . import stream27_field_compile as original_compile

ROOT=Path(__file__).resolve().parents[1]
PINS={'reference/stream27_field_plan.py':'6103899b2488d4dc96aedfe2549db291045badb7e38f5885de20c7f721a4f032',
      'reference/stream27_field_compile.py':'c31f0295c891f02d2d96311e8ccc2f3c1d73e8fb9b0112fc4f2d80d3e972b53d'}


def function_source(path,name):
    raw=(ROOT/path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PINS[path]:raise ValueError('frozen compiler ancestor '+path)
    text=raw.decode();lines=text.splitlines(keepends=True)
    nodes=[n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name]
    if len(nodes)!=1:raise ValueError('unique ancestor function')
    node=nodes[0];return ''.join(lines[node.lineno-1:node.end_lineno])


def replace_once(text,before,after):
    if text.count(before)!=1:raise ValueError('unique compiler delta anchor '+before)
    return text.replace(before,after)


topology_source=function_source('reference/stream27_field_plan.py','topology')
topology_source=replace_once(topology_source,'p != 8','p not in (8,16)')
topology_source=topology_source.replace('AW3..16/P8 (AW3 is correction transform only)','AW3..16/P8|P16 canonical baseline')
_plan_namespace=dict(vars(original_plan))
exec(compile(topology_source,'<frozen-topology-P8-P16-guard>','exec'),_plan_namespace)
topology=_plan_namespace['topology']

compiler_source=function_source('reference/stream27_field_compile.py','compile_transform')
compiler_source=replace_once(compiler_source,'n=32, field=0, *, inverse=False','n=32, field=0, parallelism=8, *, inverse=False')
compiler_source=replace_once(compiler_source,'topology(n, inverse=inverse)','topology(n, parallelism, inverse=inverse)')
compiler_source=replace_once(compiler_source,"_p8_f{field}'","_p{parallelism}_f{field}'")
compiler_source=replace_once(compiler_source,'range(8)','range(parallelism)')
_compile_namespace=dict(vars(original_compile),topology=topology)
exec(compile(compiler_source,'<frozen-compiler-P8-P16-geometry>','exec'),_compile_namespace)


def compile_transform(n=32,field=0,parallelism=8,*,inverse=False,small_registers=False,
                      emit_numeric_roms=True,allow_large_root_tables=False):
    if parallelism not in (8,16) or n<parallelism:raise ValueError('baseline P8/P16 geometry')
    result=_compile_namespace['compile_transform'](n,field,parallelism,inverse=inverse,
        emit_numeric_roms=emit_numeric_roms,allow_large_root_tables=allow_large_root_tables)
    source=result['source']
    if parallelism==16:
        alignment='      sh_start!={4{sh_start[0]}} || sh_generation[1]!=sh_generation[0] ||\n      sh_generation[2]!=sh_generation[0] || sh_generation[3]!=sh_generation[0]);'
        replacement='      sh_start!={8{sh_start[0]}} || '+' || '.join(f'sh_generation[{i}]!=sh_generation[0]' for i in range(1,8))+');'
        count=sum(s['shuffle_depth_per_buffer']!=0 for s in result['topology']['stages'])
        if source.count(alignment)!=count:raise ValueError('all shuffle metadata alignment anchors')
        source=source.replace(alignment,replacement).replace('[215:0]','[431:0]').replace('[3:0]','[7:0]').replace('[0:3]','[0:7]')
        source=source.replace('bf_valid!={4{slot_pipe[5]}}','bf_valid!={8{slot_pipe[5]}}')
    if small_registers:
        source=source.replace('genefer_stream27_mdc_commutator_slots_v2','genefer_stream27_mdc_commutator_slots_sm1_v1')
        result['source_dependencies']=[p for p in result['source_dependencies'] if not p.endswith('genefer_stream27_mdc_commutator_slots_v2.sv')]
        result['source_dependencies']+=['rtl/kernel/genefer_stream27_mdc_commutator_slots_sm1_v1.sv','rtl/kernel/genefer_stream27_mdc_fifo_smallreg_v1.sv']
    result['source']=source
    result['arithmetic_contract']='canonical [0,P),27-bit; NOT lazy [0,2P)'
    result['small_registers']=small_registers
    return result

"""Exact commuting F3 internal-write delta on the frozen upper block ABI."""
import ast,json,shutil
from pathlib import Path
from fpga.reference import anext_upper_source_v1 as upper
ROOT=upper.ROOT
GEN='reference/a10_writeback_launch_generate_v1.py'
GEN_SHA='fc3760529ddcc12044a531f9a39d89faf5e26dc0f7a3c7b611d1ea5f628d1f03'
ENGINE='rtl/kernel/genefer_a10_banked27_engine_writeback_v1.sv'
ENGINE_SHA='f200303571a01042c17e5c8a5b4070bd94d810503bc05285523cec370cda2ace'
ROLES={5:('anext-upper-whole-aw5-role-v1','74cc883d85fef7d696a8ae62e26378b7719e5079b28d0b791cda605435b14351'),8:('anext-upper-whole-aw8-role-v1','66996fbc7c4f9d712e66b5c8119a1373df637a1f5d199d907465837bc049b9bb'),16:('anext-upper-representative-aw16-role-v1','734b33e574f38d227bfbadff0c0beaeecc9891c078672ff69024ba76d32aeae4')}
def need(ok,why):
    if not ok:raise ValueError(why)
def rename(t):return t.replace('genefer_anext_upper_','genefer_anext_writeback_').replace('track_anext_upper_','track_anext_writeback_').replace('anext_upper_output_v1','anext_writeback_output_v1').replace('anext_upper_representative_output_v1','anext_writeback_representative_output_v1').replace("candidate='A-next-upper-v1'","candidate='A-next-writeback-v1'")
def changes():
    need(upper.point.sha(ROOT/GEN)==GEN_SHA and upper.point.sha(ROOT/ENGINE)==ENGINE_SHA,'frozen F3 component pins')
    tree=ast.parse((ROOT/GEN).read_text());bank=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='BANK_LAUNCH' for x in n.targets));literal=ast.literal_eval(bank.value)
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='changes');need(len(fn.body)==1 and isinstance(fn.body[0],ast.Return),'literal F3 changes only')
    def value(n):
        if isinstance(n,ast.Constant):return n.value
        if isinstance(n,ast.Tuple):return tuple(value(x) for x in n.elts)
        if isinstance(n,ast.Name) and n.id=='BANK_LAUNCH':return literal
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Add):return value(n.left)+value(n.right)
        raise ValueError('nonliteral F3 delta')
    result=value(fn.body[0].value);need(len(result)==10,'ten exact component sites');return result
def transform(t):
    old=t;once=upper.point.core.once
    for a,b in changes():t=once(t,a,b)
    restored=t
    for a,b in reversed(changes()):restored=once(restored,b,a)
    need(restored==old,'exact reversible block delta');return t
def expected():
    upper.verify();need(transform((ROOT/upper.ENGINE).read_text())==(ROOT/ENGINE).read_text(),'raw F3 equivalence')
    result={}
    for name,t in upper.expected().items():
        if name.endswith('genefer_anext_upper_block_engine_v1.sv'):t=transform(t)
        if name.endswith('anext_upper_output_v1.py'):t=upper.point.core.once(t,'from fpga.reference.anext_point_contract_v1 import schedule','from fpga.reference.anext_writeback_contract_v1 import schedule')
        result[rename(name)]=rename(t)
    for name in ('rtl/tb/track_anext_upper_representative_v1.cpp','reference/anext_upper_representative_output_v1.py'):
        t=(ROOT/name).read_text()
        if name.endswith('.py'):t=upper.point.core.once(t,'from fpga.reference.anext_point_contract_v1 import schedule','from fpga.reference.anext_writeback_contract_v1 import schedule')
        result[rename(name)]=rename(t)
    return result
def verify():
    result=expected()
    for name,t in result.items():need((ROOT/name).read_text()==t,'exact F3 composition '+name)
    return {n:upper.point.sha(ROOT/n) for n in result}
def prepare(aw,output):
    need(aw in ROLES,'finite geometry');output=Path(output).resolve();need(not output.exists() and not (ROOT/'docs/briefs/PAUSE').exists(),'fresh output/no PAUSE')
    generated=verify();role,pin=ROLES[aw];base=ROOT/'artifacts'/role;need(upper.point.sha(base/'manifest.json')==pin,'frozen upper role')
    m=json.loads((base/'manifest.json').read_text())
    for n,h in m['sources'].items():need(upper.point.sha(base/'source/fpga'/n)==h,'closed upper source')
    shutil.copytree(base/'source',output/'source')
    for n in [*generated,GEN,ENGINE,'reference/anext_writeback_source_v1.py','reference/anext_writeback_contract_v1.py','tests/test_anext_writeback_v1.py','rtl/tb/track_anext_upper_representative_v1.cpp','reference/anext_upper_representative_output_v1.py']:
        d=output/'source/fpga'/n;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,d);m['sources'][n]=upper.point.sha(d)
    m['build'].update(top='genefer_anext_writeback_core_v1',cpp_source=rename(m['build']['cpp_source']),sv_sources=[rename(n) for n in m['build']['sv_sources']])
    for s in m['steps']:s['name']=f'anext-writeback-aw{aw}';s['validator']['source']=rename(s['validator']['source'])
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    return dict(manifest_sha256=upper.point.sha(output/'manifest.json'),sources=len(m['sources']),compiled_sv=len(m['build']['sv_sources']),expected_cycle_delta=2*aw+1,native_executed=False)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--aw',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(prepare(a.aw,a.output),indent=2))

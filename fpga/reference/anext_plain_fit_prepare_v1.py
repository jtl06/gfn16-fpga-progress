"""Source-only direct A-next prototype whole-fit project; native snapshot lineage."""
import hashlib,json,copy
from pathlib import Path
from fpga.cloud.plain_fit_v1 import FULL_TCL
from fpga.tools.prefit_structural_guard_v1 import source_inventory,identities
ROOT=Path(__file__).resolve().parents[1]
ROLE='artifacts/anext-representative-aw16-role-v1'
ROLE_SHA='9cb1ca7056cc774e6d02d955f74549ee95b6df950a720856d4580765cd779524'
A4='artifacts/a4b-10ns-aws-plain-v1/project'
A4_SHA='08432ae4d607152d8384518757a79e8bcdb62edab992e28e10711b7cca2284a1'
SPEC='results/throughput-20260929/track-a4b-prefit-source-v2/inventory.json'
SPEC_SHA='47469dffa965c20843f2d65ca263f603a51eec9391c22dbc65a597bcc7c6eb7a'
NATIVE='queue/evidence/anext-v1-representative-aw16-q1-v1/attempt-0/collected/output/native/report.json'
NATIVE_SHA='4c007b321ad311bd29f030bce4f9a6e5e41e150cef6b0da20d22f6c235c06af8'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def replace_tree(value):
    if isinstance(value,list):return [replace_tree(x) for x in value]
    if isinstance(value,dict):return {replace_tree(k):replace_tree(v) for k,v in value.items()}
    if isinstance(value,str):
        for old,new in (('genefer_track_a4_square_backend_v4','genefer_anext_square_backend_v1'),('genefer_track_a4_core_v4','genefer_anext_core_v1'),('genefer_track_a4_ntt_sequencer_v1','genefer_anext_ntt_sequencer_v1')):value=value.replace(old,new)
    return value

def prepare(output,period='9.668'):
    if period not in ('9.668','8.0'):raise ValueError('finite requested target')
    output=Path(output).resolve()
    if output.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('fresh output/no PAUSE')
    for name,pin in ((ROLE+'/manifest.json',ROLE_SHA),(A4+'/manifest.json',A4_SHA),(SPEC,SPEC_SHA),(NATIVE,NATIVE_SHA)):
        if sha(ROOT/name)!=pin:raise ValueError('frozen source/native identity '+name)
    role=json.loads((ROOT/ROLE/'manifest.json').read_text());old=json.loads((ROOT/A4/'manifest.json').read_text())
    sv=role['build']['sv_sources'];m=copy.deepcopy(old);project=output/'project';(project/'rtl').mkdir(parents=True)
    if len(sv)!=30 or len({Path(x).name for x in sv})!=30:raise ValueError('exact30 unique compiled SV')
    sources={}
    for name in sv:
        src=ROOT/ROLE/'source/fpga'/name;pin=role['sources'][name]
        if sha(src)!=pin:raise ValueError('native RTL drift')
        dest=project/'rtl'/Path(name).name;dest.write_bytes(src.read_bytes());sources[dest.name]=pin
    qsf=(ROOT/A4/'probe.qsf').read_text()
    qsf='\n'.join(line for line in qsf.splitlines() if not line.startswith('set_global_assignment -name SYSTEMVERILOG_FILE '))+'\n'
    qsf=qsf.replace('TOP_LEVEL_ENTITY genefer_track_a4_core_v4','TOP_LEVEL_ENTITY genefer_anext_core_v1').replace('NUM_PARALLEL_PROCESSORS 6','NUM_PARALLEL_PROCESSORS 4')
    qsf+=''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+Path(name).name+'\n' for name in sv)
    sdc=(ROOT/A4/'probe.sdc').read_text()
    if sdc.count('-period 10 [get_ports {clk}]')!=1:raise ValueError('exact inherited clock literal')
    sdc=sdc.replace('-period 10 [get_ports {clk}]','-period '+period+' [get_ports {clk}]').replace('Exploratory 10 ns','Exploratory '+period+' ns')
    for name,text in (('probe.qsf',qsf),('probe.sdc',sdc),('run.tcl',FULL_TCL),('probe.qpf',(ROOT/A4/'probe.qpf').read_text())):(project/name).write_text(text)
    m.update(status='source_prepared_direct_A_next_not_dispatched',top='genefer_anext_core_v1',clock_period_ns=float(period),compile_processors=4,
             source_sha256=sources,parent_manifest_sha256=A4_SHA,native_source_manifest_sha256=ROLE_SHA,native_report_sha256=NATIVE_SHA,
             note='Direct AW16-qualified A-next prototype, explicit command ABI; not selector trunk. No inherited clock or promotion.')
    m['parent_source_ticket_sha256']=m.pop('source_ticket_sha256')
    m['control_sha256']={name:sha(project/name) for name in ('probe.qpf','probe.sdc','run.tcl','probe.qsf')};save(project/'manifest.json',m)
    spec=replace_tree(json.loads((ROOT/SPEC).read_text()));spec['identity']['clock_period_ns']=float(period)
    spec['sources']={'rtl/'+name:pin for name,pin in sources.items()};spec['settings']={**m['control_sha256'],'manifest.json':sha(project/'manifest.json')}
    source=source_inventory(project,spec)
    if source['findings']:raise ValueError('structural findings')
    save(output/'inventory.json',spec)
    context=dict(manifest_sha256=sha(project/'manifest.json'),source_sha256=sources,control_sha256={**m['control_sha256'],'manifest.json':sha(project/'manifest.json')},qsf_parameters={'AW':16});save(output/'project-context.json',context)
    result=dict(status='PASS_declared_source_inventory_only',**identities(spec),manifest_sha256=sha(project/'manifest.json'),inventory_sha256=sha(output/'inventory.json'),context_sha256=sha(output/'project-context.json'),
                compiled_sv=30,rtl_changed_from_native=False,native_report_sha256=NATIVE_SHA,structural_result=source,
                scope='Same declared macro boundaries/ports as A4b; inner field/root implementation changed to A10. Source inventory is not complete netlist/timing proof.',
                host_abi='command_ready_response_valid',vendor_executed=False,fit_launched=False,promotion_allowed=False)
    save(output/'source-preparation.json',result);return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--period',default='9.668');a=p.parse_args();print(json.dumps(prepare(a.output,a.period),indent=2))

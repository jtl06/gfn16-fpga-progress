"""Source-only physical project for the qualified shared canonical flag.

Standing fits consumes the project/structural inventory after the actual
full-size normal gate. No vendor run, cloud call or clock claim occurs here.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from fpga.reference import stream27_host_chain_param_v3 as core
from fpga.reference import stream27_host_chain_physical_v1 as old
from fpga.reference.stream27_host_chain_canonpipe_native_v1 import IDENTIFIER
from fpga.tools.prefit_structural_guard_v1 import source_inventory
from fpga.tools.plain_fit_queue_v3 import variant_descriptor

ROOT=core.ROOT
SELF='reference/stream27_canonical_pipe_fit_v1.py'
BASE_INVENTORY='results/throughput-20260929/s4-p8-whole-host-structural-source-v2/inventory.json'
NATIVE_REQUIRED=IDENTIFIER[:-1]+'2'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination,*,workers=4):
    destination=Path(destination).resolve()
    if (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('CANON_PIPE_FIT_PAUSE')
    b=core.prepare(65536,8,paired=False,contexts=1,allow_full_constants=True,canonical_pipe_stages=1)
    root_pin=hashlib.sha256(b['files'][b['top']+'.sv'].encode()).hexdigest()
    raw=(ROOT/'reference/stream27_host_chain_physical_v1.py').read_text()
    node=next(x for x in ast.parse(raw).body if isinstance(x,ast.FunctionDef) and x.name=='prepare')
    body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    body=body.replace('parameters=dict(AW=16,P=8,CONTEXTS=1,EPOCH_SEED=65534)',
                      'parameters=dict(AW=16,P=8,CONTEXTS=1,EPOCH_SEED=65534,CANONICAL_PIPE_STAGES=1)')
    body=body.replace('s4-aw16-p8-full-host-q1-v1 actual PASS source/config closure; pending, not inherited from field or small PRP',
                      NATIVE_REQUIRED+' actual source/config-bound PASS required; pending, not inherited from frozen physical baseline')
    def compile_core(n,p,**kwargs):return core.prepare(n,p,canonical_pipe_stages=1,**kwargs)
    ns=dict(vars(old));ns.update(core=SimpleNamespace(prepare=compile_core),ROOT_PIN=root_pin,
        PINS={path:sha(ROOT/path) for path in ('reference/stream27_host_chain_param_v3.py',core.LEAF,'cloud/plain_fit_v2.py')})
    exec(compile(body,'[shared canonical flag physical source]','exec'),ns)
    if destination.exists():
        if (destination/'inventory.json').exists() or (destination/'variant.json').exists():
            raise ValueError('CANON_PIPE_FIT_ALREADY_CLOSED')
        # A source-only structural diagnostic may resume against the exact
        # unchanged prepared project; never overwrite its candidate bytes.
        saved=json.loads((destination/'project/manifest.json').read_text())
        if saved['source_sha256']!=b['generated_sha256'] or saved['compile_processors']!=workers:
            raise ValueError('CANON_PIPE_FIT_RESUME_SOURCE_DRIFT')
        for name,pin in {**{'rtl/'+k:v for k,v in saved['source_sha256'].items()},**saved['control_sha256']}.items():
            if sha(destination/'project'/name)!=pin:raise ValueError('CANON_PIPE_FIT_RESUME_PIN')
    else:
        ns['prepare'](destination,workers=workers)
    project=destination/'project';manifest=json.loads((project/'manifest.json').read_text())
    if manifest['source_sha256']!=b['generated_sha256']:raise ValueError('CANON_PIPE_FIT_GENERATOR_JOIN')
    # Reuse all frozen external transfer declarations, rebound to actual new
    # wrapper/leaf names and controls. Add the new internal register boundary.
    spec_text=(ROOT/BASE_INVENTORY).read_text()
    for before,after in (
        ('genefer_stream27_host_chain_aw16_p8_param_v1','genefer_stream27_host_chain_aw16_p8_canonreg_v1'),
        ('genefer_stream27_chain_canonical_aw16_p8_param_v1','genefer_stream27_chain_canonical_aw16_p8_canonreg_v1'),
        ('genefer_stream27_canonical_image_v1','genefer_stream27_canonical_image_pipe_v1')):
        spec_text=spec_text.replace(before,after)
    spec=json.loads(spec_text)
    spec['identity']=dict(top=manifest['top'],device=manifest['device'],parameters=manifest['core_parameters'],clock_period_ns=10,seed=1)
    spec['sources']={'rtl/'+name:pin for name,pin in manifest['source_sha256'].items()}
    spec['settings']={**manifest['control_sha256'],'manifest.json':sha(project/'manifest.json')}
    for transfer in spec['transfers']:
        for stage in transfer['registered_stages']:
            if 'scope_note' in stage:stage['scope_note']=stage['scope_note'].replace('6N/7N','9N/10N')
    spec['blocks'].append('canonical_value')
    spec['transfers'].append(dict(id='canonical_RAM_to_value_register',producer='canonical_image',consumer='canonical_value',
        signals=['RAM digit32','carry3','correction32','signed34 value','stored digit range'],registered_stages=[
            dict(id='canonical_RAM_q',owner='canonical_image',edge=0,source='rtl/genefer_sdp_ram32.sv',
                payload=['read_data'],valid='READ_WORD read_en',metadata=['address/bank/pass stable'],
                anchors=['(* ramstyle="M20K, no_rw_check" *) logic [31:0] mem [0:DEPTH-1];',
                    'if(rst_n && read_en) read_data<=mem[read_addr];'],kind='registered_ram_output',alignment='same_accepted_edge'),
            dict(id='canonical_value',owner='canonical_value',edge=1,source='rtl/genefer_stream27_canonical_image_pipe_v1.sv',
                payload=['value','stored_digit_bad'],valid='state VALUE_WORD transitions to PROCESS_WORD',
                metadata=['held address/pass/base/corrections/carry'],
                anchors=['value<=value_next;stored_digit_bad<=pass_index==0 && ram_q[bank]>=base_reg;', 'state<=PROCESS_WORD;'],
                kind='flop',alignment='same_accepted_edge')]))
    findings=source_inventory(project,spec)
    if findings['findings']:raise ValueError('CANON_PIPE_FIT_STRUCTURE:'+repr(findings['findings']))
    inventory=destination/'inventory.json';inventory.write_text(json.dumps(spec,indent=2)+'\n')
    profile='gfn16-azure-f16' if workers==4 else 'gfn16-aws-m8i'
    descriptor=variant_descriptor(project,profile,structural_spec=dict(path=str(inventory),sha256=sha(inventory)))
    variant=destination/'variant.json';variant.write_text(json.dumps(descriptor,indent=2)+'\n')
    return dict(status='PASS_source_ready_not_native_or_fit_qualified',project=str(project),inventory=str(inventory),variant=str(variant),
        standalone_rtl=49,root_sha256=root_pin,parameters=manifest['core_parameters'],workers=workers,
        native_required=NATIVE_REQUIRED,canonical_added_cycles=196608,warm_interval=16653,
        structural_transfers=len(spec['transfers']),findings=0,clock_claim=None)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,choices=(4,6),default=4)
    a=p.parse_args();print(json.dumps(prepare(a.output,workers=a.workers),indent=2))

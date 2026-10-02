"""Separate actual leaf faults with coherent issue metadata and rc41 control.

The complete field predictor/register is paired in normal roles; this role
checks the actual new leaf's origin/reset/stop authority, never delayed rows.
"""
import argparse,json
from pathlib import Path
from datetime import datetime,timezone
from . import stream27_term_lookahead_p16_bind as binding
from . import stream27_term_select_p16_diet_fault_native as donor
from . import stream27_term_select_native as base
from fpga.tools import native_class_package_v2 as package
ROOT=binding.ROOT
SELF='reference/stream27_term_lookahead_p16_fault_native.py'
TOP='genefer_stream27_term_lookahead_fault_pair_aw8_f1_v1'
CPP='rtl/tb/stream27_term_lookahead_p16_faults.cpp'
ID='s4-p16-term-lookahead-aw8-f1-faults-v1-q1'
def role():
    b=binding.prepare();info=b['term_lookahead'];m,oldfiles=donor.role();oldinfo=m['term_select']['binding']
    new=info['new_term'];diag=new+'_fault_probe_v1';term=b['files'][new+'.sv']
    term=binding.once(term,'module '+new+' #','module '+diag+' #')
    term=binding.once(term,'input logic clk,rst_n,quarantine,','input logic clk,rst_n,quarantine,debug_drop_select,')
    term=binding.once(term,'wire product_slot,product_error,product_pending,data_select_slot;',
        'wire product_slot,product_error,product_pending,data_select_slot,data_select_slot_raw;\n    assign data_select_slot=data_select_slot_raw && !debug_drop_select;')
    term=binding.once(term,'.data_select_slot(data_select_slot));','.data_select_slot(data_select_slot_raw));')
    term=binding.once(term,donor.binding.frozen.TERM_ASSERT,'')
    wrapper=oldfiles['rtl/'+donor.TOP+'.sv'].decode().replace(donor.TOP,TOP)
    wrapper=wrapper.replace(oldinfo['parent_term']+' #(',info['parent_term']+' #(')
    wrapper=wrapper.replace(oldinfo['new_term']+'_fault_probe_v1 #(',diag+' #(')
    # Direct leaf fault stimuli supply the current raw issue row/epoch even
    # when malformed; validators still read original owner/row at the origin.
    anchor='.pointwise_slot,.pointwise_start,.pointwise_owner,.pointwise_row,.next_coeff'
    need=binding.need;need(wrapper.count(anchor)==2,'TERM_LOOKAHEAD_FAULT_PAIR_CONNECTION')
    candidate=wrapper.index(' '+diag+' #(')
    wrapper=wrapper[:candidate]+wrapper[candidate:].replace(anchor,'.pointwise_slot,.pointwise_start,.pointwise_owner,.pointwise_row,.payload_epoch(pointwise_owner[23:8]),.payload_row(pointwise_row),.next_coeff',1)
    files={name:raw for name,raw in oldfiles.items() if not(name.startswith('rtl/') and name.endswith('.sv'))}
    files.update({'rtl/'+name:text.encode() for name,text in b['files'].items()})
    files['rtl/'+diag+'.sv']=term.encode();files['rtl/'+TOP+'.sv']=wrapper.encode()
    header=files[donor.oracle.HEADER].decode().replace('V'+donor.TOP,'V'+TOP);files[donor.oracle.HEADER]=header.encode()
    files[CPP]=files.pop(donor.CPP).decode().replace('S4_P16_DIET_TERM_SELECT','S4_TERM_LOOKAHEAD').encode()
    for name in b['source_dependencies']+[SELF,donor.SELF,donor.oracle.CPP]:files['lineage/'+name]=(ROOT/name).read_bytes()
    for step in m['steps']:
        step['name']='lookahead-'+step['name'];step['expected_stdout']=step['expected_stdout'].replace('S4_P16_DIET_TERM_SELECT','S4_TERM_LOOKAHEAD');step['expected_stderr']=step['expected_stderr'].replace('S4_P16_DIET_TERM_SELECT','S4_TERM_LOOKAHEAD')
    m.update(sources={name:base.sha(raw) for name,raw in files.items()},build=dict(top=TOP,sv_sources=[name for name in files if name.startswith('rtl/') and name.endswith('.sv')],cpp_source=CPP,parameters={},cflags=['-std=c++17','-O2','-Werror=return-type']),
        term_lookahead=dict(binding=info,scope='Actual new term leaf direct-weight/fullowner/malformed-row/origin/reset/stop pair with coherent current payload metadata; complete field predictor/register paired separately. Typed41 bypass mutation is simulation-only diagnostic, not a production pin.'),promotion_allowed=False)
    return m,files
def prepare(output,budget):
    output=Path(output).resolve();binding.need(not output.exists() and not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),'TERM_LOOKAHEAD_FAULT_FRESH_PAUSE')
    m,files=role();source=output/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    m.update(source_root=str(source),output_parent=str(output/'UNBOUND_OUTPUT'));base.dump(output/'manifest.json',m)
    packet=output/'packet-01';r=package.prepare(output/'manifest.json',source,'gcp-c4d-static01-v1',ID+'-01','run',packet,Path(budget).resolve())
    nt=json.loads((packet/'ticket.json').read_text());ticket=json.loads((ROOT/'results/throughput-20260929/trackS-warm-contexts-v1/aw5-p8-normal-v1/global-ticket.json').read_text())
    ticket.update(id=ID,candidate_id=ID,owner='p16-mlab',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),test_role='deliberate_fault',after=['s4-p16-term-lookahead-aw8-f1-v2-normal-q1'],source_gate=dict(scope=m['term_lookahead']['scope'],promotion_allowed=False));ticket.pop('rtl_readiness',None)
    ticket['packages'][0].update(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],manifest_sha256=nt['manifest_sha256'],worker_id=nt['id'],native_root=nt['native_root'])
    base.dump(output/'global-ticket.json',ticket);print(output/'global-ticket.json')
if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--output',type=Path,required=True);q.add_argument('--budget',type=Path,required=True);a=q.parse_args();prepare(a.output,a.budget)

"""Private FF/MLAB term unit normal first; copied actual arithmetic closure."""
import argparse
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
from . import stream27_context_term_mlab_bind as binding

ROOT=binding.ROOT
SELF='reference/stream27_context_term_mlab_native.py'
CPP='rtl/tb/stream27_term_payload_mlab_pair.cpp'
TOP='genefer_stream27_term_payload_mlab_pair_v1'
NORMAL='TERM_MLAB_PAIR_PASS frames=40 lane_words=10240 pre_post=1 bypass=480 contexts=2 epoch_wrap=1 latency_delta=0\n'


def wrapper():
    names=('clk','rst_n','quarantine','seed_slot','seed_start','seed_owner','seed_row','seed_coeff','seed_R_roots',
        'pointwise_slot','pointwise_start','pointwise_owner','pointwise_row','next_coeff','next_seed_R_roots','update_R_factor')
    text='''module genefer_stream27_term_payload_mlab_pair_v1 (
 input logic clk,rst_n,quarantine,seed_slot,seed_start,
 input logic [26:0] seed_owner,pointwise_owner,
 input logic [1:0] seed_row,
 input logic [431:0] seed_coeff,seed_R_roots,next_coeff,next_seed_R_roots,
 input logic pointwise_slot,pointwise_start,
 input logic [3:0] pointwise_row,
 input logic [26:0] update_R_factor,
 output wire [431:0] old_term_data,new_term_data,old_current,new_current,
 output wire [26:0] old_term_owner,new_term_owner,old_cache_owner,new_cache_owner,
 output wire [3:0] old_term_row,new_term_row,
 output wire [4:0] old_status,new_status,
 output wire old_bypass,new_bypass
);
'''
    for label,module in (('old',binding.TERM),('new',binding.NEW)):
        text+=' wire '+label+'_slot,'+label+'_start,'+label+'_cache,'+label+'_error,'+label+'_pending;\n'
        ports=['.'+n for n in names]+['.term_slot('+label+'_slot)', '.term_start('+label+'_start)',
            '.term_owner('+label+'_term_owner)', '.term_row('+label+'_term_row)', '.term_data('+label+'_term_data)',
            '.cache_ready('+label+'_cache)', '.cache_owner('+label+'_cache_owner)', '.out_error('+label+'_error)',
            '.fault_pending('+label+'_pending)']
        text+=' '+module+' #(.AW(8),.LANES(16)) '+label+'_leaf ('+', '.join(ports)+');\n'
        text+=' assign '+label+'_status={'+', '.join(label+'_'+s for s in ('pending','error','cache','start','slot'))+'};\n'
        text+=' assign '+label+'_current='+label+'_leaf.current_term;\n assign '+label+'_bypass='+label+'_leaf.bypass;\n'
    return text+'endmodule\n'


def role(mode='normal'):
    binding.captured.need(mode in ('normal','faults'),'TERM_MLAB_ROLE')
    from . import stream27_context_storage_banks_fault as captured_fault
    manifest,files=captured_fault.role('oracle')
    _,_,parent=binding.captured.capture('aw8');parent=binding.captured.binder.bind(parent,enabled=1)
    candidate=binding.bind(parent,enabled=1)
    # Unit includes both frozen FF and new term, actual unchanged multiplier
    # definitions/parameters. Unused field/host modules are source assets only.
    files['rtl/'+binding.NEW+'.sv']=candidate['files'][binding.NEW+'.sv'].encode()
    files['rtl/'+binding.RAM+'.sv']=candidate['files'][binding.RAM+'.sv'].encode()
    files['rtl/'+TOP+'.sv']=wrapper().encode();files[CPP]=(ROOT/CPP).read_bytes()
    for name in (binding.SELF,SELF):files['lineage/'+name]=(ROOT/name).read_bytes()
    sv=['rtl/'+name for name in (binding.TERM+'.sv',binding.NEW+'.sv',binding.RAM+'.sv',
        'genefer_stream27_row_arithmetic_param_v1.sv','genefer_montgomery_mul27_sparse_pipe.sv',TOP+'.sv')]
    binding.captured.need(all(name in files for name in sv),'TERM_MLAB_ACTUAL_UNIT_CLOSURE')
    manifest['build'].update(top=TOP,sv_sources=sv,cpp_source=CPP,parameters={})
    footer=NORMAL if mode=='normal' else NORMAL*2+'TERM_MLAB_FAULT_PASS missing_cache=1 bad_seed=1 in_flight_reset=1 quiet_edges=24 recovered_lane_words=10240 raw_pending_lockstep=1\n'
    manifest['steps']=[dict(name='term-mlab-'+mode,argv=['{exe}']+([] if mode=='normal' else ['--faults']),
        expected_returncode=0,expected_stdout=footer,expected_stderr='')]
    manifest['sources']={name:binding.captured.sha(data) for name,data in files.items()}
    manifest['test_role']='normal' if mode=='normal' else 'deliberate_fault'
    manifest['term_mlab_unit']=dict(source_parent='actual clean storage2 FF term',parent_sha256=binding.sha(parent['files'][binding.TERM+'.sv']),
        candidate_sha256=binding.sha(candidate['files'][binding.NEW+'.sv']),ram_sha256=binding.sha(candidate['files'][binding.RAM+'.sv']),
        ordinary_scalar_reference=True,asynchronous_PRE_POST_reads=True,registered_latency_delta=0,
        whole_integration_qualified=False,inferred_MLAB_credit=False,promotion_allowed=False)
    return manifest,files


def prepare(output,mode='normal'):
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    out=Path(output).resolve();binding.captured.need(out.is_relative_to(ROOT) and not out.exists(),'TERM_MLAB_FRESH')
    binding.captured.need(not any((ROOT/x).exists() for x in ('queue/PAUSE','docs/briefs/PAUSE')),'TERM_MLAB_PAUSE')
    manifest,files=role(mode);source=out/'source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(data)
    manifest['source_root']=str(source);binding.captured.dump(out/'manifest.json',manifest)
    binding.captured.dump(out/'host-hours.json',candidate_ladder.budget_from_hourly())
    from . import stream27_context_storage_banks_fault as captured_fault
    template=json.loads((captured_fault.NORMAL/'global-ticket.json').read_text());variants=[]
    identifier='s4-p16-c2-term-mlab-unit-'+mode+'-q1-v1'
    for pair,old in zip(('01','23'),template['packages']):
        worker='s4-p16-c2-term-mlab-'+mode+'-'+pair+'-v1';packet=out/('packet-'+pair)
        r=package.prepare(out/'manifest.json',source,old['profile'],worker,'run',packet,out/'host-hours.json')
        t=json.loads((packet/'ticket.json').read_text());v=copy.deepcopy(old)
        v.update(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
            manifest_sha256=binding.captured.sha((packet/'manifest.json').read_bytes()),worker_id=worker,native_root=t['native_root'])
        variants.append(v)
    logical={k:copy.deepcopy(template[k]) for k in ('schema','owner','priority','kind','needs','tool_identity','resources',
        'minimum_ram_gib','minimum_ram_rationale','est_minutes','promotion_bound')}
    logical.update(id=identifier,created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),test_role=manifest['test_role'],packages=variants)
    if mode=='faults':logical.update(after=['s4-p16-c2-term-mlab-unit-normal-q1-v1'],on='PASS_expected_contracts')
    binding.captured.dump(out/'global-ticket.json',logical)
    return dict(id=identifier,ticket=str(out/'global-ticket.json'),status='prepared_not_native')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('normal','faults'),default='normal');a=p.parse_args()
    print(json.dumps(prepare(a.output,a.mode),indent=2))

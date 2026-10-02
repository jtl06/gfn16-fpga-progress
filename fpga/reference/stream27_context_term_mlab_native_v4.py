"""Explicit reset-write unit successor with actual simultaneous-edge check."""
import argparse
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
from . import stream27_context_term_mlab_native_v3 as base
from . import stream27_context_term_mlab_bind_v2 as binding

ROOT=binding.ROOT
SELF='reference/stream27_context_term_mlab_native_v4.py'
NORMAL_ID='s4-p16-c2-term-mlab-unit-normal-q1-v4'


def role(mode='normal'):
    m,files=base.role(mode);old=base.parent
    files['rtl/'+binding.NEW+'.sv']=binding.term(files['rtl/'+binding.TERM+'.sv'].decode()).encode()
    wrapper=files['rtl/'+old.TOP+'.sv'].decode()
    wrapper=binding.captured.binder.parent.once(wrapper,
        ' output wire old_bypass,new_bypass\n',
        ' output wire old_bypass,new_bypass,debug_old_write,debug_new_write,debug_product_slot,\n output wire [26:0] debug_product_owner,\n output wire [3:0] debug_product_row\n')
    wrapper=binding.captured.binder.parent.once(wrapper,'endmodule\n',
        ''' assign debug_old_write=rst_n && !old_leaf.stop && old_leaf.product_slot && old_leaf.bank_owner[old_leaf.prod_bank]==old_leaf.product_owner;
 assign debug_new_write=new_leaf.payload_write;
 assign debug_product_slot=old_leaf.product_slot;
 assign debug_product_owner=old_leaf.product_owner;
 assign debug_product_row=old_leaf.product_row;
endmodule
''')
    files['rtl/'+old.TOP+'.sv']=wrapper.encode()
    cpp=files[old.CPP].decode().replace('#include <cstdint>','#include <cstdint>\n#include <array>')
    cpp=binding.captured.binder.parent.once(cpp,'static void faults(DUT& d){',
        '''static void simultaneous_reset(DUT& d){
    reset(d);uint32_t owner=(65534u<<8)|1u;
    for(unsigned row=0;row<4;row++){
        clear(d);d.seed_slot=1;d.seed_start=row==0;d.seed_row=row;d.seed_owner=owner;
        for(unsigned lane=0;lane<LANES;lane++){lane_set(d.seed_coeff,lane,coeff(99,row,lane));lane_set(d.seed_R_roots,lane,R);}
        edge(d);
    }
    clear(d);d.pointwise_owner=owner^1u;d.pointwise_row=d.debug_product_row;d.clk=0;d.eval();
    need(d.debug_product_slot&&d.debug_old_write&&d.debug_new_write&&!d.old_bypass&&!d.new_bypass,"TERM_MLAB_SIMULT_RESET_REAL_WRITE_PENDING");
    std::array<uint32_t,LANES> before{};
    for(unsigned lane=0;lane<LANES;lane++){before[lane]=lane_get(d.old_current,lane);need(before[lane]==lane_get(d.new_current,lane),"TERM_MLAB_SIMULT_RESET_BASELINE");}
    d.rst_n=0;d.clk=1;d.eval();
    need(!d.debug_old_write&&!d.debug_new_write&&!(d.old_status&13u)&&!(d.new_status&13u),"TERM_MLAB_SIMULT_RESET_WRITE_BLOCKED");
    for(unsigned lane=0;lane<LANES;lane++)need(lane_get(d.old_current,lane)==before[lane]&&lane_get(d.new_current,lane)==before[lane],"TERM_MLAB_SIMULT_RESET_NUMERIC_RETENTION");
    d.rst_n=1;for(unsigned q=0;q<8;q++){clear(d);edge(d);need(!(d.old_status&13u),"TERM_MLAB_SIMULT_RESET_QUIET");}
}
static void faults(DUT& d){''')
    cpp=binding.captured.binder.parent.once(cpp,'    reset(d);frame(d,0,3);normal(d);',
        '    reset(d);frame(d,0,3);simultaneous_reset(d);normal(d);')
    cpp=cpp.replace('quiet_edges=24 recovered_lane_words=10240 raw_pending_lockstep=1',
        'quiet_edges=32 recovered_lane_words=10240 raw_pending_lockstep=1 simultaneous_reset_write_hold=1')
    files[old.CPP]=cpp.encode()
    for name in (binding.SELF,SELF):files['lineage/'+name]=(ROOT/name).read_bytes()
    m['sources']={name:binding.captured.sha(raw) for name,raw in files.items()}
    if mode=='faults':m['steps'][0]['expected_stdout']=m['steps'][0]['expected_stdout'].replace(
        'quiet_edges=24 recovered_lane_words=10240 raw_pending_lockstep=1',
        'quiet_edges=32 recovered_lane_words=10240 raw_pending_lockstep=1 simultaneous_reset_write_hold=1')
    m['term_mlab_unit'].update(candidate_sha256=binding.sha(files['rtl/'+binding.NEW+'.sv'].decode()),
        explicit_reset_ELSE_write_guard=True,actual_simultaneous_reset_numeric_hold=True,
        preserved_predecessor_units=True)
    return m,files


def prepare(output,mode='normal'):
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    out=Path(output).resolve();binding.captured.need(out.is_relative_to(ROOT) and not out.exists(),'MLAB_V4_FRESH')
    binding.captured.need(not any((ROOT/x).exists() for x in ('queue/PAUSE','docs/briefs/PAUSE')),'MLAB_V4_PAUSE')
    manifest,files=role(mode);source=out/'source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(data)
    manifest['source_root']=str(source);binding.captured.dump(out/'manifest.json',manifest)
    binding.captured.dump(out/'host-hours.json',candidate_ladder.budget_from_hourly())
    from . import stream27_context_storage_banks_fault as captured_fault
    template=json.loads((captured_fault.NORMAL/'global-ticket.json').read_text());variants=[]
    identifier='s4-p16-c2-term-mlab-unit-'+mode+'-q1-v4'
    for pair,old in zip(('01','23'),template['packages']):
        worker='s4-p16-c2-term-mlab-'+mode+'-'+pair+'-v4';packet=out/('packet-'+pair)
        r=package.prepare(out/'manifest.json',source,old['profile'],worker,'run',packet,out/'host-hours.json')
        t=json.loads((packet/'ticket.json').read_text());v=copy.deepcopy(old)
        v.update(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
            manifest_sha256=binding.captured.sha((packet/'manifest.json').read_bytes()),worker_id=worker,native_root=t['native_root'])
        variants.append(v)
    logical={k:copy.deepcopy(template[k]) for k in ('schema','owner','priority','kind','needs','tool_identity','resources',
        'minimum_ram_gib','minimum_ram_rationale','est_minutes','promotion_bound')}
    logical.update(id=identifier,created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),test_role=manifest['test_role'],packages=variants)
    if mode=='faults':logical.update(after=[NORMAL_ID],on='PASS_expected_contracts')
    binding.captured.dump(out/'global-ticket.json',logical)
    return dict(id=identifier,ticket=str(out/'global-ticket.json'),status='prepared_not_native')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('normal','faults'),default='normal');a=p.parse_args()
    print(json.dumps(prepare(a.output,a.mode),indent=2))

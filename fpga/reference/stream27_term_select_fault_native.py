"""Actual P16 term/root diagnostic pair after the corr2 field normal gate.

The production leaf/binding stays unchanged. A unique diagnostic successor
adds only a masked data-selector token for the typed mutant. Real root ROM,
frozen sparse Montgomery and original qualified control/term producer are
compiled. This is a component fault theorem, not a whole engine clone.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from . import stream27_term_select_native as normal
from . import stream27_term_select_bind as binding
from . import stream27_shared_field_flags as donor
from .stream_ntt_model import FIELDS

ROOT=normal.ROOT
SELF='reference/stream27_term_select_fault_native.py'
CPP='rtl/tb/stream27_term_select_faults.cpp'
HEADER='rtl/tb/s4_term_select_fault_config.h'
TOP='genefer_stream27_term_select_pair_aw8_p16_f1_v1'
ID='s4-p16-term-select-aw8-f1-c2-faults-q1-v1'
NORMAL_ID='s4-p16-term-select-aw8-f1-c2-normal-q1-v1'
need,sha,dump=normal.need,normal.sha,normal.dump


def role():
    parent=donor.prepare(256,16,1,mode='warm_signed',corr_serial_bfs=2)
    b=binding.bind(parent);info=b['term_select'];old=info['parent_term'];new=info['new_term']
    term=b['files'][new+'.sv'];diag=new+'_fault_probe_v1'
    term=binding.once(term,'module '+new+' #','module '+diag+' #')
    term=binding.once(term,'input logic clk,rst_n,quarantine,','input logic clk,rst_n,quarantine,debug_drop_select,')
    term=binding.once(term,'wire product_slot,product_error,product_pending,data_select_slot;',
                      'wire product_slot,product_error,product_pending,data_select_slot,data_select_slot_raw;\n'
                      '    assign data_select_slot=data_select_slot_raw && !debug_drop_select;')
    term=binding.once(term,'.data_select_slot(data_select_slot));','.data_select_slot(data_select_slot_raw));')
    # Production assertion stays captured in lineage; the diagnostic mutation
    # is detected by the independent value oracle with a typed nonzero exit.
    term=binding.once(term,binding.TERM_ASSERT,'')
    roots=[name for name in parent['files'] if name.startswith('genefer_stream27_shared_term_roots_')]
    need(len(roots)==1,'TERM_SELECT_REAL_ROOT_LEAF');root=roots[0][:-3]
    width=16*27
    ports='''module '''+TOP+''' (
 input logic clk,rst_n,quarantine,debug_drop_select,seed_slot,seed_start,
 input logic [23:0] seed_owner,
 input logic [1:0] seed_row,
 input logic [431:0] seed_coeff,next_coeff,
 input logic pointwise_slot,pointwise_start,
 input logic [23:0] pointwise_owner,
 input logic [3:0] pointwise_row,
 output logic term_slot,term_start,cache_ready,out_error,fault_pending,
 output logic [23:0] term_owner,cache_owner,
 output logic [3:0] term_row,
 output logic [431:0] term_data,
 output logic parent_term_slot,parent_term_start,parent_cache_ready,parent_out_error,parent_fault_pending,
 output logic [23:0] parent_term_owner,parent_cache_owner,
 output logic [3:0] parent_term_row,
 output logic [431:0] parent_term_data,
 output logic monitor_data_select,monitor_product_slot,monitor_data_bypass);
 wire [431:0] seed_R_roots,next_seed_R_roots;
 wire [26:0] update_R_factor;
 '''+root+''' term_roots (
  .clk,.rst_n,.seed_slot,.seed_start,.pw_slot(pointwise_slot),.pw_start(pointwise_start),
  .seed_row,.pw_row(pointwise_row),.seed_R_roots,.next_seed_R_roots,.update_R_factor);
'''
    prime,g=FIELDS[1];q=(2-prime)%(1<<32)
    common='''  .clk,.rst_n,.quarantine,.seed_slot,.seed_start,.seed_owner,.seed_row,.seed_coeff,.seed_R_roots,
  .pointwise_slot,.pointwise_start,.pointwise_owner,.pointwise_row,.next_coeff,.next_seed_R_roots,.update_R_factor,
'''
    params=f" #(.AW(8),.LANES(16),.P(32'd{prime}),.Q(32'd{q})) "
    top=ports+' '+old+params+'parent_term (\n'+common+'''  .term_slot(parent_term_slot),.term_start(parent_term_start),.term_owner(parent_term_owner),.term_row(parent_term_row),
  .term_data(parent_term_data),.cache_ready(parent_cache_ready),.cache_owner(parent_cache_owner),
  .out_error(parent_out_error),.fault_pending(parent_fault_pending));
 '''+diag+params+'candidate (\n'+common+'''  .debug_drop_select,.term_slot,.term_start,.term_owner,.term_row,.term_data,.cache_ready,.cache_owner,.out_error,.fault_pending);
 assign monitor_data_select=candidate.data_select_slot;
 assign monitor_product_slot=candidate.product_slot;
 assign monitor_data_bypass=candidate.bypass_data;
endmodule
'''
    names=(old+'.sv','genefer_stream27_row_arithmetic_param_v1.sv','genefer_montgomery_mul27_sparse_pipe.sv',roots[0])
    files={'rtl/'+name:parent['files'][name].encode() for name in names}
    files.update({'rtl/'+diag+'.sv':term.encode(),'rtl/'+Path(binding.LEAF).name:(ROOT/binding.LEAF).read_bytes(),
                  'rtl/'+TOP+'.sv':top.encode(),CPP:(ROOT/CPP).read_bytes(),
                  HEADER:(f'#include "V{TOP}.h"\nusing DUT=V{TOP};\n'
                          f'constexpr unsigned N=256,LANES=16,LANE_BITS=4,ROWS=16,ROW_BITS=4,WORDS=14,PW_FIRST=10,PRIME={prime},GENERATOR={g};\n').encode()})
    for name in b['source_dependencies']+[SELF,CPP,normal.SELF]:files['lineage/'+name]=(ROOT/name).read_bytes()
    footer='S4_TERM_SELECT_FAULT_PASS aw=8 p=16 field=1 cases=13 normal_frames=6 normal_rows=96 normal_words=1536 genuine_faults=4 legal_origin_terms=1 reset_aborts=2 quarantine_windows=1 stopped_selection_seen=1 quiet_tail=16\n'
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/unbound/term-select-fault/fpga',output_parent='/unbound/term-select-fault/output',
        sources={name:sha(raw) for name,raw in files.items()},
        build=dict(top=TOP,sv_sources=[name for name in files if name.startswith('rtl/') and name.endswith('.sv')],
                   cpp_source=CPP,parameters={},cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='p16-term-selector-direct-math-genuine-fault-reset',argv=['{exe}'],expected_returncode=0,
                    expected_stdout=footer,expected_stderr=''),
               dict(name='p16-term-selector-bypass-typed-mutant',argv=['{exe}','--negative-bypass'],expected_returncode=41,
                    expected_stdout=footer,expected_stderr='S4_TERM_SELECT_TYPED_BYPASS row=4 lane=0 direct-mismatch\n')],
        test_role='deliberate_fault',term_select=dict(binding=info,production_geometry=b['geometry'],
            direct_oracle='Ordinary modular coefficient times independently exponentiated negacyclic root; actual ROM and sparse Montgomery',
            scope='P16 real component/full24owner, exact parent qualified outputs, four-cycle bypass, genuine bubble/owner/row/collision, async reset and quarantine; no whole error/physical qualification.'),
        lint_baseline_policy='Fresh class-gated lint; no unknown warning/defect waiver.')
    return m,files


def prepare(output,budget):
    from fpga.tools import native_class_package_v2 as package
    output=Path(output).resolve()
    need(not output.exists() and not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),'TERM_SELECT_FAULT_FRESH_PAUSE')
    m,files=role();source=output/'input/source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    manifest=output/'input/manifest.json';dump(manifest,m)
    profile='gcp-c4d-static01-v1';worker=ID+'-01';packet=output/'packet-01'
    r=package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve())
    variant=dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],
        ticket_sha256=r['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),native_root=r['native_root'],
        runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
        stager=str(ROOT/'tools/native_package_v3.py'),stager_sha256=sha((ROOT/'tools/native_package_v3.py').read_bytes()),
        stager_dependencies=[dict(path=str(ROOT/'tools/native_package_v2.py'),sha256=sha((ROOT/'tools/native_package_v2.py').read_bytes()))],max_seconds=3700)
    ticket=dict(schema='gfn16-global-ticket-v1',id=ID,owner='term-select',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
        minimum_ram_rationale='Bounded actual P16 term/root pair under existing4GiB envelope, no measured peak claim.',
        est_minutes=10,promotion_bound=False,test_role='deliberate_fault',packages=[variant],after=[NORMAL_ID],on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',ticket)
    return dict(status='fault_source_prepared_not_submitted',id=ID,ticket=str(output/'global-ticket-v1.json'),manifest_sha256=sha(manifest.read_bytes()))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--budget',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.budget),indent=2))

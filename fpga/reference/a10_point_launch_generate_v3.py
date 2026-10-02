"""Measured mul_lhs RAM cone successor; one extra pointwise launch edge only."""
import hashlib
import json
from pathlib import Path
from fpga.reference import a10_lint_repair_v2 as parent
from fpga.reference import a10_engine_geometry_gates_v1 as math

ROOT=parent.ROOT
TARGET='rtl/kernel/genefer_a10_banked27_engine_pointlaunch_v3.sv'
LEDGER='results/throughput-20260929/a10-aw16-registered-aws-plain-v1/path-ledger-v1.json'
LEDGER_SHA='275d37132f3906833d4428e16c0a8b6e0f69a2b1761ebd55a47a1efa0b9dc42b'
FITTED='results/throughput-20260929/a10-aw16-registered-aws-plain-v1/project/rtl/genefer_a10_banked27_engine_lint_v2.sv'
PARENT_SHA='3f50001119f0ca672fa19f89f209765d0a4140abcd963b18107d4a407eebec16'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def source_parent():
    parent.need(sha((ROOT/FITTED).read_bytes())==PARENT_SHA and sha((ROOT/LEDGER).read_bytes())==LEDGER_SHA,'A10_POINT_NATIVE_SOURCE_LEDGER_PIN')
    original=(ROOT/parent.ENGINE_V1).read_text();fixed=parent.engine_source(original)
    parent.need(fixed==(ROOT/FITTED).read_text(),'A10_POINT_EXACT_FITTED_PARENT')
    ledger=json.loads((ROOT/LEDGER).read_text())
    parent.need(ledger['top']=='genefer_a10_registered_field_probe_v1' and ledger['target_period_ns']==8 and
        ledger['setup']['native_sample_count']==10 and ledger['setup']['native_violated_count']==10 and
        all(any('mul_lhs' in node['element'] for node in path['observed_data_cone']) for path in ledger['setup']['paths']),
        'A10_POINT_MEASURED_MUL_LHS_CONE')
    return fixed


def changes():
    return [
        ('logic [6:0] point_half_pipe;','logic [7:0] point_half_pipe;'),
        ('logic shared_valid;','logic shared_valid,point_launch_valid;\n        (* preserve,dont_merge *) logic [31:0] point_lhs_q;'),
        ('assign mul_lhs=point_half_d ? data_q[lane+LANES] : data_q[lane];',
         'assign mul_lhs=point_lhs_q;\n        // Raw RAM response E1 -> registered point operand -> BF accept E2.\n        always_ff @(posedge clk)if(rst_n && mul_in_valid[lane])\n            point_lhs_q<=point_half_d ? data_q[lane+LANES] : data_q[lane];'),
        ('.in_valid(bf_in_valid[lane] || mul_in_valid[lane]),','.in_valid(bf_in_valid[lane] || point_launch_valid),'),
        ("if(!rst_n)point_type_pipe<=0;\n            else point_type_pipe<={point_type_pipe[4:0],mul_in_valid[lane]};",
         "if(!rst_n)begin point_type_pipe<=0;point_launch_valid<=0;end\n            else begin\n                point_launch_valid<=mul_in_valid[lane];\n                point_type_pipe<={point_type_pipe[4:0],point_launch_valid};\n            end"),
        ("1'(bank/LANES)==point_half_pipe[6]","1'(bank/LANES)==point_half_pipe[7]"),
        ('data_we[bank]=1;data_wa[bank]=row_tag[6][bank];data_w[bank]=product[bank%LANES];',
         'data_we[bank]=1;data_wa[bank]=row_tag[7][bank];data_w[bank]=product[bank%LANES];'),
        ('point_half_pipe<={point_half_pipe[5:0],point_half};','point_half_pipe<={point_half_pipe[6:0],point_half};')]


def source():
    original=source_parent();result=original
    for old,new in changes():
        parent.need(result.count(old)==1,'A10_POINT_ONE_SITE '+old);result=result.replace(old,new)
    restored=result
    for old,new in reversed(changes()):
        parent.need(restored.count(new)==1,'A10_POINT_RESTORE_SITE');restored=restored.replace(new,old)
    parent.need(restored==original,'A10_POINT_ONLY_LAUNCH_AND_POINT_TAGS')
    return result.rstrip()+'\n'  # Normalize only the parent's spare EOF blank.


def ledger(aw):
    result=dict(math.ledger(aw));result['point_cycles']+=1;result['engine_work_cycles']+=5;result['whole_controller_ntt_cycles']+=1
    result.update(point_read_to_write_edges=8,point_RAM_response_to_launch_register=1,
        transform_read_to_write_edges=8,external_host_block_read_ABI_unchanged=True,
        status='source_prediction_native_required',delta='Pointoperand+valid launch; pointrow/bank tags+1. BF/root/profile/arithmetic unchanged.',
        extra_payload_bits_per_field=64*32,extra_valid_bits_per_field=64,physical_clock_promotion=False)
    return result

"""F3 measured RAM-write route cut, one internal write/drain edge per phase.

All arithmetic/root/profile/idle host logic stays exact upper-sum parent. The
bank-local bundle captures selected data, row and enable together. Completion
counts physical commits, not enqueue. This is not a hold-path RTL remedy.
"""
import argparse
import hashlib
import json
from pathlib import Path
from fpga.reference import a10_upper_sum_generate_v2 as upper
from fpga.reference import a10_point_launch_generate_v3 as point

ROOT = upper.ROOT
PARENT = upper.ENGINE
PARENT_SHA = '03f3e395cccac6e17979f7990bc12095675e264afa08a884a77100aa3f3cb273'
TARGET = 'rtl/kernel/genefer_a10_banked27_engine_writeback_v1.sv'
HOST = 'rtl/kernel/genefer_a10_banked27_host16_engine_v1.sv'
HOST_SHA = 'e430a6ea603fa83909f1c7d732f2610f8f5c5ad764718e5a61f4b07ef14dd6e1'
NATIVE_HOST = 'rtl/tb/genefer_a10_writeback_host_probe_v1.sv'
CPP_PARENT = 'rtl/tb/a10_point_launch_geometry_v4.cpp'
CPP_PARENT_SHA = '277b224d6e1dde7718d47d2338d0ec7f48a0f4bc92790dffa37319b2cb361dd9'
CPP = 'rtl/tb/a10_writeback_geometry_v1.cpp'
MEASURED = 'results/throughput-20260929/a10-upper-field-fit-consumption-v2/path-ledger-v2.json'
MEASURED_SHA = '4d19e0c0452fd52bc0fe1e15af2f30668eff128f8d035519c6a3f2d2b9d73b5c'
RECEIPT = 'queue/fit-r54-controller-v9/terminal/a10-upper-sum-sizing/receipt.json'
RECEIPT_SHA = '1eec3912a8f84f18166a78f3cdbe40ae729406025bdfbacb859c83ec82cde3be'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source_guard():
    for name, pin in ((PARENT,PARENT_SHA),(HOST,HOST_SHA),(CPP_PARENT,CPP_PARENT_SHA),
                      (MEASURED,MEASURED_SHA),(RECEIPT,RECEIPT_SHA)):
        upper.need(sha((ROOT/name).read_bytes()) == pin, 'A10_F3_EXACT_PARENT_MEASUREMENT '+name)
    measured = json.loads((ROOT/MEASURED).read_text())
    upper.need(measured['source_manifest_sha256'] == '711fd3a733e90bf5ab1a9c12175ac9d757e76bfe75e854a86184fcd36cf95787' and
               all('.data_ram|' in row['destination'] for row in measured['setup']['paths']) and
               any('bf_write_option' in row['element'] for row in measured['setup']['paths'][0]['observed_data_cone']) and
               any('|data_w[' in row['element'] for row in measured['setup']['paths'][0]['observed_data_cone']),
               'A10_F3_ACTUAL_RAM_WRITE_CONE')


def transform(text, changes):
    result = text
    for old, new in changes:
        upper.need(result.count(old) == 1, 'A10_F3_SINGLE_LITERAL_SITE '+old[:80])
        result = result.replace(old, new)
    restored = result
    for old, new in reversed(changes):
        upper.need(restored.count(new) == 1, 'A10_F3_SINGLE_REVERSE_SITE')
        restored = restored.replace(new, old)
    upper.need(restored == text, 'A10_F3_ONLY_LITERAL_DELTA')
    return result


BANK_LAUNCH = '''        // F3: raw output at E8 enqueues one bank-local bundle; RAM commits E9.
        // Host/vector IDLE writes retain their original immediate RAM edge.
        (* preserve,dont_merge *) logic write_launch_valid;
        (* preserve,dont_merge *) logic [RW-1:0] write_launch_row;
        (* preserve,dont_merge *) logic [31:0] write_launch_word;
        logic ram_write_en;
        logic [RW-1:0] ram_write_addr;
        logic [31:0] ram_write_data;
        assign writeback_pending_mask[bank]=write_launch_valid;
        assign ram_write_en=state==IDLE ? data_we[bank] :
            ((state==BF_READ || state==BF_DRAIN || state==MUL_READ || state==MUL_DRAIN) &&
             !writeback_cancel && write_launch_valid);
        assign ram_write_addr=state==IDLE ? data_wa[bank] : write_launch_row;
        assign ram_write_data=state==IDLE ? data_w[bank] : write_launch_word;
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)write_launch_valid<=0;
            else write_launch_valid<=busy && !writeback_cancel && data_we[bank];
        end
        // Payload is retained on reset; eligibility alone controls publication.
        always_ff @(posedge clk)if(rst_n && busy && !writeback_cancel && data_we[bank])begin
            write_launch_row<=data_wa[bank];write_launch_word<=data_w[bank];
        end
'''


def changes():
    return (
        ('// SOURCE-ONLY additive A10 canonical fixed-ROM engine; G4 host/data geometry retained.',
         '// Additive F3 bank-local internal write launch; arithmetic/host ABI unchanged, drain+1 per phase.'),
        ('    logic [LANES-1:0] bf_in_valid,mul_in_valid,bf_valid,mul_valid,arith_error;',
         '    logic [LANES-1:0] bf_in_valid,mul_in_valid,bf_valid,mul_valid,arith_error;\n'
         '    logic bf_writeback_valid,mul_writeback_valid,writeback_cancel;\n'
         '    logic [BANKS-1:0] writeback_pending_mask;\n'
         '    assign writeback_cancel=profile_request || profile_error || lookup_error || (|arith_error);'),
        ('        genefer_sdp_ram32 #(.AW(RW),.DEPTH(DEPTH)) data_ram (',
         BANK_LAUNCH+'        genefer_sdp_ram32 #(.AW(RW),.DEPTH(DEPTH)) data_ram ('),
        ('.read_en(data_re[bank]),.write_en(data_we[bank]),\n            .read_addr(data_ra[bank]),.write_addr(data_wa[bank]),\n            .write_data(data_w[bank])',
         '.read_en(data_re[bank]),.write_en(ram_write_en),\n            .read_addr(data_ra[bank]),.write_addr(ram_write_addr),\n            .write_data(ram_write_data)'),
        ('if(data_we[bank] && data_w[bank]>=P)', 'if(ram_write_en && ram_write_data>=P)'),
        ('if(data_re[bank] && data_we[bank] && data_ra[bank]==data_wa[bank])',
         'if(data_re[bank] && ram_write_en && data_ra[bank]==ram_write_addr)'),
        ('            bf_read_delay<=0;bf_in_valid<=0;mul_in_valid<=0;issue_tag_d<=0;issue_tag_destination<=0;',
         '            bf_read_delay<=0;bf_in_valid<=0;mul_in_valid<=0;issue_tag_d<=0;issue_tag_destination<=0;\n'
         '            bf_writeback_valid<=0;mul_writeback_valid<=0;'),
        ('            done<=0;\n',
         '            done<=0;\n'
         '            // These registered frame tokens count actual RAM commits, not enqueue.\n'
         '            bf_writeback_valid<=busy && !writeback_cancel && (state==BF_READ || state==BF_DRAIN) && bf_valid[0];\n'
         '            mul_writeback_valid<=busy && !writeback_cancel && (state==MUL_READ || state==MUL_DRAIN) && mul_valid[0];\n'),
        ('if((state==BF_READ || state==BF_DRAIN) && bf_valid[0])begin',
         'if((state==BF_READ || state==BF_DRAIN) && bf_writeback_valid && !writeback_cancel)begin'),
        ('if((state==MUL_READ || state==MUL_DRAIN) && mul_valid[0])begin',
         'if((state==MUL_READ || state==MUL_DRAIN) && mul_writeback_valid && !writeback_cancel)begin'))


def source():
    source_guard()
    return transform((ROOT/PARENT).read_text(), changes())


def native_host_source():
    source_guard()
    return transform((ROOT/HOST).read_text(), (
        ('// SOURCE-ONLY exact G4 host adapter delta; explicit format3 abort/metrics.',
         '// Native-only F3 observability wrapper; parent host routing/ABI otherwise exact.'),
        ('    output logic busy,done,error,', '    output logic busy,done,error,writeback_pending,'),
        ('    // synthesis translate_off\n    initial if(AW<1',
         '    assign writeback_pending=|child.writeback_pending_mask;\n    // synthesis translate_off\n    initial if(AW<1')))


CANCEL_CASES = r'''        // F3-specific cancellation at an ACTUAL pending bundle, before first RAM commit.
        // RAM equality, quiet tails and full reload/recovery are checked, not just flags.
        unsigned pending_cancels=0;uint64_t recovery_cycles=0;
        for(unsigned phase=0;phase<2;++phase)for(unsigned method=0;method<2;++method){
            load_header();std::vector<uint32_t> original(N,17);
            idle(d);for(unsigned k=0;k<N;k+=16){d.vector_load_we=1;d.vector_addr=k;d.vector_lane_mask=0xffff;
                for(unsigned lane=0;lane<16;++lane)d.vector_write_data[lane]=original[k+lane];tick();require(!d.host_error,"A10_F3_RELOAD");}
            idle(d);tick();d.op=phase;d.inverse=0;d.dif=0;d.root_phase=phase?0:1;d.scale=0;d.start=1;tick();idle(d);
            unsigned until_pending=0;while(!d.writeback_pending && until_pending<32){tick();++until_pending;}
            require(d.writeback_pending && d.busy && !d.done && d.data_writes==0,"A10_F3_PENDING_BEFORE_FIRST_COMMIT");
            const uint64_t writes=d.data_writes;
            if(method==0){d.profile_abort=1;tick();idle(d);
                require(d.done && d.error && !d.busy && !d.profile_loaded && !d.writeback_pending && d.data_writes==writes,"A10_F3_ABORT_FLUSH");}
            else reset();
            for(unsigned tail=0;tail<12;++tail){tick();require(!d.done && !d.busy && !d.writeback_pending &&
                !d.read_valid && !d.vector_read_valid && d.data_writes==writes,"A10_F3_QUIET_TAIL");}
            read_compare(original,"pending-cancel-RAM");load_header();
            const auto ordinary=spectrum_oracle(original);recovery_cycles+=run(0,false);read_compare(ordinary,"cancel-recovery");
            ++pending_cancels;
        }
'''


def cpp_source():
    source_guard()
    return transform((ROOT/CPP_PARENT).read_text(), (
        ('// Additive AW5/8/16 point launch-register geometry harness; independent ordinary oracle.\n// One added pointwise RAM-to-normalizer launch edge; butterfly schedule unchanged.',
         '// F3 writeback+1 each transform stage and point; independent ordinary oracle retained.\n// Added native-only pending observability tests physical RAM cancellation/reload.'),
        ('elapsed<AW*((N+127)/128+9)+64', 'elapsed<AW*((N+127)/128+10)+64'),
        ('if(op && fault=="--negative-counter")', 'if(!op && !inverse && fault=="--negative-counter")'),
        ('require(d.cycles==point_groups+7 && d.wait_cycles==7,"A10_POINT_COUNTER_NEGATIVE_REJECT");',
         'require(d.cycles==AW*(groups+9) && d.wait_cycles==AW*8,"A10_WRITEBACK_COUNTER_NEGATIVE_REJECT");'),
        ('"A10_POINT_COUNTER_NEGATIVE_MISSED"', '"A10_WRITEBACK_COUNTER_NEGATIVE_MISSED"'),
        ('d.cycles==(op?point_groups+8:AW*(groups+9)) && d.wait_cycles==(op?8:AW*8)',
         'd.cycles==(op?point_groups+9:AW*(groups+10)) && d.wait_cycles==(op?9:AW*9)'),
        ('        // Reset midtransform invalidates root/header and suppresses delayed outputs.',
         CANCEL_CASES+'        // Reset midtransform invalidates root/header and suppresses delayed outputs.'),
        ('"A10_POINT_ENGINE_PASS aw="', '"A10_WRITEBACK_ENGINE_PASS aw="'),
        ('<<total<<" profile_words=4\\n";', '<<total<<" profile_words=4 pending_cancels="<<pending_cancels<<" recovery_operations="<<pending_cancels<<" recovery_residues="<<pending_cancels*N<<" recovery_cycles="<<recovery_cycles<<"\\n";')))


def ledger(aw):
    result = dict(point.ledger(aw)); result['transform_cycles'] += aw; result['point_cycles'] += 1
    result['engine_work_cycles'] += 5*(2*aw+1); result['whole_controller_ntt_cycles'] += 2*aw+1
    rw = max(1,aw-7)
    result.update(transform_read_to_write_edges=9, point_read_to_write_edges=9,
        transform_wait_cycles=9*aw, point_wait_cycles=9, raw_BF_k_plus=5, II=1,
        per_transform_cycle_delta=aw, per_point_cycle_delta=1, whole_cycle_delta=2*aw+1,
        internal_write_payload_bits=128*(32+rw), internal_write_enable_bits=128,
        completion_token_bits=2, external_host_block_read_ABI_unchanged=True,
        external_host_write_ABI_unchanged=True, pending_cancel_native_cases=4,
        phase_contract='Selected internal data/row/bank-mask/valid captured together; immutable active phase until finalphysicalcommit; reset/profile/lookup/aritherror cancels eligible pending writes.',
        source_prediction_native_required=True, hold_repair_claim=False,
        delta='Only internal RAM write launch+physicalcommit tokens/drain; no arithmetic/root/profile/27-bit storage change.')
    return result


def write_sources():
    outputs = {TARGET:source(), NATIVE_HOST:native_host_source(), CPP:cpp_source()}
    for name in outputs:
        upper.need(not (ROOT/name).exists(), 'A10_F3_FRESH_TARGET '+name)
    for name, text in outputs.items():
        with (ROOT/name).open('x') as stream:
            stream.write(text)
    return {name:sha((ROOT/name).read_bytes()) for name in outputs}


if __name__ == '__main__':
    args = argparse.ArgumentParser(description=__doc__); args.add_argument('--write', action='store_true')
    parsed = args.parse_args()
    print(json.dumps(write_sources() if parsed.write else {str(aw):ledger(aw) for aw in (5,8,16)}, indent=2))

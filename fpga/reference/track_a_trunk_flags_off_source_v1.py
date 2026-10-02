"""Exact T5b observer/harness successors with a direct-parent lockstep witness."""
import hashlib
from pathlib import Path
from fpga.reference.track_a_trunk_contract_v1 import verify as trunk_verify,PARENT
ROOT=Path(__file__).resolve().parents[1]
PINS={
 'rtl/tb/core27_prefill_pipe_probe_v1.sv':'a47b2c89464ac727e9d40f7702cc0fc534e96694ffafbb8a1fed465c6cb447ce',
 'rtl/tb/core27_prefill_pipe_normal_v1.cpp':'dfc3b4550d5a37d71803db3b6b7a1429bcb004f65b43c4c01d1414b9ec0b1bb7',
 'rtl/tb/core27_prefill_pipe_normal_threaded_v1.cpp':'0374dc55627a76a23cbff420fabe3975842d3db79e8c1d07e55932b96ec15519'}
NEW='track_a_trunk_flags_off_probe_v1'

def expected():
    trunk_verify();texts={}
    for name,pin in PINS.items():
        raw=(ROOT/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('frozen observer/harness drift')
        texts[name]=raw.decode()
    old=texts['rtl/tb/core27_prefill_pipe_probe_v1.sv']
    instance=Path(PARENT).stem+' #(.AW(AW),.NTT_LANES(NTT_LANES)) dut (.*);'
    replacement='''genefer_track_a_trunk_v1 #(.AW(AW),.NTT_LANES(NTT_LANES)) selected (
        .clk,.rst_n,.load_we,.read_en,.start,.host_addr,.write_data,.base,.double_bit,
        .read_valid,.read_data,.busy,.done,.error,.cycles,.conversion_cycles,.root_cycles,
        .ntt_cycles,.crt_cycles,.carry_cycles,.carry_passes,.profile_cache_valid,
        .profile_loads,.profile_hits,.profile_words_loaded,.seed_setup_cycles,
        .cmd_valid(1'b1),.rsp_ready(1'b1),.cmd_opcode(3'd7),.cmd_address('1),
        .cmd_word(-32'sd1),.cmd_base(32'd0),.cmd_double(1'b1),
        .cmd_ready(),.rsp_valid(),.rsp_error(),.fault_sticky(),.image_valid(),.prefill_valid(),
        .rsp_opcode(),.rsp_word(),.rsp_error_code(),.rsp_generation(),.image_generation(),
        .square_cycles(),.prefill_cycles(),.post_cycles(),.host_abi()
    );'''
    if old.count(instance)!=1:raise ValueError('observer instance anchor')
    probe=old.replace('core27_prefill_pipe_probe_v1',NEW).replace(instance,replacement).replace('dut.','selected.baseline.dut.')
    outputs='read_valid read_data busy done error cycles conversion_cycles root_cycles ntt_cycles crt_cycles carry_cycles carry_passes profile_cache_valid profile_loads profile_hits profile_words_loaded seed_setup_cycles'.split()
    decl='''    logic ref_read_valid,ref_busy,ref_done,ref_error,ref_profile_cache_valid,ref_profile_loads,ref_profile_hits;
    logic signed [95:0] ref_read_data;
    logic [63:0] ref_cycles,ref_conversion_cycles,ref_root_cycles,ref_ntt_cycles,ref_crt_cycles,ref_carry_cycles,ref_seed_setup_cycles;
    logic [6:0] ref_carry_passes;
    logic [15:0] ref_profile_words_loaded;
'''
    bindings=['.'+x for x in 'clk rst_n load_we read_en start host_addr write_data base double_bit'.split()]+[f'.{x}(ref_{x})' for x in outputs]
    witness=decl+'    '+Path(PARENT).stem+' #(.AW(AW),.NTT_LANES(NTT_LANES)) reference_parent (\n        '+','.join(bindings)+'\n    );\n'
    compared=[x for x in outputs if x!='read_data']
    witness+='    always @(negedge clk)if(rst_n)begin\n'
    witness+='        if({'+','.join(compared)+'} !== {'+','.join('ref_'+x for x in compared)+'})$fatal(1,"A_TRUNK_FLAGS_OFF_CYCLE_MISMATCH");\n'
    witness+='        if(read_valid && read_data!==ref_read_data)$fatal(1,"A_TRUNK_FLAGS_OFF_WORD_MISMATCH");\n    end\n'
    probe=probe.replace('endmodule',witness+'endmodule')
    normal=texts['rtl/tb/core27_prefill_pipe_normal_v1.cpp'].replace('core27_prefill_pipe_probe_v1',NEW)
    threaded=texts['rtl/tb/core27_prefill_pipe_normal_threaded_v1.cpp'].replace('core27_prefill_pipe_probe_v1',NEW).replace('core27_prefill_pipe_normal_v1.cpp','track_a_trunk_flags_off_normal_v1.cpp')
    return {'rtl/tb/'+NEW+'.sv':probe,'rtl/tb/track_a_trunk_flags_off_normal_v1.cpp':normal,'rtl/tb/track_a_trunk_flags_off_threaded_v1.cpp':threaded}

def verify():
    for name,text in expected().items():
        if (ROOT/name).read_text()!=text:raise ValueError('flags-off source delta '+name)
    return dict(status='PASS_source_only',direct_parent_lockstep=True,original_observer_retained=True,native_pass=False)

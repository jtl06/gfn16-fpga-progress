// Additive integration selector. Frozen children remain separate exact modules.
// HOST_ABI=0 is the unchanged T5b pulse interface; HOST_ABI=1 is explicitly the
// command interface. This is NOT an implicit pulse-to-command protocol bridge.
module genefer_track_a_trunk_v1 #(
    parameter int AW=16,
    parameter int NTT_LANES=64,
    parameter bit USE_BLOCKCARRY=0,
    parameter bit USE_MERGED_TWIST=0,
    parameter bit USE_ROOT_LOOKAHEAD=0
) (
    input logic clk,rst_n,load_we,read_en,start,
    input logic [AW-1:0] host_addr,
    input logic signed [31:0] write_data,
    input logic [31:0] base,
    input logic double_bit,
    output logic read_valid,
    output logic signed [95:0] read_data,
    output logic busy,done,error,
    output logic [63:0] cycles,conversion_cycles,root_cycles,ntt_cycles,crt_cycles,carry_cycles,
    output logic [6:0] carry_passes,
    output logic profile_cache_valid,profile_loads,profile_hits,
    output logic [15:0] profile_words_loaded,
    output logic [63:0] seed_setup_cycles,
    input logic cmd_valid,rsp_ready,
    input logic [2:0] cmd_opcode,
    input logic [AW-1:0] cmd_address,
    input logic signed [31:0] cmd_word,
    input logic [31:0] cmd_base,
    input logic cmd_double,
    output logic cmd_ready,rsp_valid,rsp_error,fault_sticky,image_valid,prefill_valid,
    output logic [2:0] rsp_opcode,
    output logic signed [31:0] rsp_word,
    output logic [7:0] rsp_error_code,
    output logic [31:0] rsp_generation,image_generation,
    output logic [63:0] square_cycles,prefill_cycles,post_cycles,
    output logic host_abi
);
    initial begin
        if(USE_ROOT_LOOKAHEAD)$fatal(1,"A_TRUNK_LOOKAHEAD_BRANCH_NOT_PORTED");
        if(USE_MERGED_TWIST && !USE_BLOCKCARRY)$fatal(1,"A_TRUNK_MERGED_REQUIRES_BLOCK_ABI");
        if(USE_BLOCKCARRY && NTT_LANES!=64)$fatal(1,"A_TRUNK_BLOCK_LANES64_REQUIRED");
    end
    assign host_abi=USE_BLOCKCARRY;
    generate if(!USE_BLOCKCARRY)begin: baseline
        genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1
            #(.AW(AW),.NTT_LANES(NTT_LANES)) dut (
            .clk,.rst_n,.load_we,.read_en,.start,.host_addr,.write_data,.base,.double_bit,
            .read_valid,.read_data,.busy,.done,.error,.cycles,.conversion_cycles,.root_cycles,
            .ntt_cycles,.crt_cycles,.carry_cycles,.carry_passes,.profile_cache_valid,
            .profile_loads,.profile_hits,.profile_words_loaded,.seed_setup_cycles
        );
        assign cmd_ready=0;assign rsp_valid=0;assign rsp_error=0;assign fault_sticky=0;
        assign image_valid=0;assign prefill_valid=0;assign rsp_opcode=0;assign rsp_word=0;
        assign rsp_error_code=0;assign rsp_generation=0;assign image_generation=0;
        assign square_cycles=0;assign prefill_cycles=0;assign post_cycles=0;
    end else begin: command_host
        // Pulse outputs have no command-ABI meaning and remain explicitly zero.
        // Shared transform/profile counters describe the selected command core.
        assign read_valid=0;assign read_data=0;assign done=0;assign error=0;
        assign cycles=0;assign conversion_cycles=0;assign crt_cycles=0;assign carry_cycles=0;
        assign carry_passes=0;assign profile_cache_valid=0;assign profile_words_loaded=0;
        if(USE_MERGED_TWIST)begin: merged
            genefer_anext_core_v1 #(.AW(AW)) dut (
                .clk,.rst_n,.cmd_valid,.rsp_ready,.cmd_opcode,.cmd_address,.cmd_word,.cmd_base,.cmd_double,
                .cmd_ready,.rsp_valid,.rsp_error,.busy,.fault_sticky,.image_valid,.prefill_valid,
                .rsp_opcode,.rsp_word,.rsp_error_code,.rsp_generation,.image_generation,
                .square_cycles,.prefill_cycles,.ntt_cycles,.root_cycles,.post_cycles,.seed_setup_cycles,
                .profile_loads,.profile_hits
            );
        end else begin: block_only
            genefer_track_a4_core_v4 #(.AW(AW)) dut (
                .clk,.rst_n,.cmd_valid,.rsp_ready,.cmd_opcode,.cmd_address,.cmd_word,.cmd_base,.cmd_double,
                .cmd_ready,.rsp_valid,.rsp_error,.busy,.fault_sticky,.image_valid,.prefill_valid,
                .rsp_opcode,.rsp_word,.rsp_error_code,.rsp_generation,.image_generation,
                .square_cycles,.prefill_cycles,.ntt_cycles,.root_cycles,.post_cycles,.seed_setup_cycles,
                .profile_loads,.profile_hits
            );
        end
    end endgenerate
endmodule

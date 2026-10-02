// Simulation-only selective read-only observer; never a physical top.
module track_a_trunk_flags_off_probe_v1 #(
    parameter int AW=16,
    parameter int NTT_LANES=64
) (
    input logic clk, rst_n, load_we, read_en, start,
    input logic [AW-1:0] host_addr,
    input logic signed [31:0] write_data,
    input logic [31:0] base,
    input logic double_bit,
    output logic read_valid,
    output logic signed [95:0] read_data,
    output logic busy, done, error,
    output logic [63:0] cycles, conversion_cycles, root_cycles, ntt_cycles,
                        crt_cycles, carry_cycles,
    output logic [6:0] carry_passes,
    output logic profile_cache_valid,
    output logic profile_loads,profile_hits,
    output logic [15:0] profile_words_loaded,
    output logic [63:0] seed_setup_cycles,
    output logic dbg_prefilled,dbg_emit,dbg_write,dbg_check,
    output logic [AW:0] dbg_issued,dbg_written
);
    genefer_track_a_trunk_v1 #(.AW(AW),.NTT_LANES(NTT_LANES)) selected (
        .clk,.rst_n,.load_we,.read_en,.start,.host_addr,.write_data,.base,.double_bit,
        .read_valid,.read_data,.busy,.done,.error,.cycles,.conversion_cycles,.root_cycles,
        .ntt_cycles,.crt_cycles,.carry_cycles,.carry_passes,.profile_cache_valid,
        .profile_loads,.profile_hits,.profile_words_loaded,.seed_setup_cycles,
        .cmd_valid(1'b1),.rsp_ready(1'b1),.cmd_opcode(3'd7),.cmd_address('1),
        .cmd_word(-32'sd1),.cmd_base(32'd0),.cmd_double(1'b1),
        .cmd_ready(),.rsp_valid(),.rsp_error(),.fault_sticky(),.image_valid(),.prefill_valid(),
        .rsp_opcode(),.rsp_word(),.rsp_error_code(),.rsp_generation(),.image_generation(),
        .square_cycles(),.prefill_cycles(),.post_cycles(),.host_abi()
    );
    // Explicit-width values are mechanically checked against the exact pinned
    // core/carry enum declarations before staging and before native imports.
    localparam logic [3:0] CORE_IDLE=4'd0,CORE_CARRY_WAIT=4'd11,
        CORE_PREFILL_CHECK=4'd13,CARRY_EMIT=4'd7;
    initial if($bits(selected.baseline.dut.state)!=4 || $bits(selected.baseline.dut.carry_unit.state)!=4)
        $fatal(1,"T5_OBSERVER_STATE_WIDTH");
    assign dbg_prefilled=selected.baseline.dut.ntt_prefilled;
    assign dbg_emit=source_commit_valid;
    assign dbg_write=selected.baseline.dut.prefill_commit;
    assign dbg_check=selected.baseline.dut.state==CORE_PREFILL_CHECK;
    assign dbg_issued=selected.baseline.dut.prefill_issued;
    assign dbg_written=selected.baseline.dut.prefill_written;
    localparam int N=1<<AW, W=N<16?N:16;
    localparam logic [15:0] MASK=16'hffff>>(16-W);
    localparam logic [31:0] PRIME[0:2]='{32'd104857601,32'd69206017,32'd67239937};
    logic source_commit_valid;
    logic [AW-1:0] source_commit_addr;
    logic [1535:0] source_commit_data;
    logic [15:0] source_we,source_en;
    logic [AW-1:0] source_row[0:15];
    assign source_we=selected.baseline.dut.carry_unit.mem_we;
    assign source_en=selected.baseline.dut.carry_unit.mem_en;
    assign source_commit_valid=selected.baseline.dut.carry_unit.state==CARRY_EMIT && (|source_we);
    assign source_commit_addr=AW'(selected.baseline.dut.carry_unit.mem_addr[0])<<4;
    for(genvar h=0;h<16;h=h+1)begin: observed_source
        assign source_row[h]=AW'(selected.baseline.dut.carry_unit.mem_addr[h]);
        assign source_commit_data[h*96+:96]={{64{selected.baseline.dut.carry_unit.mem_data[h][31]}},selected.baseline.dut.carry_unit.mem_data[h][31:0]};
    end
    logic [7:0] observed_valid;
    logic [AW-1:0] observed_addr[0:7];
    logic [1535:0] observed_data[0:7];
    logic [127:0] actual_we[0:2];
    logic [31:0] actual_row[0:2][0:127],actual_data[0:2][0:127];
    integer emitted,written;
    logic image_valid;
    logic tail_host_error,quarantined;
    logic [31:0] image_base,operation_base;
    function automatic integer physical_bank(input integer address);
        integer bank;
        begin
            bank=0;
            for(integer b=0;b<AW;b=b+1)bank=bank^(((address>>b)&1)<<(b%7));
            physical_bank=bank;
        end
    endfunction
    for(genvar f=0;f<3;f=f+1)begin: observed_field
        assign actual_we[f]=selected.baseline.dut.field_lane[f].engine.child.data_we;
        for(genvar b=0;b<128;b=b+1)begin: observed_bank
            assign actual_row[f][b]=32'(selected.baseline.dut.field_lane[f].engine.child.data_wa[b]);
            assign actual_data[f][b]=selected.baseline.dut.field_lane[f].engine.child.data_w[b];
        end
    end
    // Independent event history uses eight clock delays from the actual commit;
    // it does not derive expected writes from the candidate boundary registers.
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            observed_valid<=0;emitted<=0;written<=0;image_valid<=0;
            image_base<=0;operation_base<=0;tail_host_error<=0;quarantined<=0;
        end else begin
            // Fault-edge writes, if any, still MUST match the independent old
            // committed-row history below. No writes survive the flush edge.
            if(quarantined)begin
                if(selected.baseline.dut.ntt_prefilled || actual_we[0]!=0 || actual_we[1]!=0 || actual_we[2]!=0)
                    $fatal(1,"T5B_MONITOR_QUARANTINE_WRITE");
            end
            if((selected.baseline.dut.state==CORE_CARRY_WAIT || selected.baseline.dut.state==CORE_PREFILL_CHECK) &&
               (selected.baseline.dut.core_fault || selected.baseline.dut.prefill_fault))quarantined<=1;
            if((selected.baseline.dut.state==CORE_CARRY_WAIT || selected.baseline.dut.state==CORE_PREFILL_CHECK) && (|selected.baseline.dut.ntt_host_error))
                tail_host_error<=1;
            if(selected.baseline.dut.state==CORE_PREFILL_CHECK &&
               (int'(selected.baseline.dut.prefill_issued)!=N || int'(selected.baseline.dut.prefill_written)!=N))
                $fatal(1,"T5_MONITOR_COMPLETE_COUNT");
            observed_valid<={observed_valid[6:0],source_commit_valid};
            if(source_commit_valid!=selected.baseline.dut.emit_commit_valid)$fatal(1,"T5_MONITOR_TEE_VALID");
            if(source_commit_valid)begin
                if(source_we!=MASK || (source_en&MASK)!=MASK ||
                   selected.baseline.dut.emit_commit_addr!=source_commit_addr || selected.baseline.dut.emit_commit_mask!=MASK)
                    $fatal(1,"T5_MONITOR_TEE_DESCRIPTOR");
                for(integer h=0;h<W;h=h+1)begin
                    if(source_row[h]!=source_row[0])$fatal(1,"T5_MONITOR_SOURCE_ROW");
                    if(selected.baseline.dut.emit_commit_data[h*96+:96]!=source_commit_data[h*96+:96])
                        $fatal(1,"T5_MONITOR_TEE_DATA");
                end
            end
            if(source_commit_valid)begin
                if(selected.baseline.dut.emit_commit_mask!=MASK || int'(source_commit_addr)!=emitted)
                    $fatal(1,"T5_MONITOR_EMIT_DESCRIPTOR");
                observed_addr[0]<=source_commit_addr;observed_data[0]<=source_commit_data;
                emitted<=emitted+W;
            end
            for(integer d=1;d<8;d=d+1)if(observed_valid[d-1])begin
                observed_addr[d]<=observed_addr[d-1];observed_data[d]<=observed_data[d-1];
            end
            if(selected.baseline.dut.state==CORE_CARRY_WAIT)begin
                if(selected.baseline.dut.prefill_commit!=observed_valid[7])$fatal(1,"T5_MONITOR_WRITE_AGE");
                for(integer f=0;f<3;f=f+1)begin
                    if($countones(actual_we[f])!=(observed_valid[7]?W:0))
                        $fatal(1,"T5_MONITOR_WRITE_MASK");
                    if(observed_valid[7])for(integer h=0;h<W;h=h+1)begin
                        if(!actual_we[f][physical_bank(int'(observed_addr[7])+h)] ||
                           actual_row[f][physical_bank(int'(observed_addr[7])+h)]!=32'((int'(observed_addr[7])+h)>>7))
                            $fatal(1,"T5_MONITOR_WRITE_ADDRESS");
                        if(actual_data[f][physical_bank(int'(observed_addr[7])+h)]!=
                           (observed_data[7][h*96+:96]==96'hffffffffffffffffffffffff ? PRIME[f]-1 :
                            32'(observed_data[7][h*96+:96]%96'(PRIME[f]))))
                            $fatal(1,"T5_MONITOR_WRITE_DATA");
                    end
                end
                if(observed_valid[7])written<=written+W;
            end
            if(done && !error)begin
                if(tail_host_error || (|selected.baseline.dut.ntt_host_error))$fatal(1,"T5_MONITOR_LATE_ERROR");
                if(emitted!=N || written!=N || observed_valid!=0 || !selected.baseline.dut.ntt_prefilled)
                    $fatal(1,"T5_MONITOR_COMPLETE_COUNT");
                image_valid<=1;image_base<=operation_base;
            end
            if(selected.baseline.dut.state==CORE_IDLE && !start && load_we)image_valid<=0;
            if(selected.baseline.dut.state==CORE_IDLE && start)begin
                // An immediate next start may share the edge that first sees
                // the preceding done pulse, before image_valid is registered.
                if(selected.baseline.dut.fast_eligible && ((!image_valid && !(done && !error)) ||
                   base!=(image_valid ? image_base : operation_base)))
                    $fatal(1,"T5_MONITOR_FAST_ELIGIBILITY");
                image_valid<=0;operation_base<=base;emitted<=0;written<=0;observed_valid<=0;tail_host_error<=0;
            end
            if(error)begin image_valid<=0;observed_valid<=0;end
        end
    end
    logic ref_read_valid,ref_busy,ref_done,ref_error,ref_profile_cache_valid,ref_profile_loads,ref_profile_hits;
    logic signed [95:0] ref_read_data;
    logic [63:0] ref_cycles,ref_conversion_cycles,ref_root_cycles,ref_ntt_cycles,ref_crt_cycles,ref_carry_cycles,ref_seed_setup_cycles;
    logic [6:0] ref_carry_passes;
    logic [15:0] ref_profile_words_loaded;
    genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1 #(.AW(AW),.NTT_LANES(NTT_LANES)) reference_parent (
        .clk,.rst_n,.load_we,.read_en,.start,.host_addr,.write_data,.base,.double_bit,.read_valid(ref_read_valid),.read_data(ref_read_data),.busy(ref_busy),.done(ref_done),.error(ref_error),.cycles(ref_cycles),.conversion_cycles(ref_conversion_cycles),.root_cycles(ref_root_cycles),.ntt_cycles(ref_ntt_cycles),.crt_cycles(ref_crt_cycles),.carry_cycles(ref_carry_cycles),.carry_passes(ref_carry_passes),.profile_cache_valid(ref_profile_cache_valid),.profile_loads(ref_profile_loads),.profile_hits(ref_profile_hits),.profile_words_loaded(ref_profile_words_loaded),.seed_setup_cycles(ref_seed_setup_cycles)
    );
    always @(negedge clk)if(rst_n)begin
        if({read_valid,busy,done,error,cycles,conversion_cycles,root_cycles,ntt_cycles,crt_cycles,carry_cycles,carry_passes,profile_cache_valid,profile_loads,profile_hits,profile_words_loaded,seed_setup_cycles} !== {ref_read_valid,ref_busy,ref_done,ref_error,ref_cycles,ref_conversion_cycles,ref_root_cycles,ref_ntt_cycles,ref_crt_cycles,ref_carry_cycles,ref_carry_passes,ref_profile_cache_valid,ref_profile_loads,ref_profile_hits,ref_profile_words_loaded,ref_seed_setup_cycles})$fatal(1,"A_TRUNK_FLAGS_OFF_CYCLE_MISMATCH");
        if(read_valid && read_data!==ref_read_data)$fatal(1,"A_TRUNK_FLAGS_OFF_WORD_MISMATCH");
    end
endmodule

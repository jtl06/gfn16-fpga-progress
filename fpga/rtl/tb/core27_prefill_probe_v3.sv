// Simulation-only selective read-only observer; never a physical top.
module core27_prefill_probe_v3 #(
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
    genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill #(.AW(AW),.NTT_LANES(NTT_LANES)) dut (.*);
    // Explicit-width values are mechanically checked against the exact pinned
    // core/carry enum declarations before staging and before native imports.
    localparam logic [3:0] CORE_IDLE=4'd0,CORE_CARRY_WAIT=4'd11,
        CORE_PREFILL_CHECK=4'd13,CARRY_EMIT=4'd7;
    initial if($bits(dut.state)!=4 || $bits(dut.carry_unit.state)!=4)
        $fatal(1,"T5_OBSERVER_STATE_WIDTH");
    assign dbg_prefilled=dut.ntt_prefilled;
    assign dbg_emit=source_commit_valid;
    assign dbg_write=dut.prefill_commit;
    assign dbg_check=dut.state==CORE_PREFILL_CHECK;
    assign dbg_issued=dut.prefill_issued;
    assign dbg_written=dut.prefill_written;
    localparam int N=1<<AW, W=N<16?N:16;
    localparam logic [15:0] MASK=16'hffff>>(16-W);
    localparam logic [31:0] PRIME[0:2]='{32'd104857601,32'd69206017,32'd67239937};
    logic source_commit_valid;
    logic [AW-1:0] source_commit_addr;
    logic [1535:0] source_commit_data;
    logic [15:0] source_we,source_en;
    logic [AW-1:0] source_row[0:15];
    assign source_we=dut.carry_unit.mem_we;
    assign source_en=dut.carry_unit.mem_en;
    assign source_commit_valid=dut.carry_unit.state==CARRY_EMIT && (|source_we);
    assign source_commit_addr=AW'(dut.carry_unit.mem_addr[0])<<4;
    for(genvar h=0;h<16;h=h+1)begin: observed_source
        assign source_row[h]=AW'(dut.carry_unit.mem_addr[h]);
        assign source_commit_data[h*96+:96]={{64{dut.carry_unit.mem_data[h][31]}},dut.carry_unit.mem_data[h][31:0]};
    end
    logic [4:0] observed_valid;
    logic [AW-1:0] observed_addr[0:4];
    logic [1535:0] observed_data[0:4];
    logic [127:0] actual_we[0:2];
    logic [31:0] actual_row[0:2][0:127],actual_data[0:2][0:127];
    integer emitted,written;
    logic image_valid;
    logic tail_host_error;
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
        assign actual_we[f]=dut.field_lane[f].engine.child.data_we;
        for(genvar b=0;b<128;b=b+1)begin: observed_bank
            assign actual_row[f][b]=32'(dut.field_lane[f].engine.child.data_wa[b]);
            assign actual_data[f][b]=dut.field_lane[f].engine.child.data_w[b];
        end
    end
    // Independent event history uses five clock delays from the actual commit;
    // it does not derive expected writes from the candidate boundary registers.
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            observed_valid<=0;emitted<=0;written<=0;image_valid<=0;
            image_base<=0;operation_base<=0;tail_host_error<=0;
        end else begin
            if((dut.state==CORE_CARRY_WAIT || dut.state==CORE_PREFILL_CHECK) && (|dut.ntt_host_error))
                tail_host_error<=1;
            if(dut.state==CORE_PREFILL_CHECK &&
               (int'(dut.prefill_issued)!=N || int'(dut.prefill_written)!=N))
                $fatal(1,"T5_MONITOR_COMPLETE_COUNT");
            observed_valid<={observed_valid[3:0],source_commit_valid};
            if(source_commit_valid!=dut.emit_commit_valid)$fatal(1,"T5_MONITOR_TEE_VALID");
            if(source_commit_valid)begin
                if(source_we!=MASK || (source_en&MASK)!=MASK ||
                   dut.emit_commit_addr!=source_commit_addr || dut.emit_commit_mask!=MASK)
                    $fatal(1,"T5_MONITOR_TEE_DESCRIPTOR");
                for(integer h=0;h<W;h=h+1)begin
                    if(source_row[h]!=source_row[0])$fatal(1,"T5_MONITOR_SOURCE_ROW");
                    if(dut.emit_commit_data[h*96+:96]!=source_commit_data[h*96+:96])
                        $fatal(1,"T5_MONITOR_TEE_DATA");
                end
            end
            if(source_commit_valid)begin
                if(dut.emit_commit_mask!=MASK || int'(source_commit_addr)!=emitted)
                    $fatal(1,"T5_MONITOR_EMIT_DESCRIPTOR");
                observed_addr[0]<=source_commit_addr;observed_data[0]<=source_commit_data;
                emitted<=emitted+W;
            end
            for(integer d=1;d<5;d=d+1)if(observed_valid[d-1])begin
                observed_addr[d]<=observed_addr[d-1];observed_data[d]<=observed_data[d-1];
            end
            if(dut.state==CORE_CARRY_WAIT && !dut.core_fault && !dut.prefill_fault)begin
                if(dut.prefill_commit!=observed_valid[4])$fatal(1,"T5_MONITOR_WRITE_AGE");
                for(integer f=0;f<3;f=f+1)begin
                    if($countones(actual_we[f])!=(observed_valid[4]?W:0))
                        $fatal(1,"T5_MONITOR_WRITE_MASK");
                    if(observed_valid[4])for(integer h=0;h<W;h=h+1)begin
                        if(!actual_we[f][physical_bank(int'(observed_addr[4])+h)] ||
                           actual_row[f][physical_bank(int'(observed_addr[4])+h)]!=32'((int'(observed_addr[4])+h)>>7))
                            $fatal(1,"T5_MONITOR_WRITE_ADDRESS");
                        if(actual_data[f][physical_bank(int'(observed_addr[4])+h)]!=
                           (observed_data[4][h*96+:96]==96'hffffffffffffffffffffffff ? PRIME[f]-1 :
                            32'(observed_data[4][h*96+:96]%96'(PRIME[f]))))
                            $fatal(1,"T5_MONITOR_WRITE_DATA");
                    end
                end
                if(observed_valid[4])written<=written+W;
            end
            if(done && !error)begin
                if(tail_host_error || (|dut.ntt_host_error))$fatal(1,"T5_MONITOR_LATE_ERROR");
                if(emitted!=N || written!=N || observed_valid!=0 || !dut.ntt_prefilled)
                    $fatal(1,"T5_MONITOR_COMPLETE_COUNT");
                image_valid<=1;image_base<=operation_base;
            end
            if(dut.state==CORE_IDLE && !start && load_we)image_valid<=0;
            if(dut.state==CORE_IDLE && start)begin
                // An immediate next start may share the edge that first sees
                // the preceding done pulse, before image_valid is registered.
                if(dut.fast_eligible && ((!image_valid && !(done && !error)) ||
                   base!=(image_valid ? image_base : operation_base)))
                    $fatal(1,"T5_MONITOR_FAST_ELIGIBILITY");
                image_valid<=0;operation_base<=base;emitted<=0;written<=0;observed_valid<=0;tail_host_error<=0;
            end
            if(error)begin image_valid<=0;observed_valid<=0;end
        end
    end
endmodule

// Coherent frame-stable threshold registers; zero extra carry-loop edges.
// PROVISIONAL A4 SOURCE ONLY: no native simulation or physical qualification.
// Generic-P isolated successor; only P8/defaultP16 qualified by this task.
// One contiguous block, T=N/P. Reuses the frozen div77/div47 and S3 small cell.
// Coefficient accept E0 -> parts E23 -> y E24 -> digit E25.
// Final digit E25 -> raw0 E26 -> boundary small cell E27 -> pair E28,
// final child-error quarantine/check E29. Bubbles preserve feedback/history.
// begin_block latches a SHARED CONTROLLER-QUALIFIED exact floor(2^96/base)
// reciprocal and A(base,N,P) coefficient_limit. Computing/checking these once
// per whole core is a REQUIRED integration gate, not implemented in this lane.
// No host/canonicalization protocol or next-frame eligibility is provided here.
module genefer_stream27_blockcarry_lane_localbase_v1 #(
    parameter int AW=16,P=16
) (
    input logic clk,rst_n,begin_block,in_valid,block_start,block_end,
    input logic [31:0] base,
    input logic [95:0] reciprocal,
    input logic [76:0] coefficient_limit,
    input logic signed [95:0] coefficient,
    input logic [AW-1:0] offset,
    output logic busy,done,error,
    output logic [3:0] error_code,
    output logic digit_valid,
    output logic [31:0] digit,
    output logic [AW-1:0] digit_offset,
    output logic boundary_valid,
    output logic [31:0] boundary_low,
    output logic signed [31:0] boundary_high
);
    localparam int BLOCKS=P,N=1<<AW,T=N/BLOCKS;
    localparam int K=2*N+24*BLOCKS,Q_SMALL=2*N+23*BLOCKS;
    localparam int MIN_PROOF=(2*K+2)/3+1;
    localparam int MIN_BASE=(2*N+5)>MIN_PROOF ? (2*N+5) : MIN_PROOF;
    localparam logic [95:0] MAX_B=96'd999999999;
    localparam logic [95:0] MAX_A=96'd2*((96'(N)+96'd3*96'(BLOCKS))*MAX_B*MAX_B+
        96'd4*96'(BLOCKS)*MAX_B*96'(K)+96'(BLOCKS)*96'(K)*96'(K));
    typedef enum logic [1:0] {IDLE,ACTIVE,FAILED} state_t;
    state_t state;
    logic [31:0] base_reg;
    logic signed [32:0] radix_reg,two_radix_reg,three_radix_reg,four_radix_reg;
    logic signed [32:0] negative_radix_reg,negative_two_radix_reg,y_high_reg;
    logic [95:0] reciprocal_reg;
    logic [76:0] limit_reg;
    logic [AW:0] accepted,split_seen,emitted;
    wire [95:0] magnitude=coefficient[95] ? $unsigned(-coefficient) : $unsigned(coefficient);
    wire config_ok=base>=32'(MIN_BASE) && base<=32'd1000000000 &&
        coefficient_limit!=0 && {19'd0,coefficient_limit}<=MAX_A && reciprocal!=0;
    wire input_ok=int'(accepted)<T && offset==AW'(accepted) &&
        block_start==(accepted==0) && block_end==(int'(accepted)==T-1) &&
        magnitude<={19'd0,limit_reg};
    logic fault_now;
    logic [3:0] fault_code;
    wire accept=state==ACTIVE && in_valid && !fault_now;
    assign busy=state==ACTIVE;

    logic first_valid,parts_valid;
    logic signed [77:0] first_q;
    logic [31:0] first_r,parts_r1;
    logic [AW-1:0] first_offset;
    logic signed [47:0] parts_q2;
    logic [AW+31:0] parts_payload;
    wire [31:0] parts_r0=parts_payload[31:0];
    wire [AW-1:0] parts_offset=parts_payload[AW+31:32];
    wire first_ok=first_q==$signed({{30{first_q[47]}},first_q[47:0]}) &&
        first_q!=-78'sd140737488355328 && first_r<base_reg;
    wire parts_ok=parts_q2>=-48'(Q_SMALL) && parts_q2<=48'(Q_SMALL) &&
        parts_r0<base_reg && parts_r1<base_reg && parts_offset==AW'(split_seen) && int'(split_seen)<T;
    genefer_div_recip_precision #(.MAG_W(77),.PAYLOAD_W(AW)) split_first (
        .clk,.rst_n,.in_valid(accept),.value(coefficient[77:0]),
        .base(base_reg),.reciprocal(reciprocal_reg),.payload_in(offset),
        .out_valid(first_valid),.quotient(first_q),.remainder(first_r),.payload_out(first_offset)
    );
    genefer_div_recip_precision #(.MAG_W(47),.PAYLOAD_W(AW+32)) split_second (
        .clk,.rst_n,.in_valid(state==ACTIVE && first_valid && first_ok && !fault_now),
        .value(first_q[47:0]),.base(base_reg),.reciprocal(reciprocal_reg),
        .payload_in({first_offset,first_r}),.out_valid(parts_valid),
        .quotient(parts_q2),.remainder(parts_r1),.payload_out(parts_payload)
    );

    logic [31:0] prev_r1,tail_r1;
    logic signed [32:0] prev_q2,prev2_q2,tail_prev_q2,tail_q2;
    logic y_valid;
    logic signed [32:0] y_reg;
    logic [AW-1:0] y_offset;
    logic small_valid,small_error;
    logic signed [2:0] small_carry;
    logic [31:0] small_digit;
    logic [AW-1:0] small_offset;
    genefer_stream27_blockcarry_small_cell_localbase_v1 #(.AW(AW),.P(BLOCKS),.PAYLOAD_W(AW)) digits (
        .clk,.rst_n,.in_valid(state==ACTIVE && y_valid && !fault_now),
        .block_start(y_offset==0),.base(base_reg),
        .radix(radix_reg),.two_radix(two_radix_reg),.three_radix(three_radix_reg),.four_radix(four_radix_reg),
        .negative_radix(negative_radix_reg),.negative_two_radix(negative_two_radix_reg),.y_high(y_high_reg),.y(y_reg),.carry_in(small_carry),
        .payload_in(y_offset),.out_valid(small_valid),.out_error(small_error),
        .digit(small_digit),.carry_out(small_carry),.payload_out(small_offset)
    );
    // Publish only registered state/valid. Gating this with fault_now would
    // make the output glitch when the upstream changes a next-cycle token.
    assign digit_valid=state==ACTIVE && small_valid;
    assign digit=small_digit;
    assign digit_offset=small_offset;

    logic raw_valid,boundary_small_valid,boundary_small_error;
    logic signed [32:0] raw0,raw1;
    logic [31:0] boundary_digit;
    logic signed [2:0] boundary_adjust;
    wire signed [32:0] high_sum=raw1+$signed({{30{boundary_adjust[2]}},boundary_adjust});
    genefer_stream27_blockcarry_small_cell_localbase_v1 #(.AW(AW),.P(BLOCKS),.PAYLOAD_W(1)) normalize_boundary (
        .clk,.rst_n,.in_valid(state==ACTIVE && raw_valid && !fault_now),
        .block_start(1'b0),.base(base_reg),
        .radix(radix_reg),.two_radix(two_radix_reg),.three_radix(three_radix_reg),.four_radix(four_radix_reg),
        .negative_radix(negative_radix_reg),.negative_two_radix(negative_two_radix_reg),.y_high(y_high_reg),.y(raw0),.carry_in(3'sd0),.payload_in(1'b0),
        .out_valid(boundary_small_valid),.out_error(boundary_small_error),
        .digit(boundary_digit),.carry_out(boundary_adjust),.payload_out()
    );

    always_comb begin
        fault_now=0;fault_code=0;
        if(state==IDLE)begin
            if(in_valid)begin fault_now=1;fault_code=4'd1;end
            else if(begin_block && !config_ok)begin fault_now=1;fault_code=4'd2;end
        end else if(state==ACTIVE)begin
            if(begin_block)begin fault_now=1;fault_code=4'd3;end
            else if(in_valid && !input_ok)begin fault_now=1;fault_code=4'd4;end
            else if(first_valid && !first_ok)begin fault_now=1;fault_code=4'd5;end
            else if(parts_valid && !parts_ok)begin fault_now=1;fault_code=4'd6;end
            else if(small_error || boundary_small_error)begin fault_now=1;fault_code=4'd7;end
            else if(small_valid && (small_offset!=AW'(emitted) || int'(emitted)>=T))begin
                fault_now=1;fault_code=4'd8;
            end else if(boundary_small_valid && (high_sum < -33'(K) || high_sum>33'(K)))begin
                fault_now=1;fault_code=4'd9;
            end else if(boundary_valid && (int'(accepted)!=T || int'(emitted)!=T ||
                    int'(split_seen)!=T || y_valid || raw_valid || first_valid || parts_valid || small_valid))begin
                fault_now=1;fault_code=4'd10;
            end
        end
    end
    // Same accepted begin as base/reciprocal/limit; no live-base use in feedback.
    // Payload reset is unnecessary: state/child eligibility revokes stale terms.
    // All terms fit signed33 for the admitted b<=1e9 (4b<=4e9<2^32).
    always_ff @(posedge clk)if(rst_n && state==IDLE && begin_block && !fault_now)begin
        radix_reg<=$signed({1'b0,base});
        two_radix_reg<=$signed({1'b0,base})<<<1;
        three_radix_reg<=($signed({1'b0,base})<<<1)+$signed({1'b0,base});
        four_radix_reg<=$signed({1'b0,base})<<<2;
        negative_radix_reg<= -$signed({1'b0,base});
        negative_two_radix_reg<= -($signed({1'b0,base})<<<1);
        y_high_reg<=($signed({1'b0,base})<<<1)-33'sd2+33'(Q_SMALL);
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;done<=0;error<=0;error_code<=0;
            base_reg<=32'd2;reciprocal_reg<=0;limit_reg<=0;
            accepted<=0;split_seen<=0;emitted<=0;
            prev_r1<=0;prev_q2<=0;prev2_q2<=0;
            tail_r1<=0;tail_prev_q2<=0;tail_q2<=0;
            y_valid<=0;y_reg<=0;y_offset<=0;
            raw_valid<=0;raw0<=0;raw1<=0;
            boundary_valid<=0;boundary_low<=0;boundary_high<=0;
        end else begin
            done<=0;y_valid<=0;raw_valid<=0;boundary_valid<=0;
            if(state==IDLE && begin_block && !fault_now)begin
                state<=ACTIVE;base_reg<=base;reciprocal_reg<=reciprocal;limit_reg<=coefficient_limit;
                accepted<=0;split_seen<=0;emitted<=0;
                prev_r1<=0;prev_q2<=0;prev2_q2<=0;
            end
            if(accept)accepted<=accepted+1'b1;
            if(state==ACTIVE && parts_valid && !fault_now)begin
                // History is updated only for accepted ordered coefficient parts.
                y_reg<=$signed({1'b0,parts_r0})+$signed({1'b0,prev_r1})+prev2_q2;
                y_offset<=parts_offset;y_valid<=1;
                prev_r1<=parts_r1;prev2_q2<=prev_q2;prev_q2<=33'(parts_q2);
                split_seen<=split_seen+1'b1;
                if(int'(parts_offset)==T-1)begin
                    tail_r1<=parts_r1;tail_prev_q2<=prev_q2;tail_q2<=33'(parts_q2);
                end
            end
            if(digit_valid)begin
                emitted<=emitted+1'b1;
                if(int'(small_offset)==T-1)begin
                    raw0<=$signed({1'b0,tail_r1})+tail_prev_q2+$signed({{30{small_carry[2]}},small_carry});
                    raw1<=tail_q2;raw_valid<=1;
                end
            end
            if(state==ACTIVE && boundary_small_valid && !fault_now)begin
                boundary_low<=boundary_digit;boundary_high<=32'(high_sum);boundary_valid<=1;
            end
            if(state==ACTIVE && boundary_valid && !fault_now)begin
                state<=IDLE;done<=1;
            end
            // Sticky quarantine: only external reset can recover after error.
            // Child pipelines may drain, but no old valid can escape FAILED.
            if(fault_now)begin
                state<=FAILED;error<=1;error_code<=fault_code;done<=0;
                y_valid<=0;raw_valid<=0;boundary_valid<=0;
            end
        end
    end
    // synthesis translate_off
    initial begin
        if(AW<5 || AW>16 || P<1 || P>N/2 || (P&(P-1))!=0)$fatal(1,"A4_BLOCK_LANE_GEOMETRY");
        if(MAX_A>=96'd151115727451828646838272)$fatal(1,"A4_BLOCK_LANE_WIDTH");
    end
    // synthesis translate_on
endmodule

// Shared P8/P16 registered transport wrappers. Pending faults are diagnostics;
// previous-edge out_error/quarantine inhibit the next occupied sampling edge.
module genefer_stream27_mul_param_v1 #(
    parameter int LANES=16, GEN_W=8,
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] Q=32'd4190109697
) (
    input logic clk,rst_n,in_slot_valid,frame_start,quarantine,
    input logic [GEN_W-1:0] generation_in,
    input logic [LANES*27-1:0] lhs,rhs,
    output logic out_slot_valid,out_frame_start,out_error,fault_pending,
    output logic [GEN_W-1:0] generation_out,
    output logic [LANES*27-1:0] result
);
    logic [LANES-1:0] lane_valid;
    logic [3:0] slot_pipe,start_pipe;
    logic [GEN_W-1:0] generation_pipe[0:3];
    wire stop=quarantine || out_error;
    wire mismatch=lane_valid!={LANES{slot_pipe[3]}};
    assign out_slot_valid=slot_pipe[3] && (&lane_valid) && !stop;
    assign out_frame_start=start_pipe[3] && out_slot_valid;
    assign generation_out=generation_pipe[3];
    assign fault_pending=out_error || (!stop && mismatch);
    for(genvar lane=0;lane<LANES;lane=lane+1)begin: products
        wire [31:0] product;
        genefer_stream27_montgomery_factored_v1 #(.P(P),.Q(Q)) multiplier (
            .clk,.rst_n,.in_valid(in_slot_valid && !stop),
            .lhs({5'b0,lhs[lane*27+:27]}),.rhs({5'b0,rhs[lane*27+:27]}),
            .out_valid(lane_valid[lane]),.result(product));
        assign result[lane*27+:27]=product[26:0];
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin slot_pipe<=0;start_pipe<=0;out_error<=0;end
        else begin
            if(!stop && mismatch)out_error<=1;
            if(stop)begin slot_pipe<=0;start_pipe<=0;end
            else begin
                slot_pipe<={slot_pipe[2:0],in_slot_valid};
                start_pipe<={start_pipe[2:0],in_slot_valid && frame_start};
                generation_pipe[0]<=generation_in;
                for(int k=1;k<4;k=k+1)generation_pipe[k]<=generation_pipe[k-1];
            end
        end
    end
    // synthesis translate_off
    initial if(LANES!=8 && LANES!=16)$fatal(1,"STREAM_SHARED_LANES");
    // synthesis translate_on
endmodule

module genefer_stream27_add_param_v1 #(
    parameter int LANES=16, GEN_W=8,
    parameter logic [31:0] P=32'd104857601
) (
    input logic clk,rst_n,in_slot_valid,frame_start,quarantine,
    input logic [GEN_W-1:0] generation_in,
    input logic [LANES*27-1:0] lhs,rhs,
    output logic out_slot_valid,out_frame_start,out_error,fault_pending,
    output logic [GEN_W-1:0] generation_out,
    output logic [LANES*27-1:0] result
);
    wire stop=quarantine || out_error;
    logic [LANES-1:0] noncanonical;
    assign fault_pending=out_error || (!stop && in_slot_valid && (|noncanonical));
    for(genvar lane=0;lane<LANES;lane=lane+1)begin: sums
        wire [31:0] total={5'b0,lhs[lane*27+:27]}+{5'b0,rhs[lane*27+:27]};
        assign noncanonical[lane]={5'b0,lhs[lane*27+:27]}>=P || {5'b0,rhs[lane*27+:27]}>=P;
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid && !stop)
                result[lane*27+:27]<=27'(total>=P ? total-P : total);
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin out_slot_valid<=0;out_frame_start<=0;out_error<=0;end
        else begin
            if(!stop && in_slot_valid && (|noncanonical))out_error<=1;
            out_slot_valid<=in_slot_valid && !stop;
            out_frame_start<=in_slot_valid && frame_start && !stop;
            if(in_slot_valid && !stop)generation_out<=generation_in;
        end
    end
    // synthesis translate_off
    initial if(LANES!=8 && LANES!=16)$fatal(1,"STREAM_SHARED_LANES");
    // synthesis translate_on
endmodule

// Additive source-only physical-row wrappers. Canceled rows retain occupied
// slots and tags. Eligibility is checked only at the owning terminal sink.
module genefer_stream27_mul8_v2 #(
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] Q=32'd4190109697
) (
    input logic clk,rst_n,in_slot_valid,frame_start,quarantine,
    input logic [7:0] generation_in,
    input logic [215:0] lhs,rhs,
    output logic out_slot_valid,out_frame_start,out_error,fault_pending,
    output logic [7:0] generation_out,
    output logic [215:0] result
);
    logic [7:0] lane_valid;
    logic [3:0] slot_pipe,start_pipe;
    logic [7:0] generation_pipe[0:3];
    wire mismatch=lane_valid!={8{slot_pipe[3]}};
    assign out_slot_valid=slot_pipe[3] && (&lane_valid) && !quarantine && !out_error;
    assign out_frame_start=start_pipe[3] && out_slot_valid;
    assign generation_out=generation_pipe[3];
    assign fault_pending=out_error || (!quarantine && mismatch);
    for(genvar lane=0;lane<8;lane=lane+1) begin : multipliers
        wire [31:0] product;
        genefer_montgomery_mul27_sparse_pipe #(.P(P),.Q(Q)) multiplier (
            .clk,.rst_n,.in_valid(in_slot_valid && !quarantine),
            .lhs({5'b0,lhs[lane*27+:27]}),.rhs({5'b0,rhs[lane*27+:27]}),
            .out_valid(lane_valid[lane]),.result(product));
        assign result[lane*27+:27]=product[26:0];
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin slot_pipe<=0;start_pipe<=0;out_error<=0;end
        else begin
            if(!quarantine && mismatch)out_error<=1;
            if(quarantine)begin slot_pipe<=0;start_pipe<=0;end
            else begin
                slot_pipe<={slot_pipe[2:0],in_slot_valid};
                start_pipe<={start_pipe[2:0],in_slot_valid && frame_start};
                generation_pipe[0]<=generation_in;
                for(int k=1;k<4;k=k+1)generation_pipe[k]<=generation_pipe[k-1];
            end
        end
    end
endmodule

module genefer_stream27_add8_v2 #(
    parameter logic [31:0] P=32'd104857601
) (
    input logic clk,rst_n,in_slot_valid,frame_start,quarantine,
    input logic [7:0] generation_in,
    input logic [215:0] lhs,rhs,
    output logic out_slot_valid,out_frame_start,out_error,fault_pending,
    output logic [7:0] generation_out,
    output logic [215:0] result
);
    logic [7:0] noncanonical;
    assign fault_pending=out_error || (!quarantine && in_slot_valid && (|noncanonical));
    for(genvar lane=0;lane<8;lane=lane+1) begin : adders
        wire [31:0] total={5'b0,lhs[lane*27+:27]}+{5'b0,rhs[lane*27+:27]};
        assign noncanonical[lane]={5'b0,lhs[lane*27+:27]}>=P || {5'b0,rhs[lane*27+:27]}>=P;
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid && !quarantine && !fault_pending)
                result[lane*27+:27]<=27'(total>=P ? total-P : total);
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n)begin out_slot_valid<=0;out_frame_start<=0;out_error<=0;end
        else begin
            if(!quarantine && in_slot_valid && (|noncanonical))out_error<=1;
            out_slot_valid<=in_slot_valid && !quarantine && !fault_pending;
            out_frame_start<=in_slot_valid && frame_start && !quarantine && !fault_pending;
            if(in_slot_valid)generation_out<=generation_in;
        end
    end
endmodule

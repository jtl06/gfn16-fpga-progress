// Four register stages, II=1: accepted edge t responds at edge t+3.
// Ordinary inputs0..999999999 or signed32 -1 (FFFFFFFF) only.
// Invalid full-word inputs produce out_error, never a truncated residue.
module genefer_digit_reduce27_pipe #(
    parameter logic [31:0] P=32'd104857601,
    parameter int PAYLOAD_W=1
) (
    input logic clk,rst_n,in_valid,
    input logic [31:0] digit,
    input logic [PAYLOAD_W-1:0] payload_in,
    output logic out_valid,out_error,
    output logic [31:0] residue,
    output logic [PAYLOAD_W-1:0] payload_out
);
    localparam bit PARAM_OK=P<32'd134217728 && (64'(P)<<4)>64'd999999999;
    localparam logic [31:0] P8=P<<3;
    localparam logic [29:0] P4=30'(P)<<2;
    localparam logic [28:0] P2=29'(P)<<1;
    logic [2:0] good,bad;
    logic [29:0] s1;
    logic [28:0] s2;
    logic [27:0] s3;
    logic [PAYLOAD_W-1:0] tag1,tag2,tag3;
    logic legal;
    logic [31:0] normalized,first_difference;
    assign legal=PARAM_OK && (digit<=32'd999999999 || digit==32'hffffffff);
    assign normalized=digit==32'hffffffff ? P-32'd1 : digit;
    assign first_difference=normalized>=P8 ? normalized-P8 : normalized;

    // Data stages are valid-gated and intentionally not reset. No invalid
    // input reaches a narrowed arithmetic register.
    always_ff @(posedge clk)begin
        if(rst_n && in_valid && legal)s1<=first_difference[29:0];
        if(rst_n && good[0])s2<=29'(s1>=P4 ? s1-P4 : s1);
        if(rst_n && good[1])s3<=28'(s2>=P2 ? s2-P2 : s2);
        if(rst_n && in_valid)tag1<=payload_in;
        if(rst_n && (good[0] || bad[0]))tag2<=tag1;
        if(rst_n && (good[1] || bad[1]))tag3<=tag2;
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            good<='0;bad<='0;out_valid<=0;out_error<=0;residue<=0;payload_out<='0;
        end else begin
            good<={good[1:0],in_valid && legal};bad<={bad[1:0],in_valid && !legal};
            out_valid<=good[2];out_error<=bad[2];
            if(good[2])residue<={5'b0,27'(s3>=28'(P) ? s3-28'(P) : s3)};
            if(good[2] || bad[2])payload_out<=tag3;
        end
    end
    // synthesis translate_off
    initial begin
        if(!PARAM_OK)$fatal(1,"unsupported digit reducer modulus range");
        if(PAYLOAD_W<1)$fatal(1,"invalid digit reducer payload width");
    end
    always @(posedge clk)if(rst_n)begin
        if(good[0] && 32'(s1)>=P8)$fatal(1,"digit stage1 range");
        if(good[1] && s2>=29'(P4))$fatal(1,"digit stage2 range");
        if(good[2] && s3>=28'(P2))$fatal(1,"digit stage3 range");
        if(out_valid && (out_error || residue>=P))$fatal(1,"digit reducer output range");
    end
    // synthesis translate_on
endmodule

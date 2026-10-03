// Setup snapshot terms are qualified by the frame controller, like its reciprocal/A.
// No extra input/register/feedback edge. Base bounds and all token guards remain.
// stream27-blockcarry shared S3/A4 primitive; SOURCE-ONLY, not native/fit qualified.
// Producer already registers y. Acceptance at this edge registers digit/carry:
// one feedback edge, II1, no input/y register and no extra carry-state register.
// Caller feeds carry_out back as carry_in, preserves base/generation coherency,
// and owns error quarantine. This cell is deliberately not a frame controller.
module genefer_stream27_blockcarry_small_cell_localbase_v1 #(
    parameter int AW=16,
    parameter int P=8,
    parameter int PAYLOAD_W=1
) (
    input logic clk,rst_n,in_valid,block_start,
    input logic [31:0] base,
    // Trusted frame terms: coherent registers from the caller's accepted begin.
    input logic signed [32:0] radix,two_radix,three_radix,four_radix,
    input logic signed [32:0] negative_radix,negative_two_radix,y_high,
    input logic signed [32:0] y,
    input logic signed [2:0] carry_in,
    input logic [PAYLOAD_W-1:0] payload_in,
    output logic out_valid,out_error,
    output logic [31:0] digit,
    output logic signed [2:0] carry_out,
    output logic [PAYLOAD_W-1:0] payload_out
);
    localparam int unsigned N=32'd1<<AW;
    localparam int unsigned K=2*N+24*P;
    // Conservative, base-independent ceil(A/base^2) bound from the adopted
    // coefficient invariant. No wide divider/quotient is in this feedback loop.
    localparam int unsigned Q=2*N+23*P;
    localparam int unsigned PROOF_MIN=(2*K+2)/3+1;
    localparam int unsigned MIN_BASE=(2*N+5)>PROOF_MIN ? (2*N+5) : PROOF_MIN;
    localparam bit PARAM_OK=AW>=5 && AW<=16 && P>=1 && P<=N/2 &&
        (P&(P-1))==0 && PAYLOAD_W>=1;
    localparam logic signed [32:0] Q_BOUND=33'(Q);
    logic signed [32:0] total,digit_next;
    logic signed [2:0] carry_effective,carry_next;
    logic legal;

    assign carry_effective=block_start ? 3'sd0 : carry_in;
    assign total=y+$signed({{30{carry_effective[2]}},carry_effective});
    // Six Euclidean quotient regions: floor(total/base), NOT truncation to0.
    // All thresholds and corrections fit signed33 for every legal base<=1e9.
    always_comb begin
        if(total < negative_radix)begin carry_next=-3'sd2;digit_next=total+two_radix;end
        else if(total < 0)begin carry_next=-3'sd1;digit_next=total+radix;end
        else if(total < radix)begin carry_next=3'sd0;digit_next=total;end
        else if(total < two_radix)begin carry_next=3'sd1;digit_next=total-radix;end
        else if(total < three_radix)begin carry_next=3'sd2;digit_next=total-two_radix;end
        else begin carry_next=3'sd3;digit_next=total-three_radix;end
    end
    // A signed3 port is already <=3; its -4/-3 encodings are rejected even
    // at block_start. Full signed33 y and full base32 are checked before any
    // narrowing. First-block history is zero, so initial y must be in0..base-1.
    assign legal=PARAM_OK && base>=32'(MIN_BASE) && base<=32'd1000000000 &&
        carry_in>=-3'sd2 && y>=-Q_BOUND && y<=y_high &&
        (!block_start || (y>=0 && y<radix)) &&
        total>=negative_two_radix && total<four_radix;

    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin out_valid<=0;out_error<=0;carry_out<=0;end
        else begin
            out_valid<=in_valid && legal;
            out_error<=in_valid && !legal;
            if(in_valid && legal)carry_out<=carry_next;
        end
    end
    // On a rejected token the tag still identifies the error, while digit and
    // carry hold. Bubbles/reset hold digit/tag; reset clears carry and eligibility.
    always_ff @(posedge clk)begin
        if(rst_n && in_valid)begin
            payload_out<=payload_in;
            if(legal)digit<=digit_next[31:0];
        end
    end
    // synthesis translate_off
    initial begin
        if(!PARAM_OK)$fatal(1,"STREAM27_SMALL_CARRY_GEOMETRY");
        if(Q>=K || 64'(4)*64'(1000000000)>64'hffffffff)
            $fatal(1,"STREAM27_SMALL_CARRY_WIDTH_PROOF");
    end
    always @(posedge clk)if(rst_n && in_valid && legal)begin
        if(digit_next[32] || digit_next>=radix || carry_next < -3'sd2)
            $fatal(1,"STREAM27_SMALL_CARRY_RESULT_RANGE");
    end
    // synthesis translate_on
endmodule

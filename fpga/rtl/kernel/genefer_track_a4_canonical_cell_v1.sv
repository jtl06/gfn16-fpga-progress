// Provisional host-only canonical cell. Registered input producer, one feedback
// edge. Different legal y envelope from S3 small cell; frozen S3 is unchanged.
module genefer_track_a4_canonical_cell_v1 #(parameter int AW=16,PAYLOAD_W=1) (
    input logic clk,rst_n,in_valid,
    input logic [31:0] base,
    input logic signed [32:0] value,
    input logic signed [2:0] carry_in,
    input logic [PAYLOAD_W-1:0] payload_in,
    output logic out_valid,out_error,
    output logic [31:0] digit,
    output logic signed [2:0] carry_out,
    output logic [PAYLOAD_W-1:0] payload_out
);
    localparam int N=1<<AW,K=2*N+384;
    localparam int MIN_PROOF=(2*K+2)/3+1;
    localparam int MIN_BASE=(2*N+5)>MIN_PROOF ? (2*N+5) : MIN_PROOF;
    wire signed [32:0] radix=$signed({1'b0,base});
    wire signed [32:0] b=radix-33'sd1;
    wire signed [32:0] lower=-(b>33'(K) ? b : 33'(K));
    wire signed [32:0] upper=(b<<<1)>(b+33'(K)) ? (b<<<1) : b+33'(K);
    wire signed [32:0] total=value+$signed({{30{carry_in[2]}},carry_in});
    wire legal=base>=32'(MIN_BASE) && base<=32'd1000000000 &&
        carry_in>=-3'sd2 && carry_in<=3'sd2 && value>=lower && value<=upper &&
        total>=-(radix<<<1) && total<(radix+(radix<<<1));
    logic signed [2:0] next_carry;
    logic signed [32:0] next_digit;
    always_comb begin
        if(total < -radix)begin next_carry=-3'sd2;next_digit=total+(radix<<<1);end
        else if(total<0)begin next_carry=-3'sd1;next_digit=total+radix;end
        else if(total<radix)begin next_carry=3'sd0;next_digit=total;end
        else if(total<(radix<<<1))begin next_carry=3'sd1;next_digit=total-radix;end
        else begin next_carry=3'sd2;next_digit=total-(radix<<<1);end
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin out_valid<=0;out_error<=0;carry_out<=0;digit<=0;payload_out<=0;end
        else begin
            out_valid<=in_valid && legal;out_error<=in_valid && !legal;
            if(in_valid)begin
                payload_out<=payload_in;
                if(legal)begin digit<=next_digit[31:0];carry_out<=next_carry;end
            end
        end
    end
    // synthesis translate_off
    initial if(AW<5 || AW>16 || PAYLOAD_W<1)$fatal(1,"A4_CANON_CELL_GEOMETRY");
    always @(posedge clk)if(rst_n && in_valid && legal)
        if(next_digit<0 || next_digit>=radix)$fatal(1,"A4_CANON_CELL_REMAINDER");
    // synthesis translate_on
endmodule

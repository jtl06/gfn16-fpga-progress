// Exact signed96 Euclidean quotient/remainder using a shared reciprocal.
// Contract: 2<=base<=1e9, reciprocal=floor(2^96/base), |value|<2^95.
// Seven registered stages; accept every clock. Shared parameters remain stable
// until all transactions drain. Outputs are meaningful only when out_valid.
module genefer_div96_recip_prefix #(parameter int PAYLOAD_W=1) (
    input logic clk, rst_n, in_valid,
    input logic signed [95:0] value,
    input logic [31:0] base,
    input logic [95:0] reciprocal,
    input logic [PAYLOAD_W-1:0] payload_in,
    output logic out_valid,
    output logic signed [95:0] quotient,
    output logic [31:0] remainder,
    output logic [PAYLOAD_W-1:0] payload_out
);
    logic [6:0] valid;
    logic [5:0] negative;
    logic [95:0] magnitude, estimate, estimate_d, unsigned_q;
    logic [31:0] lows[0:4], residue_product, unsigned_r, provisional_r;
    logic [63:0] partial[0:2][0:2];
    logic [127:0] rows[0:2];
    logic [191:0] product_sum;
    logic [PAYLOAD_W-1:0] payloads[0:6];
    assign product_sum={64'b0,rows[0]}+{32'b0,rows[1],32'b0}+{rows[2],64'b0};
    assign provisional_r=lows[4]-residue_product;
    assign out_valid=valid[6];
    assign payload_out=payloads[6];
    always_ff @(posedge clk) begin
        magnitude<=value<0 ? $unsigned(-value) : $unsigned(value);
        lows[0]<=value<0 ? 32'($unsigned(-value)) : value[31:0];
        for(int j=1;j<5;j=j+1) lows[j]<=lows[j-1];
        negative<={negative[4:0],value<0};
        for(int a=0;a<3;a=a+1)
            for(int b=0;b<3;b=b+1)
                partial[a][b]<=magnitude[a*32+:32]*reciprocal[b*32+:32];
        for(int a=0;a<3;a=a+1)
            rows[a]<={64'b0,partial[a][0]}+{32'b0,partial[a][1],32'b0}+{partial[a][2],64'b0};
        estimate<=product_sum[191:96];
        estimate_d<=estimate;
        residue_product<=estimate[31:0]*base;
        unsigned_q<=estimate_d+(provisional_r>=base ? 96'd1 : 96'd0);
        unsigned_r<=provisional_r>=base ? provisional_r-base : provisional_r;
        quotient<=negative[5] ? -$signed(unsigned_q)-(unsigned_r!=0 ? 96'sd1 : 96'sd0) : $signed(unsigned_q);
        remainder<=negative[5] && unsigned_r!=0 ? base-unsigned_r : unsigned_r;
        payloads[0]<=payload_in;
        for(int j=1;j<7;j=j+1) payloads[j]<=payloads[j-1];
    end
    always_ff @(posedge clk or negedge rst_n)
        if(!rst_n) valid<=0;
        else valid<={valid[5:0],in_valid};
endmodule

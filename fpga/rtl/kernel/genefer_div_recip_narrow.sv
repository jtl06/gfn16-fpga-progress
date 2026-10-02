// Exact Euclidean division with genuinely narrowed multiplier operands.
// MAG_W is 77 or47; |value|<2^MAG_W; base2..1e9; reciprocal=floor(2^96/base).
// Same seven-stage II=1 schedule as genefer_div96_recip_prefix.
module genefer_div_recip_narrow #(parameter int MAG_W=77, PAYLOAD_W=1) (
    input logic clk, rst_n, in_valid,
    input logic signed [MAG_W:0] value,
    input logic [31:0] base,
    input logic [95:0] reciprocal,
    input logic [PAYLOAD_W-1:0] payload_in,
    output logic out_valid,
    output logic signed [MAG_W:0] quotient,
    output logic [31:0] remainder,
    output logic [PAYLOAD_W-1:0] payload_out
);
    localparam int LIMBS=(MAG_W+31)/32, PROD_W=MAG_W+96;
    logic [6:0] valid;
    logic [5:0] negative;
    logic [MAG_W-1:0] magnitude,estimate,estimate_d,unsigned_q;
    logic [31:0] lows[0:4],residue_product,unsigned_r,provisional_r;
    logic [PROD_W-1:0] shifted_rows[0:LIMBS-1],product_sum;
    logic [PAYLOAD_W-1:0] payloads[0:6];
    for(genvar a=0;a<LIMBS;a=a+1)begin: limb
        localparam int LW=(a==LIMBS-1) ? MAG_W-a*32 : 32;
        wire [LW-1:0] digit=magnitude[a*32+:LW];
        logic [LW+31:0] partial[0:2];
        logic [LW+95:0] row;
        for(genvar b=0;b<3;b=b+1)begin: product
            // The high limb is physically 13x32 or15x32, not padded96x96.
            always_ff @(posedge clk)partial[b]<=digit*reciprocal[b*32+:32];
        end
        always_ff @(posedge clk)
            row<={{64{1'b0}},partial[0]}+{{32{1'b0}},partial[1],32'b0}+{partial[2],64'b0};
        assign shifted_rows[a]=PROD_W'(row)<<(a*32);
    end
    always_comb begin
        product_sum='0;
        for(int a=0;a<LIMBS;a=a+1)product_sum=product_sum+shifted_rows[a];
    end
    assign provisional_r=lows[4]-residue_product;
    assign out_valid=valid[6];
    assign payload_out=payloads[6];
    always_ff @(posedge clk)begin
        magnitude<=MAG_W'(value<0 ? $unsigned(-value) : $unsigned(value));
        lows[0]<=value<0 ? 32'($unsigned(-value)) : value[31:0];
        for(int j=1;j<5;j=j+1)lows[j]<=lows[j-1];
        negative<={negative[4:0],value<0};
        estimate<=product_sum[PROD_W-1:96];
        estimate_d<=estimate;
        residue_product<=estimate[31:0]*base;
        unsigned_q<=estimate_d+(provisional_r>=base ? MAG_W'(1) : MAG_W'(0));
        unsigned_r<=provisional_r>=base ? provisional_r-base : provisional_r;
        quotient<=negative[5] ? -$signed({1'b0,unsigned_q})-$signed((MAG_W+1)'(unsigned_r!=0)) : $signed({1'b0,unsigned_q});
        remainder<=negative[5] && unsigned_r!=0 ? base-unsigned_r : unsigned_r;
        payloads[0]<=payload_in;
        for(int j=1;j<7;j=j+1)payloads[j]<=payloads[j-1];
    end
    always_ff @(posedge clk or negedge rst_n)
        if(!rst_n)valid<=0;else valid<={valid[5:0],in_valid};
    // synthesis translate_off
    initial if(MAG_W!=77 && MAG_W!=47)$fatal(1,"unsupported narrow magnitude width");
    always @(posedge clk)if(rst_n && in_valid && value=={1'b1,{MAG_W{1'b0}}})
        $fatal(1,"narrow divider input outside magnitude contract");
    // synthesis translate_on
endmodule

// Exact Euclidean division with genuinely narrowed multiplier operands.
// MAG_W is 77 or47; |value|<2^MAG_W; base2..1e9; reciprocal=floor(2^96/base).
// Ten stages, II=1: accepted edge k -> response after edge k+9.
// base and reciprocal stay stable for every response the caller consumes.
// Abandoned work may be quarantined by the caller during configuration setup.
module genefer_div_recip_narrow_pipe #(parameter int MAG_W=77, PAYLOAD_W=1) (
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
    logic [9:0] valid;
    logic [7:0] negative;
    logic [MAG_W-1:0] magnitude,estimate,estimate_d,estimate_e,estimate_f,unsigned_q;
    logic correction,negative_fraction;
    logic signed [MAG_W:0] signed_q;
    logic [31:0] signed_r,provisional_d,subtracted_r;
    logic [31:0] lows[0:4],residue_product,unsigned_r,provisional_r;
    logic [PROD_W-1:0] shifted_rows[0:LIMBS-1],product_sum;
    logic [PAYLOAD_W-1:0] payloads[0:9];
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
    
    assign out_valid=valid[9];
    assign payload_out=payloads[9];
    always_ff @(posedge clk)begin
        magnitude<=MAG_W'(value<0 ? $unsigned(-value) : $unsigned(value));
        lows[0]<=value<0 ? 32'($unsigned(-value)) : value[31:0];
        for(int j=1;j<5;j=j+1)lows[j]<=lows[j-1];
        negative<={negative[6:0],value<0};
        estimate<=product_sum[PROD_W-1:96];
        estimate_d<=estimate;
        residue_product<=estimate[31:0]*base;
        // Stage5: exact low32 provisional residue (proved less than2*base).
        provisional_r<=lows[4]-residue_product;estimate_e<=estimate_d;
        // Stage6: compare and subtract in parallel, with no wide quotient add.
        correction<=provisional_r>=base;subtracted_r<=provisional_r-base;
        provisional_d<=provisional_r;estimate_f<=estimate_e;
        // Stage7: isolated wide quotient increment and remainder selection.
        unsigned_q<=estimate_f+MAG_W'(correction);
        unsigned_r<=correction ? subtracted_r : provisional_d;
        // Stage8: sign negation separate from the Euclidean floor adjustment.
        signed_q<=negative[7] ? -$signed({1'b0,unsigned_q}) : $signed({1'b0,unsigned_q});
        negative_fraction<=negative[7] && unsigned_r!=0;
        signed_r<=negative[7] && unsigned_r!=0 ? base-unsigned_r : unsigned_r;
        // Stage9: floor, not truncation, for negative nonmultiples.
        quotient<=signed_q-$signed((MAG_W+1)'(negative_fraction));
        remainder<=signed_r;
        payloads[0]<=payload_in;
        for(int j=1;j<10;j=j+1)payloads[j]<=payloads[j-1];
    end
    always_ff @(posedge clk or negedge rst_n)
        if(!rst_n)valid<=0;else valid<={valid[8:0],in_valid};
    // synthesis translate_off
    initial if(MAG_W!=77 && MAG_W!=47)$fatal(1,"unsupported narrow magnitude width");
    always @(posedge clk)if(rst_n && in_valid && value=={1'b1,{MAG_W{1'b0}}})
        $fatal(1,"narrow divider input outside magnitude contract");
    always @(posedge clk)if(rst_n && in_valid && (base<2 || base>1000000000))
        $fatal(1,"narrow divider base outside contract");
    // synthesis translate_on
endmodule

// Exact reciprocal front end; range-observable quotient tail specialization.
// Legal base2..1e9, exact floor(2^96/base), stable for every consumed response.
// E0 -> E11, II1. quotient_range_error marks |floor(value/base)| >=2^QUOT_W.
// In-range quotient/remainder are exact. Out-of-range quotient bits MUST NOT
// be consumed: the caller preserves its original same-edge range fault.
module genefer_div_recip_range_token_v1 #(
    parameter int MAG_W=77, QUOT_W=47, PAYLOAD_W=1
) (
    input logic clk,rst_n,in_valid,
    input logic signed [MAG_W:0] value,
    input logic [31:0] base,
    input logic [95:0] reciprocal,
    input logic [PAYLOAD_W-1:0] payload_in,
    output logic out_valid,
    output logic signed [QUOT_W:0] quotient,
    output logic [31:0] remainder,
    output logic [PAYLOAD_W-1:0] payload_out,
    output logic quotient_range_error
);
    localparam int LIMBS=(MAG_W+26)/27,PROD_W=2*MAG_W;
    localparam int ROW01_W=(MAG_W<54 ? MAG_W : 54)+MAG_W;
    localparam int EST_W=QUOT_W<32 ? 32 : QUOT_W;
    logic [11:0] valid;
    logic [9:0] negative;
    logic [MAG_W-1:0] magnitude;
    logic [EST_W-1:0] estimate;
    logic [QUOT_W-1:0] estimate_d,estimate_e,estimate_f,unsigned_q;
    logic large_estimate,large_d,large_e,large_f,large_q,large_s;
    logic correction,negative_fraction;
    logic signed [QUOT_W:0] signed_q;
    logic [31:0] signed_r,provisional_d,subtracted_r;
    logic [31:0] lows[0:6],residue_product,unsigned_r,provisional_r;
    logic [PROD_W-1:0] shifted_rows[0:LIMBS-1],product_sum,row2_d;
    logic [ROW01_W-1:0] rows01;
    wire [MAG_W-1:0] reciprocal_short=reciprocal[95-:MAG_W];
    logic [PAYLOAD_W-1:0] payloads[0:11];
    for(genvar a=0;a<LIMBS;a=a+1)begin: limb
        localparam int LW=(a==LIMBS-1) ? MAG_W-a*27 : 27;
        localparam int PAIR_BITS=MAG_W<54 ? MAG_W : 54;
        localparam int HIGH_BITS=MAG_W>54 ? MAG_W-54 : 1;
        wire [LW-1:0] digit=magnitude[a*27+:LW];
        logic [LW+PAIR_BITS-1:0] pair_lo;
        logic [LW+HIGH_BITS-1:0] high_d;
        logic [LW+MAG_W-1:0] row;
        for(genvar b=0;b<LIMBS;b=b+1)begin: product
            localparam int RW=(b==LIMBS-1) ? MAG_W-b*27 : 27;
            wire [RW-1:0] reciprocal_digit=reciprocal_short[b*27+:RW];
            logic [LW+RW-1:0] partial;
            always_ff @(posedge clk)partial<=digit*reciprocal_digit;
        end
        always_ff @(posedge clk)
            pair_lo<=(LW+PAIR_BITS)'(product[0].partial)+((LW+PAIR_BITS)'(product[1].partial)<<27);
        if(LIMBS==3)begin: high_product
            always_ff @(posedge clk)high_d<=product[2].partial;
        end else begin: no_high_product
            assign high_d='0;
        end
        always_ff @(posedge clk)
            row<=(LW+MAG_W)'(pair_lo)+((LW+MAG_W)'(high_d)<<54);
        assign shifted_rows[a]=PROD_W'(row)<<(a*27);
    end
    always_ff @(posedge clk)rows01<=ROW01_W'(shifted_rows[0])+ROW01_W'(shifted_rows[1]);
    if(LIMBS==3)begin: high_row
        always_ff @(posedge clk)row2_d<=shifted_rows[2];
    end else begin: no_high_row
        assign row2_d='0;
    end
    assign product_sum=PROD_W'(rows01)+row2_d;
    assign out_valid=valid[11];
    assign payload_out=payloads[11];
    always_ff @(posedge clk)begin
        magnitude<=MAG_W'(value<0 ? $unsigned(-value) : $unsigned(value));
        lows[0]<=value<0 ? 32'($unsigned(-value)) : value[31:0];
        for(int j=1;j<7;j=j+1)lows[j]<=lows[j-1];
        negative<={negative[8:0],value<0};
        // E5: retain low32 for residue even when QUOT_W is only18.
        estimate<=product_sum[MAG_W+:EST_W];
        large_estimate<=|product_sum[PROD_W-1:MAG_W+QUOT_W];
        estimate_d<=estimate[QUOT_W-1:0];large_d<=large_estimate;
        residue_product<=estimate[31:0]*base;
        provisional_r<=lows[6]-residue_product;estimate_e<=estimate_d;large_e<=large_d;
        correction<=provisional_r>=base;subtracted_r<=provisional_r-base;
        provisional_d<=provisional_r;estimate_f<=estimate_e;large_f<=large_e;
        unsigned_q<=estimate_f+QUOT_W'(correction);
        large_q<=large_f || (correction && (&estimate_f));
        unsigned_r<=correction ? subtracted_r : provisional_d;
        signed_q<=negative[9] ? -$signed({1'b0,unsigned_q}) : $signed({1'b0,unsigned_q});
        large_s<=large_q;
        negative_fraction<=negative[9] && unsigned_r!=0;
        signed_r<=negative[9] && unsigned_r!=0 ? base-unsigned_r : unsigned_r;
        quotient<=signed_q-$signed((QUOT_W+1)'(negative_fraction));
        quotient_range_error<=large_s ||
            (negative_fraction && signed_q==-$signed({1'b0,{QUOT_W{1'b1}}}));
        remainder<=signed_r;
        payloads[0]<=payload_in;
        for(int j=1;j<12;j=j+1)payloads[j]<=payloads[j-1];
    end
    always_ff @(posedge clk or negedge rst_n)
        if(!rst_n)valid<=0;else valid<={valid[10:0],in_valid};
    // synthesis translate_off
    initial if(!((MAG_W==77 && QUOT_W==47)||(MAG_W==47 && QUOT_W==18)))
        $fatal(1,"range token requires exact carry consumer geometry");
    always @(posedge clk)if(rst_n && in_valid && value=={1'b1,{MAG_W{1'b0}}})
        $fatal(1,"range token input outside magnitude contract");
    always @(posedge clk)if(rst_n && in_valid && (base<2 || base>1000000000))
        $fatal(1,"range token base outside contract");
    // synthesis translate_on
endmodule

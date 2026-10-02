// Centered CRT for the checked27-bit three-prime profile; ordinary residues.
// Pair-step remainder pipelines:96 stages, II=1, accepted edge t -> t+95.
// Frozen64-stage retimed CRT unchanged; three reductions add11+11+10 stages.
// Full32-bit ports must carry canonical residues; not unchecked radix digits.
module genefer_crt3_27_pair_pipe (
    input logic clk,rst_n,in_valid,
    input logic [31:0] r1,r2,r3,
    output logic ready,out_valid,
    output logic signed [95:0] coefficient
);
    localparam logic [26:0] P1=27'd104857601,P2=27'd69206017,P3=27'd67239937;
    localparam logic [25:0] INV12=26'd44780362;
    localparam logic [23:0] INV123=24'd10355480;
    localparam logic [52:0] P12=53'd7256776917385217;
    localparam logic [78:0] MODULUS=79'd487945222748036195811329;
    wire [26:0] r1_small=r1[26:0],r2_small=r2[26:0],r3_small=r3[26:0];
    logic [26:0] r1_mod2,delta2,delta3;
    logic [27:0] delta2_work,delta3_work,delta2_diff,delta3_diff;
    logic [26:0] r2_d;
    logic [53:0] input_payload[0:1];
    logic [52:0] x_payload_d;
    logic [1:0] input_valid;
    logic vx_d;
    logic [2:0] va,vb,vc,vd;
    logic [41:0] a_lo;
    logic [36:0] a_hi;
    logic [52:0] a_product;
    logic [53:0] a_payload[0:2];
    logic v2,vx,v3;
    logic [31:0] t2,x_mod3,t3;
    logic [53:0] p2,b_payload[0:2];
    logic [42:0] b_lo;
    logic [37:0] b_hi;
    logic [53:0] b_product,x12_work;
    logic [52:0] x12;
    logic [79:0] px;
    logic [39:0] c_lo;
    logic [34:0] c_hi;
    logic [50:0] c_product;
    logic [52:0] c_payload[0:2],p3,d_payload[0:1];
    logic [68:0] d_lo;
    logic [63:0] d_hi;
    logic [79:0] d_product,value_work;
    logic [78:0] value;

    assign ready=1'b1;
    // P1<2*P2, so one subtraction reduces a canonical r1 moduloP2.
    // Differences of canonical27-bit values fit signed28 bits exactly.
    assign delta2_work=delta2_diff[27] ? delta2_diff+{1'b0,P2} : delta2_diff;
    assign delta3_work=delta3_diff[27] ? delta3_diff+{1'b0,P3} : delta3_diff;
    assign x12_work=b_product+{27'b0,b_payload[1][53:27]};
    assign value_work=d_product+{27'b0,d_payload[1]};

    genefer_mod27_pair_pipe #(.WORD_W(53),.MODULUS(P2),.PAYLOAD_W(54)) reduce_t2 (
        .clk,.rst_n,.in_valid(va[2]),.word_in(a_product),
        .payload_in(a_payload[2]),.out_valid(v2),.remainder(t2),.payload_out(p2)
    );
    genefer_mod27_pair_pipe #(.WORD_W(53),.MODULUS(P3),.PAYLOAD_W(80)) reduce_x12 (
        .clk,.rst_n,.in_valid(vb[2]),.word_in(x12),
        .payload_in({x12,b_payload[2][26:0]}),.out_valid(vx),.remainder(x_mod3),.payload_out(px)
    );
    genefer_mod27_pair_pipe #(.WORD_W(51),.MODULUS(P3),.PAYLOAD_W(53)) reduce_t3 (
        .clk,.rst_n,.in_valid(vc[2]),.word_in(c_product),
        .payload_in(c_payload[2]),.out_valid(v3),.remainder(t3),.payload_out(p3)
    );
    always_ff @(posedge clk)begin
        r1_mod2<=r1_small>=P2 ? r1_small-P2 : r1_small;
        r2_d<=r2_small;input_payload[0]<={r1_small,r3_small};
        delta2_diff<={1'b0,r2_d}-{1'b0,r1_mod2};
        input_payload[1]<=input_payload[0];
        delta2<=delta2_work[26:0];a_payload[0]<=input_payload[1];
        a_lo<=INV12*delta2[15:0];a_hi<=INV12*delta2[26:16];a_payload[1]<=a_payload[0];
        a_product<={11'b0,a_lo}+{a_hi,16'b0};a_payload[2]<=a_payload[1];

        b_lo<=P1*t2[15:0];b_hi<=P1*t2[26:16];b_payload[0]<=p2;
        b_product<={11'b0,b_lo}+{b_hi,16'b0};b_payload[1]<=b_payload[0];
        x12<=x12_work[52:0];b_payload[2]<=b_payload[1];

        delta3_diff<={1'b0,px[26:0]}-{1'b0,x_mod3[26:0]};
        x_payload_d<=px[79:27];
        delta3<=delta3_work[26:0];c_payload[0]<=x_payload_d;
        c_lo<=INV123*delta3[15:0];c_hi<=INV123*delta3[26:16];c_payload[1]<=c_payload[0];
        c_product<={11'b0,c_lo}+{c_hi,16'b0};c_payload[2]<=c_payload[1];

        d_lo<=P12*t3[15:0];d_hi<=P12*t3[26:16];d_payload[0]<=p3;
        d_product<={11'b0,d_lo}+{d_hi,16'b0};d_payload[1]<=d_payload[0];
        value<=value_work[78:0];
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin input_valid<=0;vx_d<=0;va<=0;vb<=0;vc<=0;vd<=0;out_valid<=0;coefficient<=0;end
        else begin
            input_valid<={input_valid[0],in_valid};vx_d<=vx;
            va<={va[1:0],input_valid[1]};vb<={vb[1:0],v2};vc<={vc[1:0],vx_d};vd<={vd[1:0],v3};
            out_valid<=vd[2];
            if(vd[2])coefficient<=value>(MODULUS>>1) ?
                $signed({17'b0,value})-$signed({17'b0,MODULUS}) : $signed({17'b0,value});
        end
    end
    // synthesis translate_off
    always @(posedge clk)if(rst_n)begin
        if(in_valid && (r1>=32'(P1) || r2>=32'(P2) || r3>=32'(P3)))$fatal(1,"noncanonical CRT27 input");
        if(input_valid[1] && delta2_work>={1'b0,P2})$fatal(1,"CRT27 delta2 bound");
        if(vx_d && delta3_work>={1'b0,P3})$fatal(1,"CRT27 delta3 bound");
        if(v2 && t2>=32'(P2))$fatal(1,"CRT27 t2 bound");
        if(vx && x_mod3>=32'(P3))$fatal(1,"CRT27 x_mod3 bound");
        if(v3 && t3>=32'(P3))$fatal(1,"CRT27 t3 bound");
        if(vb[1] && (x12_work[53] || x12_work>=54'(P12)))$fatal(1,"CRT27 x12 bound");
        if(vd[1] && (value_work[79] || value_work>=80'(MODULUS)))$fatal(1,"CRT27 value bound");
    end
    // synthesis translate_on
endmodule

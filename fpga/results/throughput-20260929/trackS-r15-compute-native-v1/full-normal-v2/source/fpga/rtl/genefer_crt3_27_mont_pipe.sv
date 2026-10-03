// Isolated Montgomery-constant CRT27 candidate; ordinary canonical residues.
// II=1,16 stages: accepted edge k -> output edge k+15 (frozen CRT: k+60).
// Raw input capture isolates the memory-output path from the modular subtracts.
// No whole-core substitution, measured resource or timing benefit is implied.
module genefer_crt3_27_mont_pipe (
    input logic clk,rst_n,in_valid,
    input logic [31:0] r1,r2,r3,
    output logic ready,out_valid,
    output logic signed [95:0] coefficient
);
    localparam logic [26:0] P1=27'd104857601,P2=27'd69206017,P3=27'd67239937;
    localparam logic [31:0] C2=32'd12212947;
    localparam logic [31:0] CA=32'd28766354;
    localparam logic [31:0] CB=32'd62755090;
    localparam logic [52:0] P12=53'd7256776917385217;
    localparam logic [78:0] MODULUS=79'd487945222748036195811329;
    logic [14:0] valid_pipe;
    logic [26:0] r2_input,r3_input,r2_d,r3_d,r1_mod2,r1_mod3,delta2;
    logic [26:0] r1_stage0;wire [26:0] r1_tail;wire [26:0] d3_tail;
    wire [27:0] delta2_diff={1'b0,r2_d}-{1'b0,r1_mod2};
    wire [27:0] delta3_diff={1'b0,r3_d}-{1'b0,r1_mod3};
    wire [27:0] delta2_work=delta2_diff[27] ? delta2_diff+{1'b0,P2} : delta2_diff;
    wire [27:0] delta3_work=delta3_diff[27] ? delta3_diff+{1'b0,P3} : delta3_diff;
    logic v2,va3,vb3;
    logic [31:0] t2,a3,b3;
    wire [26:0] t2_mod3=t2[26:0]>=P3 ? t2[26:0]-P3 : t2[26:0];
    logic [27:0] t3_sum;
    wire [27:0] t3_work=t3_sum>={1'b0,P3} ? t3_sum-{1'b0,P3} : t3_sum;
    logic [26:0] t3;

    // Plain27x27 and53x27 products; never split into16-bit halves.
    logic [53:0] p1_t2;
    logic [26:0] r1_d;
    wire [53:0] x12_work=p1_t2+{27'b0,r1_d};
    wire [52:0] x12_tail;
    logic [79:0] p12_t3;
    wire [79:0] value_work=p12_t3+{27'b0,x12_tail};
    logic [78:0] value;
    wire signed [95:0] centered_work=value>(MODULUS>>1) ?
        $signed({17'b0,value})-$signed({17'b0,MODULUS}) : $signed({17'b0,value});

    genefer_stream27_r15_numeric_delay_mlab_v1 #(.WORD_W(27),.DELAY(6)) r15_r1_history (
        .clk,.rst_n,.write_word(r1_stage0),.head(r1_tail));
    genefer_stream27_r15_numeric_delay_mlab_v1 #(.WORD_W(27),.DELAY(5)) r15_d3_history (
        .clk,.rst_n,.write_word(delta3_work[26:0]),.head(d3_tail));
    genefer_stream27_r15_numeric_delay_mlab_v1 #(.WORD_W(53),.DELAY(6)) r15_x12_history (
        .clk,.rst_n,.write_word(x12_work[52:0]),.head(x12_tail));
    assign ready=1'b1;
    // Mont(a,C)=a*C*2^-32 modP. Constants below encode ordinary multipliers.
    // C2=P1^-1*2^32 modP2. Input k+3, output k+6.
    genefer_montgomery_mul27_sparse_pipe #(.P(32'(P2)),.Q(32'd2-32'(P2))) mont_t2 (
        .clk,.rst_n,.in_valid(valid_pipe[2]),.lhs({5'b0,delta2}),.rhs(C2),
        .out_valid(v2),.result(t2)
    );
    // CA=(P1*P2)^-1*2^32 modP3. Both P3 helpers: input k+7, output k+10.
    genefer_montgomery_mul27_sparse_pipe #(.P(32'(P3)),.Q(32'd2-32'(P3))) mont_a3 (
        .clk,.rst_n,.in_valid(valid_pipe[6]),.lhs({5'b0,d3_tail}),.rhs(CA),
        .out_valid(va3),.result(a3)
    );
    // CB=-P2^-1*2^32 modP3.
    genefer_montgomery_mul27_sparse_pipe #(.P(32'(P3)),.Q(32'd2-32'(P3))) mont_b3 (
        .clk,.rst_n,.in_valid(valid_pipe[6]),.lhs({5'b0,t2_mod3}),.rhs(CB),
        .out_valid(vb3),.result(b3)
    );

    // Valid-only local reset, like the frozen CRT: payload is unreset and
    // unconditionally advances; flushed validity quarantines all stale values.
    always_ff @(posedge clk)begin
        // k: capture only raw canonical low27 bits; full32-bit guard is below.
        r1_stage0<=r1[26:0];r2_input<=r2[26:0];r3_input<=r3[26:0];
        // R15 continuous D6 r1 tail in MLAB; stage0 reduction remains literal.
        // k+1: P1<2*P2 and2*P3, so each reduction is one subtraction.
        r1_mod2<=r1_stage0>=P2 ? r1_stage0-P2 : r1_stage0;
        r1_mod3<=r1_stage0>=P3 ? r1_stage0-P3 : r1_stage0;
        r2_d<=r2_input;r3_d<=r3_input;
        // k+2: signed28-bit differences plus modulus on borrow.
        delta2<=delta2_work[26:0];
        // R15 continuous D5 delta3 payload in MLAB.

        // k+7: reconstruct x12 in parallel with the two P3 helpers.
        p1_t2<=P1*t2[26:0];r1_d<=r1_tail;
        // k+8 x12, then short register delay through k+13.
        // R15 continuous D6 reconstructed x12 payload in MLAB.

        // k+11 sum is below2*P3; k+12 correction yields canonical t3.
        t3_sum<={1'b0,a3[26:0]}+{1'b0,b3[26:0]};
        t3<=t3_work[26:0];
        // k+13 full product; k+14 reconstructed value in [0,M).
        p12_t3<=P12*t3;
        value<=value_work[78:0];
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin valid_pipe<=0;out_valid<=0;coefficient<=0;end
        else begin
            valid_pipe<={valid_pipe[13:0],in_valid};
            out_valid<=valid_pipe[14];
            // k+15: strict centering rule and invalid-cycle output hold.
            if(valid_pipe[14])coefficient<=centered_work;
        end
    end
    // synthesis translate_off
    // CRT27_CONSTANT_CHECK_BEGIN
    initial begin
        if(P12!=53'(96'(P1)*96'(P2)) ||
           MODULUS!=79'(96'(P1)*96'(P2)*96'(P3)))
            $fatal(1,"CRT27 product constants");
        if(C2>=32'(P2) || CA>=32'(P3) || CB>=32'(P3) ||
           (96'(C2)*96'(P1))%96'(P2)!=96'd4294967296%96'(P2) ||
           (96'(CA)*96'(P12))%96'(P3)!=96'd4294967296%96'(P3) ||
           (96'(CB)*96'(P2))%96'(P3)!=(96'(P3)-(96'd4294967296%96'(P3))))
            $fatal(1,"CRT27 Montgomery constants");
        if(28'(P1)>=28'(P2)*28'd2 || 28'(P1)>=28'(P3)*28'd2 ||
           28'(P2)>=28'(P3)*28'd2)
            $fatal(1,"CRT27 one-subtraction preconditions");
    end
    // CRT27_CONSTANT_CHECK_END
    always @(posedge clk)if(rst_n)begin
        if(in_valid && (r1>=32'(P1) || r2>=32'(P2) || r3>=32'(P3)))$fatal(1,"noncanonical CRT27 input");
        if(v2!==valid_pipe[6] || va3!==valid_pipe[10] || vb3!==valid_pipe[10])$fatal(1,"CRT27 Montgomery valid alignment");
        if(valid_pipe[1] && delta2_work>={1'b0,P2})$fatal(1,"CRT27 delta2 bound");
        if(valid_pipe[1] && delta3_work>={1'b0,P3})$fatal(1,"CRT27 delta3 bound");
        if(v2 && t2>=32'(P2))$fatal(1,"CRT27 t2 bound");
        if(v2 && t2_mod3>=P3)$fatal(1,"CRT27 t2_mod3 bound");
        if(valid_pipe[7] && (x12_work[53] || x12_work>=54'(P12)))$fatal(1,"CRT27 x12 bound");
        if(va3 && (a3>=32'(P3) || b3>=32'(P3)))$fatal(1,"CRT27 P3 result bound");
        if(valid_pipe[11] && t3_work>={1'b0,P3})$fatal(1,"CRT27 t3 bound");
        if(valid_pipe[13] && (value_work[79] || value_work>=80'(MODULUS)))$fatal(1,"CRT27 value bound");
    end
    // synthesis translate_on
endmodule

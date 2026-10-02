// Throughput-oriented exact centered CRT for canonical, non-Montgomery S3
// residues. One accepted coefficient per cycle, no output backpressure.
// 61 registered stages: an input sampled on edge t produces out_valid on
// edge t+60. rst_n cancels every in-flight coefficient; invalid output holds.
// All products are split into 16-bit operand chunks and then registered sums.
// No division or remainder operators and no FPGA primitive dependencies.
module genefer_crt3_pipe (
    input logic clk, rst_n, in_valid,
    input logic [31:0] r1, r2, r3,
    output logic ready, out_valid,
    output logic signed [95:0] coefficient
);
    localparam logic [31:0] P1=32'd2130706433, P2=32'd2113929217,
        P3=32'd2013265921, INV12=32'd2113929091, INV123=32'd1150438012;
    localparam logic [63:0] P12=64'd4504162581568552961;
    localparam logic [95:0] MODULUS=96'd9068077028115350401664942081;
    logic [31:0] r1_mod2;
    logic [2:0] va;
    logic [31:0] delta2;
    logic [47:0] a_lo, a_hi;
    logic [63:0] a_product;
    logic [63:0] a_payload [0:2];
    logic v2;
    logic [31:0] t2;
    logic [63:0] p2;
    logic [2:0] vb;
    logic [47:0] b_lo,b_hi;
    logic [63:0] b_product,x12;
    logic [63:0] b_payload [0:2];
    logic vx;
    logic [31:0] x_mod3;
    logic [95:0] px;
    logic [2:0] vc;
    logic [31:0] delta3;
    logic [47:0] c_lo,c_hi;
    logic [63:0] c_product;
    logic [63:0] c_payload [0:2];
    logic v3;
    logic [31:0] t3;
    logic [63:0] p3;
    logic [2:0] vd;
    logic [79:0] d_lo,d_hi;
    logic [95:0] d_product,value;
    logic [63:0] d_payload [0:1];

    assign ready=1'b1;
    assign r1_mod2=(r1>=P2) ? r1-P2 : r1;
    genefer_mod64_pipe #(.MODULUS(P2),.PAYLOAD_W(64)) reduce_t2 (
        .clk, .rst_n, .in_valid(va[2]), .word_in(a_product),
        .payload_in(a_payload[2]), .out_valid(v2), .remainder(t2), .payload_out(p2)
    );
    genefer_mod64_pipe #(.MODULUS(P3),.PAYLOAD_W(96)) reduce_x12 (
        .clk, .rst_n, .in_valid(vb[2]), .word_in(x12),
        .payload_in({x12,b_payload[2][31:0]}), .out_valid(vx),
        .remainder(x_mod3), .payload_out(px)
    );
    genefer_mod64_pipe #(.MODULUS(P3),.PAYLOAD_W(64)) reduce_t3 (
        .clk, .rst_n, .in_valid(vc[2]), .word_in(c_product),
        .payload_in(c_payload[2]), .out_valid(v3), .remainder(t3), .payload_out(p3)
    );
    always_ff @(posedge clk) begin
        delta2 <= (r2>=r1_mod2) ? r2-r1_mod2 : r2+P2-r1_mod2;
        a_payload[0]<={r1,r3};
        a_lo<=INV12*delta2[15:0]; a_hi<=INV12*delta2[31:16];
        a_payload[1]<=a_payload[0];
        a_product<={16'b0,a_lo}+{a_hi,16'b0};
        a_payload[2]<=a_payload[1];

        b_lo<=P1*t2[15:0]; b_hi<=P1*t2[31:16];
        b_payload[0]<=p2;
        b_product<={16'b0,b_lo}+{b_hi,16'b0};
        b_payload[1]<=b_payload[0];
        x12<=b_product+{32'b0,b_payload[1][63:32]};
        b_payload[2]<=b_payload[1];

        delta3 <= (px[31:0]>=x_mod3) ? px[31:0]-x_mod3 : px[31:0]+P3-x_mod3;
        c_payload[0]<=px[95:32];
        c_lo<=INV123*delta3[15:0]; c_hi<=INV123*delta3[31:16];
        c_payload[1]<=c_payload[0];
        c_product<={16'b0,c_lo}+{c_hi,16'b0};
        c_payload[2]<=c_payload[1];

        d_lo<=P12*t3[15:0]; d_hi<=P12*t3[31:16];
        d_payload[0]<=p3;
        d_product<={16'b0,d_lo}+{d_hi,16'b0};
        d_payload[1]<=d_payload[0];
        value<=d_product+{32'b0,d_payload[1]};
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            va<=0; vb<=0; vc<=0; vd<=0; out_valid<=0; coefficient<=0;
        end else begin
            va<={va[1:0],in_valid}; vb<={vb[1:0],v2};
            vc<={vc[1:0],vx}; vd<={vd[1:0],v3};
            out_valid<=vd[2];
            if (vd[2]) coefficient<=$signed(value>(MODULUS>>1) ? value-MODULUS : value);
        end
    end
endmodule

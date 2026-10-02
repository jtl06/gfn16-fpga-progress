// Exact centered CRT for the three S3 fields, standard (not Montgomery) inputs.
// Shared four-bit-per-cycle remainder unit replaces three wide % networks.
// Canonical inputs r_i < P_i; accept only when ready. Signed 96-bit output.
module genefer_crt3 (
    input logic clk, rst_n, in_valid,
    input logic [31:0] r1, r2, r3,
    output logic ready, out_valid,
    output logic signed [95:0] coefficient
);
    localparam logic [63:0] P1 = 64'd2130706433, P2 = 64'd2113929217, P3 = 64'd2013265921;
    localparam logic [95:0] P12 = 96'd4504162581568552961;
    localparam logic [95:0] MODULUS = 96'd9068077028115350401664942081;
    typedef enum logic [3:0] {IDLE, DELTA2, START_T2, REDUCE, MAKE_X12, ADD_X12,
        START_X12, MAKE_T3, START_T3, MAKE_VALUE, ADD_VALUE, CENTER} state_t;
    state_t state;
    logic [31:0] a, b, c, delta_reg;
    logic [63:0] x12, x12_product;
    logic [95:0] value, wide_product;
    logic [63:0] r1_p2, delta2, delta3;
    logic [63:0] reduce_word, word_next;
    logic [31:0] reduce_rem, rem_next, reduce_mod;
    logic [32:0] work_rem;
    logic [3:0] round;
    logic [1:0] phase;
    assign ready = state == IDLE;
    assign r1_p2 = {32'b0,a} >= P2 ? {32'b0,a}-P2 : {32'b0,a};
    assign delta2 = {32'b0,b} >= r1_p2 ? {32'b0,b}-r1_p2 : {32'b0,b}+P2-r1_p2;
    assign delta3 = {32'b0,c} >= {32'b0,reduce_rem} ? {32'b0,c}-{32'b0,reduce_rem} : {32'b0,c}+P3-{32'b0,reduce_rem};
    always_comb begin
        word_next=reduce_word; rem_next=reduce_rem; work_rem=0;
        for(int k=0;k<4;k=k+1) begin
            work_rem={rem_next,word_next[63]};
            word_next=word_next<<1;
            if(work_rem>={1'b0,reduce_mod}) work_rem=work_rem-{1'b0,reduce_mod};
            rem_next=work_rem[31:0];
        end
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state<=IDLE; out_valid<=0; coefficient<=0;
            a<=0; b<=0; c<=0; delta_reg<=0; x12<=0; value<=0; x12_product<=0; wide_product<=0;
            reduce_word<=0; reduce_rem<=0; reduce_mod<=0; round<=0; phase<=0;
        end else begin
            out_valid<=0;
            case(state)
                IDLE: if(in_valid) begin
                    a<=r1; b<=r2; c<=r3; state<=DELTA2;
                end
                DELTA2: begin delta_reg<=delta2[31:0]; state<=START_T2; end
                START_T2: begin
                    reduce_word<={32'b0,delta_reg}*64'd2113929091;
                    reduce_rem<=0; reduce_mod<=P2[31:0]; round<=0; phase<=0; state<=REDUCE;
                end
                REDUCE: begin
                    reduce_word<=word_next; reduce_rem<=rem_next; round<=round+1;
                    if(round==15) begin
                        case(phase)
                            0: state<=MAKE_X12;
                            1: state<=MAKE_T3;
                            default: state<=MAKE_VALUE;
                        endcase
                    end
                end
                MAKE_X12: begin x12_product<=P1*{32'b0,reduce_rem}; state<=ADD_X12; end
                ADD_X12: begin x12<={32'b0,a}+x12_product; state<=START_X12; end
                START_X12: begin
                    reduce_word<=x12; reduce_rem<=0; reduce_mod<=P3[31:0];
                    round<=0; phase<=1; state<=REDUCE;
                end
                MAKE_T3: begin delta_reg<=delta3[31:0]; state<=START_T3; end
                START_T3: begin
                    reduce_word<={32'b0,delta_reg}*64'd1150438012; reduce_rem<=0;
                    round<=0; phase<=2; state<=REDUCE;
                end
                MAKE_VALUE: begin wide_product<=P12*{64'b0,reduce_rem}; state<=ADD_VALUE; end
                ADD_VALUE: begin value<={32'b0,x12}+wide_product; state<=CENTER; end
                CENTER: begin
                    coefficient <= $signed(value > (MODULUS>>1) ? value-MODULUS : value);
                    out_valid<=1; state<=IDLE;
                end
                default: state<=IDLE;
            endcase
        end
    end
endmodule

// Canonical radix-b reduction using b^N == -1. Signed 96-bit coefficients.
// Four-bit-per-cycle restoring division, plus a canonical-digit fast path.
// One physical RAM port with synchronous reads; arrays are never reset.
// Contract: N=2^size_log2 >=2, 2<=base<=10^9, |input coefficient|<2^94.
// Canonical -1 is represented by [-1,0,...]. Max 64 sweeps, then error.
module genefer_carry #(parameter int AW=16) (
    input logic clk, rst_n, load_we, read_en, start,
    input logic [AW-1:0] host_addr,
    input logic signed [95:0] write_data,
    input logic [4:0] size_log2,
    input logic [31:0] base,
    output logic read_valid,
    output logic signed [95:0] read_data,
    output logic busy, done, error,
    output logic [63:0] cycles,
    output logic [6:0] passes
);
    typedef enum logic [3:0] {IDLE, READ, DIV_START, DIV_RUN, DIV_SIGN, APPLY, FOLD_READ, FOLD_WRITE, SPECIAL} state_t;
    state_t state;
    logic signed [95:0] mem [0:(1<<AW)-1];
    logic signed [95:0] value_reg, carry, base_reg, total, quotient, remainder_value, digit, next_carry;
    logic [31:0] n, idx;
    logic all_max;
    logic [95:0] div_q, div_q_next;
    logic [31:0] div_r, div_r_next;
    logic [32:0] div_work;
    logic div_negative;
    logic signed [32:0] signed_rem;
    logic [4:0] div_round;
    logic [AW-1:0] ram_addr;
    logic ram_en, ram_we;
    logic signed [95:0] ram_write;
    assign total = value_reg+carry;
    assign digit = remainder_value<0 ? remainder_value+base_reg : remainder_value;
    assign next_carry = remainder_value<0 ? quotient-96'sd1 : quotient;
    assign read_data = value_reg;
    assign signed_rem=div_negative ? -$signed({1'b0,div_r}) : $signed({1'b0,div_r});
    // Four unsigned long-division steps. The partial remainder is < base,
    // so each shifted remainder fits in 33 bits, including base=10^9.
    always_comb begin
        div_q_next=div_q; div_r_next=div_r; div_work=0;
        for(int k=0;k<4;k=k+1) begin
            div_work={div_r_next,div_q_next[95]};
            div_q_next=div_q_next<<1;
            if(div_work>={1'b0,base_reg[31:0]}) begin
                div_work=div_work-{1'b0,base_reg[31:0]};
                div_q_next[0]=1;
            end
            div_r_next=div_work[31:0];
        end
    end
    always_comb begin
        ram_addr=AW'(idx); ram_en=0; ram_we=0; ram_write=digit;
        case(state)
            IDLE: if(!start) begin
                ram_addr=host_addr; ram_en=load_we || read_en; ram_we=load_we; ram_write=write_data;
            end
            READ: ram_en=1;
            APPLY: begin ram_en=1; ram_we=1; end
            FOLD_READ: begin ram_addr=0; ram_en=1; end
            FOLD_WRITE: begin ram_addr=0; ram_en=1; ram_we=1; ram_write=value_reg-carry; end
            SPECIAL: begin ram_en=1; ram_we=1; ram_write=idx==0 ? -96'sd1 : 96'sd0; end
            default: ;
        endcase
    end
    always_ff @(posedge clk) begin
        if(rst_n && ram_en) begin
            if(ram_we) mem[ram_addr]<=ram_write;
            else value_reg<=mem[ram_addr];
        end
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE; busy<=0; done<=0; error<=0; read_valid<=0;
            n<=0; idx<=0; carry<=0; base_reg<=2; cycles<=0; passes<=0; all_max<=0;
            div_q<=0; div_r<=0; div_round<=0; div_negative<=0; quotient<=0; remainder_value<=0;
        end else begin
            done<=0; read_valid<=state==IDLE && !start && read_en && !load_we;
            if(busy) cycles<=cycles+1;
            case(state)
                IDLE: if(start) begin
                    error<=0; cycles<=0; passes<=0;
                    if(size_log2<1 || int'(size_log2)>AW || base<2 || base>1000000000) begin error<=1; done<=1; end
                    else begin
                        n<=32'd1<<size_log2; idx<=0; base_reg<=$signed({64'b0,base});
                        carry<=0; all_max<=1; passes<=1; busy<=1; state<=READ;
                    end
                end
                READ: state<=DIV_START;
                DIV_START: begin
                    if(total>=0 && total<base_reg) begin
                        quotient<=0; remainder_value<=total; state<=APPLY;
                    end else begin
                        div_q<=total<0 ? $unsigned(-total) : $unsigned(total);
                        div_r<=0; div_round<=0; div_negative<=total<0; state<=DIV_RUN;
                    end
                end
                DIV_RUN: begin
                    div_q<=div_q_next; div_r<=div_r_next; div_round<=div_round+1;
                    if(div_round==23) state<=DIV_SIGN;
                end
                DIV_SIGN: begin
                    // Separate sign correction from the divider's compare chain.
                    quotient<=div_negative ? -$signed(div_q) : $signed(div_q);
                    remainder_value<={{63{signed_rem[32]}},signed_rem};
                    state<=APPLY;
                end
                APPLY: begin
                    carry<=next_carry; all_max<=all_max && digit==base_reg-1;
                    if(idx!=n-1) begin idx<=idx+1; state<=READ; end
                    else if(next_carry==0) begin busy<=0; done<=1; state<=IDLE; end
                    else if(next_carry == -96'sd1 && all_max && digit==base_reg-1) begin idx<=0; state<=SPECIAL; end
                    else if(passes==64) begin error<=1; busy<=0; done<=1; state<=IDLE; end
                    else state<=FOLD_READ;
                end
                FOLD_READ: state<=FOLD_WRITE;
                FOLD_WRITE: begin carry<=0; all_max<=1; idx<=0; passes<=passes+1; state<=READ; end
                SPECIAL: if(idx==n-1) begin busy<=0; done<=1; state<=IDLE; end else idx<=idx+1;
                default: begin state<=IDLE; busy<=0; done<=1; error<=1; end
            endcase
        end
    end
endmodule

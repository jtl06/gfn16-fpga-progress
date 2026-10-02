// Exact reciprocal carry normalization. Same contract as genefer_carry.
// R=floor(2^96/base) is constructed in 96 cycles, once per operation.
// For x<2^96, floor(x*R/2^96) is at most one below floor(x/base).
// The provisional remainder is <2*base<=2e9, so its low32 recovery is exact.
// No coefficient truncation: signed96 inputs must have |coefficient|<2^94.
module genefer_carry_fast #(parameter int AW=16) (
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
    typedef enum logic [4:0] {IDLE, RECIP, READ, DIV_START, DIV_MUL,
        DIV_ROWS, DIV_SUM, DIV_REM, DIV_CORRECT, DIV_SIGN, APPLY,
        FOLD_READ, FOLD_WRITE, SPECIAL} state_t;
    state_t state;
    logic signed [95:0] mem [0:(1<<AW)-1];
    logic signed [95:0] value_reg, carry, base_reg, total, quotient, remainder_value, digit, next_carry;
    logic [31:0] n, idx;
    logic all_max;
    logic [95:0] reciprocal, magnitude, estimate, unsigned_q;
    logic [31:0] reciprocal_rem, unsigned_r, residue_product, provisional_rem;
    logic [32:0] reciprocal_shift;
    logic [6:0] reciprocal_round;
    logic div_negative;
    logic signed [32:0] signed_rem;
    logic [63:0] partial [0:2][0:2];
    logic [127:0] rows [0:2];
    logic [191:0] product_sum;
    logic [AW-1:0] ram_addr;
    logic ram_en, ram_we;
    logic signed [95:0] ram_write;
    assign total = value_reg+carry;
    assign digit = remainder_value<0 ? remainder_value+base_reg : remainder_value;
    assign next_carry = remainder_value<0 ? quotient-96'sd1 : quotient;
    assign read_data = value_reg;
    assign signed_rem=div_negative ? -$signed({1'b0,unsigned_r}) : $signed({1'b0,unsigned_r});
    assign reciprocal_shift={reciprocal_rem,1'b0};
    assign product_sum={64'b0,rows[0]}+{32'b0,rows[1],32'b0}+{rows[2],64'b0};
    assign provisional_rem=magnitude[31:0]-residue_product;
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
        // Datapath registers do not need reset: each is overwritten before use.
        if(state==DIV_MUL)
            for(int a=0;a<3;a=a+1)
                for(int b=0;b<3;b=b+1)
                    partial[a][b]<=magnitude[a*32+:32]*reciprocal[b*32+:32];
        if(state==DIV_ROWS)
            for(int a=0;a<3;a=a+1)
                rows[a]<={64'b0,partial[a][0]}+{32'b0,partial[a][1],32'b0}+{partial[a][2],64'b0};
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE; busy<=0; done<=0; error<=0; read_valid<=0;
            n<=0; idx<=0; carry<=0; base_reg<=2; cycles<=0; passes<=0; all_max<=0;
            reciprocal<=0; reciprocal_rem<=0; reciprocal_round<=0;
            magnitude<=0; estimate<=0; unsigned_q<=0; unsigned_r<=0; residue_product<=0;
            div_negative<=0; quotient<=0; remainder_value<=0;
        end else begin
            done<=0; read_valid<=state==IDLE && !start && read_en && !load_we;
            if(busy) cycles<=cycles+1;
            case(state)
                IDLE: if(start) begin
                    error<=0; cycles<=0; passes<=0;
                    if(size_log2<1 || int'(size_log2)>AW || base<2 || base>1000000000) begin error<=1; done<=1; end
                    else begin
                        n<=32'd1<<size_log2; idx<=0; base_reg<=$signed({64'b0,base});
                        carry<=0; all_max<=1; passes<=1; busy<=1; state<=RECIP;
                        reciprocal<=0; reciprocal_rem<=1; reciprocal_round<=0;
                    end
                end
                RECIP: begin
                    reciprocal_round<=reciprocal_round+1;
                    if(reciprocal_shift>={1'b0,base_reg[31:0]}) begin
                        reciprocal_rem<=32'(reciprocal_shift-{1'b0,base_reg[31:0]});
                        reciprocal<={reciprocal[94:0],1'b1};
                    end else begin
                        reciprocal_rem<=reciprocal_shift[31:0];
                        reciprocal<={reciprocal[94:0],1'b0};
                    end
                    if(reciprocal_round==95) state<=READ;
                end
                READ: state<=DIV_START;
                DIV_START: begin
                    if(total>=0 && total<base_reg) begin
                        quotient<=0; remainder_value<=total; state<=APPLY;
                    end else begin
                        magnitude<=total<0 ? $unsigned(-total) : $unsigned(total);
                        div_negative<=total<0; state<=DIV_MUL;
                    end
                end
                DIV_MUL: state<=DIV_ROWS;
                DIV_ROWS: state<=DIV_SUM;
                DIV_SUM: begin estimate<=product_sum[191:96]; state<=DIV_REM; end
                DIV_REM: begin residue_product<=estimate[31:0]*base_reg[31:0]; state<=DIV_CORRECT; end
                DIV_CORRECT: begin
                    unsigned_q<=estimate+(provisional_rem>=base_reg[31:0] ? 96'd1 : 96'd0);
                    unsigned_r<=provisional_rem>=base_reg[31:0] ? provisional_rem-base_reg[31:0] : provisional_rem;
                    state<=DIV_SIGN;
                end
                DIV_SIGN: begin
                    quotient<=div_negative ? -$signed(unsigned_q) : $signed(unsigned_q);
                    remainder_value<={{63{signed_rem[32]}},signed_rem}; state<=APPLY;
                end
                APPLY: begin
                    carry<=next_carry; all_max<=all_max && digit==base_reg-1;
                    // After the first sweep every untouched high digit is
                    // canonical. Once the folded carry dies, those digits
                    // cannot change; avoid a redundant full-memory rescan.
                    if(passes>1 && next_carry==0) begin busy<=0; done<=1; state<=IDLE; end
                    else if(idx!=n-1) begin idx<=idx+1; state<=READ; end
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

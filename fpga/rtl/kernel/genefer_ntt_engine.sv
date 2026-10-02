// Serial engine with explicit true-dual-port data RAM and single-read root RAM.
// Natural-order load/read interface; internal bit reversal for radix-2 DIT.
// op 0: NTT (inverse applies caller-supplied Montgomery N^-1 scale).
// op 1: pointwise square; op 2: multiply by per-element root table;
// op 3: multiply by caller-supplied scalar (1 converts out of Montgomery).
// Host supplies validated root tables; data/root RAMs are intentionally NOT reset.
// Reload all data and required roots after reset. Writes while busy are ignored.
module genefer_ntt_engine #(
    parameter int AW = 16,
    parameter logic [31:0] P = 32'd2130706433,
    parameter logic [31:0] Q = 32'd2164260865
) (
    input logic clk, rst_n,
    input logic load_we, root_we, read_en,
    input logic [AW-1:0] host_addr,
    input logic [31:0] write_data,
    output logic read_valid,
    output logic [31:0] read_data,
    input logic start, inverse,
    input logic [1:0] op,
    input logic [4:0] size_log2,
    input logic [31:0] scale,
    output logic busy, done, error,
    output logic [63:0] cycles, butterflies, data_reads, data_writes, root_reads, wait_cycles
);
    typedef enum logic [3:0] {IDLE, REV_READ, REV_WRITE, BF_READ, BF_ISSUE,
        BF_WAIT, MUL_READ, MUL_ISSUE, MUL_WAIT} state_t;
    state_t state;
    (* ramstyle = "M20K, no_rw_check" *) logic [31:0] mem [0:(1<<AW)-1];
    logic [31:0] roots [0:(1<<AW)-1];
    logic [31:0] n, idx, rev_idx, half_len, block_start, offset_idx, root_step;
    logic [4:0] lg;
    logic [1:0] active_op;
    logic active_inverse;
    logic [31:0] active_scale, a_reg, b_reg, w_reg, mul_rhs, twiddle_idx;
    logic [AW-1:0] addr_a, addr_b, root_addr;
    logic en_a, en_b, we_a, we_b, root_en;
    logic [31:0] write_a, write_b;
    logic bf_valid, mul_valid;
    logic [31:0] bf0, bf1, product;

    always_comb begin
        rev_idx = 0;
        for (int b = 0; b < AW; b = b + 1)
            if (b < int'(lg)) rev_idx = (rev_idx << 1) | ((idx >> b) & 1);
    end
    genefer_ntt_butterfly32 #(.P(P), .Q(Q)) butterfly (
        .clk, .rst_n, .in_valid(state == BF_ISSUE),
        .u(a_reg), .v(b_reg), .w(w_reg), .out_valid(bf_valid), .y0(bf0), .y1(bf1)
    );
    genefer_montgomery_mul32_pipe #(.P(P), .Q(Q)) multiplier (
        .clk, .rst_n, .in_valid(state == MUL_ISSUE),
        .lhs(a_reg), .rhs(mul_rhs), .out_valid(mul_valid), .result(product)
    );

    assign read_data = a_reg;
    assign mul_rhs = active_op == 1 ? a_reg : active_op == 2 ? w_reg : active_scale;
    // Multiplex addresses BEFORE the RAM, rather than describing many logical
    // ports. Host writes take priority over reads (no read_valid on a write).
    // Internal cycles only read both ports or write both ports, to distinct
    // addresses: no mixed-port read/write collision is observed by a consumer.
    always_comb begin
        addr_a=AW'(idx); addr_b=AW'(rev_idx); root_addr=AW'(twiddle_idx);
        en_a=0; en_b=0; we_a=0; we_b=0; root_en=0;
        write_a=write_data; write_b=a_reg;
        case(state)
            IDLE: if(!start) begin
                addr_a=host_addr; en_a=load_we || read_en; we_a=load_we;
                root_addr=host_addr;
            end
            REV_READ: begin en_a=idx<rev_idx; en_b=idx<rev_idx; end
            REV_WRITE: begin en_a=1; en_b=1; we_a=1; we_b=1; write_a=b_reg; end
            BF_READ, BF_WAIT: begin
                addr_a=AW'(block_start+offset_idx);
                addr_b=AW'(block_start+offset_idx+half_len);
                en_a=state==BF_READ || bf_valid; en_b=en_a;
                we_a=state==BF_WAIT && bf_valid; we_b=we_a;
                write_a=bf0; write_b=bf1; root_en=state==BF_READ;
            end
            MUL_READ: begin en_a=1; root_addr=AW'(idx); root_en=active_op==2; end
            MUL_WAIT: begin en_a=mul_valid; we_a=mul_valid; write_a=product; end
            default: ;
        endcase
    end
    always_ff @(posedge clk) begin
        if(rst_n && en_a) begin
            if(we_a) mem[addr_a]<=write_a;
            else a_reg<=mem[addr_a];
        end
    end
    always_ff @(posedge clk) begin
        if(rst_n && en_b) begin
            if(we_b) mem[addr_b]<=write_b;
            else b_reg<=mem[addr_b];
        end
    end
    always_ff @(posedge clk) begin
        if(rst_n) begin
            if(state==IDLE && !start && root_we) roots[host_addr]<=write_data;
            if(root_en) w_reg<=roots[root_addr];
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE; busy <= 0; done <= 0; error <= 0; read_valid <= 0;
            n <= 0; lg <= 0; idx <= 0; half_len <= 0; block_start <= 0;
            offset_idx <= 0; root_step <= 0; twiddle_idx <= 0; active_op <= 0;
            active_inverse <= 0; active_scale <= 0;
            cycles <= 0; butterflies <= 0; data_reads <= 0; data_writes <= 0;
            root_reads <= 0; wait_cycles <= 0;
        end else begin
            done <= 0;
            read_valid <= state == IDLE && !start && read_en && !load_we;
            if (busy) cycles <= cycles + 1;
            case (state)
                IDLE: if (start) begin
                    error <= 0; cycles <= 0; butterflies <= 0;
                    data_reads <= 0; data_writes <= 0; root_reads <= 0; wait_cycles <= 0;
                    if (size_log2 < 1 || int'(size_log2) > AW) begin
                        error <= 1; done <= 1;
                    end else begin
                        n <= 32'd1 << size_log2; lg <= size_log2; idx <= 0;
                        half_len <= 1; block_start <= 0; offset_idx <= 0; twiddle_idx <= 0;
                        root_step <= (32'd1 << size_log2) >> 1;
                        active_op <= op; active_inverse <= inverse; active_scale <= scale;
                        busy <= 1;
                        state <= op == 0 ? REV_READ : MUL_READ;
                    end
                end
                REV_READ: begin
                    if (idx < rev_idx) begin
                        data_reads <= data_reads + 2; state <= REV_WRITE;
                    end else if (idx == n-1) state <= BF_READ;
                    else idx <= idx + 1;
                end
                REV_WRITE: begin
                    data_writes <= data_writes + 2;
                    idx <= idx + 1; state <= REV_READ;
                end
                BF_READ: begin
                    data_reads <= data_reads + 2; root_reads <= root_reads + 1;
                    state <= BF_ISSUE;
                end
                BF_ISSUE: state <= BF_WAIT;
                BF_WAIT: begin
                    wait_cycles <= wait_cycles + 1;
                    if (bf_valid) begin
                        data_writes <= data_writes + 2; butterflies <= butterflies + 1;
                        state <= BF_READ;
                        if (offset_idx + 1 < half_len) begin
                            offset_idx <= offset_idx + 1;
                            twiddle_idx <= twiddle_idx + root_step;
                        end
                        else begin
                            offset_idx <= 0; twiddle_idx <= 0;
                            if (block_start + (half_len << 1) < n)
                                block_start <= block_start + (half_len << 1);
                            else begin
                                block_start <= 0; half_len <= half_len << 1;
                                root_step <= root_step >> 1;
                                if ((half_len << 1) == n) begin
                                    if (active_inverse) begin idx <= 0; state <= MUL_READ; end
                                    else begin busy <= 0; done <= 1; state <= IDLE; end
                                end
                            end
                        end
                    end
                end
                MUL_READ: begin
                    data_reads <= data_reads + 1;
                    if (active_op == 2) root_reads <= root_reads + 1;
                    state <= MUL_ISSUE;
                end
                MUL_ISSUE: state <= MUL_WAIT;
                MUL_WAIT: begin
                    wait_cycles <= wait_cycles + 1;
                    if (mul_valid) begin
                        data_writes <= data_writes + 1;
                        if (idx == n-1) begin busy <= 0; done <= 1; state <= IDLE; end
                        else begin idx <= idx + 1; state <= MUL_READ; end
                    end
                end
                default: begin state <= IDLE; busy <= 0; error <= 1; done <= 1; end
            endcase
        end
    end
endmodule

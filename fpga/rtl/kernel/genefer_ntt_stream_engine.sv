// Pipelined radix-2 DIT engine. Public contract matches genefer_ntt_engine.
// Natural address a is stored in bank ^a, row a>>1. A butterfly changes
// exactly one address bit, so its operands always occupy opposite banks.
// Each bank performs <=1 read and <=1 write per streaming cycle. All writes
// drain before the following stage, excluding observable read/write collisions.
// Bit reversal preserves parity: use both ports of one bank for each swap.
// RAMs deliberately have no reset. Reload operands and roots after reset.
module genefer_ntt_stream_engine #(
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
    output logic [63:0] cycles, butterflies, data_reads, data_writes,
                        root_reads, wait_cycles
);
    localparam int RW = AW > 1 ? AW-1 : 1;
    localparam int DEPTH = 1 << (AW-1);
    typedef enum logic [2:0] {IDLE, REV_READ, REV_WRITE, BF_READ,
                             BF_DRAIN, MUL_READ, MUL_DRAIN} state_t;
    state_t state;
    (* ramstyle = "M20K, no_rw_check" *) logic [31:0] bank0 [0:DEPTH-1];
    (* ramstyle = "M20K, no_rw_check" *) logic [31:0] bank1 [0:DEPTH-1];
    (* ramstyle = "M20K" *) logic [31:0] roots [0:(1<<AW)-1];
    logic [RW-1:0] addr0a, addr0b, addr1a, addr1b;
    logic en0a,en0b,en1a,en1b,we0a,we0b,we1a,we1b;
    logic [31:0] w0a,w0b,w1a,w1b,q0a,q0b,q1a,q1b;
    logic root_en;
    logic [AW-1:0] root_addr;
    logic [31:0] root_q;
    logic [31:0] n, idx, rev_idx, half_len, block_start, offset_idx;
    logic [31:0] root_step, twiddle_idx, completed;
    logic [4:0] lg;
    logic [1:0] active_op;
    logic active_inverse;
    logic [31:0] active_scale;
    logic [AW-1:0] logical_a,logical_b;
    logic bank_a, bank_rev;
    logic read_bank_d,host_bank_d,bf_read_d,mul_read_d;
    logic [AW-1:0] tag_a [0:5];
    logic [AW-1:0] tag_b [0:5];
    logic bf_valid,mul_valid;
    logic [31:0] bf0,bf1,product,mul_lhs,mul_rhs;

    always_comb begin
        rev_idx=0;
        for(int b=0;b<AW;b=b+1)
            if(b<int'(lg)) rev_idx=(rev_idx<<1)|((idx>>b)&1);
    end
    assign logical_a = state==BF_READ ? AW'(block_start+offset_idx) : AW'(idx);
    assign logical_b = state==BF_READ ? AW'(block_start+offset_idx+half_len) : AW'(rev_idx);
    assign bank_a = ^logical_a;
    assign bank_rev = ^AW'(rev_idx);
    assign mul_lhs = read_bank_d ? q1a : q0a;
    assign mul_rhs = active_op==1 ? mul_lhs : active_op==2 ? root_q : active_scale;
    assign read_data = host_bank_d ? q1a : q0a;
    genefer_ntt_butterfly32 #(.P(P),.Q(Q)) butterfly (
        .clk,.rst_n,.in_valid(bf_read_d),
        .u(read_bank_d?q1a:q0a),.v(read_bank_d?q0a:q1a),.w(root_q),
        .out_valid(bf_valid),.y0(bf0),.y1(bf1)
    );
    genefer_montgomery_mul32_pipe #(.P(P),.Q(Q)) multiplier (
        .clk,.rst_n,.in_valid(mul_read_d),.lhs(mul_lhs),.rhs(mul_rhs),
        .out_valid(mul_valid),.result(product)
    );

    // Explicit true dual-port templates: port A streaming read, port B write.
    // During reversal both ports read or both write, at distinct row addresses.
    always_comb begin
        en0a=0; en0b=0; en1a=0; en1b=0;
        we0a=0; we0b=0; we1a=0; we1b=0;
        addr0a='0; addr0b='0; addr1a='0; addr1b='0;
        w0a=write_data; w0b=0; w1a=write_data; w1b=0;
        root_en=0; root_addr=AW'(twiddle_idx);
        case(state)
            IDLE: if(!start) begin
                addr0a=RW'(host_addr>>1); addr1a=RW'(host_addr>>1);
                en0a=(load_we||read_en) && !(^host_addr);
                en1a=(load_we||read_en) && (^host_addr);
                we0a=load_we; we1a=load_we;
            end
            REV_READ: if(idx<rev_idx) begin
                addr0a=RW'(idx>>1); addr0b=RW'(rev_idx>>1);
                addr1a=RW'(idx>>1); addr1b=RW'(rev_idx>>1);
                en0a=!bank_rev; en0b=!bank_rev;
                en1a=bank_rev; en1b=bank_rev;
            end
            REV_WRITE: begin
                addr0a=RW'(idx>>1); addr0b=RW'(rev_idx>>1);
                addr1a=RW'(idx>>1); addr1b=RW'(rev_idx>>1);
                en0a=!bank_rev; en0b=!bank_rev;
                en1a=bank_rev; en1b=bank_rev;
                we0a=1; we0b=1; we1a=1; we1b=1;
                w0a=q0b; w0b=q0a; w1a=q1b; w1b=q1a;
            end
            BF_READ: begin
                en0a=1; en1a=1;
                addr0a=RW'((bank_a ? logical_b : logical_a)>>1);
                addr1a=RW'((bank_a ? logical_a : logical_b)>>1);
                root_en=1;
            end
            MUL_READ: begin
                en0a=!bank_a; en1a=bank_a;
                addr0a=RW'(logical_a>>1); addr1a=RW'(logical_a>>1);
                root_en=active_op==2; root_addr=AW'(idx);
            end
            default: ;
        endcase
        if((state==BF_READ || state==BF_DRAIN) && bf_valid) begin
            en0b=1; en1b=1; we0b=1; we1b=1;
            addr0b=RW'(((^tag_a[5]) ? tag_b[5] : tag_a[5])>>1);
            addr1b=RW'(((^tag_a[5]) ? tag_a[5] : tag_b[5])>>1);
            w0b=(^tag_a[5]) ? bf1 : bf0;
            w1b=(^tag_a[5]) ? bf0 : bf1;
        end
        if((state==MUL_READ || state==MUL_DRAIN) && mul_valid) begin
            en0b=!(^tag_a[4]); en1b=^tag_a[4]; we0b=1; we1b=1;
            addr0b=RW'(tag_a[4]>>1); addr1b=RW'(tag_a[4]>>1);
            w0b=product; w1b=product;
        end
    end
    always_ff @(posedge clk) if(rst_n && en0a) begin
        if(we0a) bank0[addr0a]<=w0a; else q0a<=bank0[addr0a];
    end
    always_ff @(posedge clk) if(rst_n && en0b) begin
        if(we0b) bank0[addr0b]<=w0b; else q0b<=bank0[addr0b];
    end
    always_ff @(posedge clk) if(rst_n && en1a) begin
        if(we1a) bank1[addr1a]<=w1a; else q1a<=bank1[addr1a];
    end
    always_ff @(posedge clk) if(rst_n && en1b) begin
        if(we1b) bank1[addr1b]<=w1b; else q1b<=bank1[addr1b];
    end
    always_ff @(posedge clk) if(rst_n) begin
        if(state==IDLE && !start && root_we) roots[host_addr]<=write_data;
        if(root_en) root_q<=roots[root_addr];
    end

    // Simulation checks deliberately reject any ambiguous RAM collision;
    // no_rw_check is safe only because scheduling makes these impossible.
    // synthesis translate_off
    always @(posedge clk) if(rst_n) begin
        if(en0a && en0b && addr0a==addr0b && (we0a||we0b))
            $fatal(1,"bank0 mixed-port collision");
        if(en1a && en1b && addr1a==addr1b && (we1a||we1b))
            $fatal(1,"bank1 mixed-port collision");
        if(state==BF_READ && ((^logical_a)==(^logical_b)))
            $fatal(1,"butterfly bank conflict");
        if(state==REV_READ && idx<rev_idx && ((^AW'(idx))!=bank_rev))
            $fatal(1,"bit reversal bank mismatch");
    end
    // synthesis translate_on

    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE; busy<=0; done<=0; error<=0; read_valid<=0;
            n<=0; lg<=0; idx<=0; half_len<=0; block_start<=0; offset_idx<=0;
            root_step<=0; twiddle_idx<=0; completed<=0;
            active_op<=0; active_inverse<=0; active_scale<=0;
            read_bank_d<=0; host_bank_d<=0; bf_read_d<=0; mul_read_d<=0;
            cycles<=0; butterflies<=0; data_reads<=0; data_writes<=0;
            root_reads<=0; wait_cycles<=0;
            for(int k=0;k<6;k=k+1) begin tag_a[k]<=0; tag_b[k]<=0; end
        end else begin
            done<=0;
            read_valid<=state==IDLE && !start && read_en && !load_we;
            if(state==IDLE) host_bank_d<=^host_addr;
            bf_read_d<=state==BF_READ;
            mul_read_d<=state==MUL_READ;
            read_bank_d<=bank_a;
            tag_a[0]<=logical_a; tag_b[0]<=logical_b;
            for(int k=1;k<6;k=k+1) begin tag_a[k]<=tag_a[k-1]; tag_b[k]<=tag_b[k-1]; end
            if(busy) cycles<=cycles+1;
            if(state==BF_READ) begin data_reads<=data_reads+2; root_reads<=root_reads+1; end
            if(state==MUL_READ) begin
                data_reads<=data_reads+1;
                if(active_op==2) root_reads<=root_reads+1;
            end
            if(state==BF_DRAIN || state==MUL_DRAIN) wait_cycles<=wait_cycles+1;
            if((state==BF_READ || state==BF_DRAIN) && bf_valid) begin
                butterflies<=butterflies+1; data_writes<=data_writes+2;
                completed<=completed+1;
                if(completed==(n>>1)-1) begin
                    completed<=0; block_start<=0; offset_idx<=0; twiddle_idx<=0;
                    half_len<=half_len<<1; root_step<=root_step>>1;
                    if((half_len<<1)==n) begin
                        if(active_inverse) begin idx<=0; state<=MUL_READ; end
                        else begin busy<=0; done<=1; state<=IDLE; end
                    end else state<=BF_READ;
                end
            end
            if((state==MUL_READ || state==MUL_DRAIN) && mul_valid) begin
                data_writes<=data_writes+1; completed<=completed+1;
                if(completed==n-1) begin busy<=0; done<=1; state<=IDLE; end
            end
            case(state)
                IDLE: if(start) begin
                    error<=0; cycles<=0; butterflies<=0; data_reads<=0;
                    data_writes<=0; root_reads<=0; wait_cycles<=0;
                    if(size_log2<1 || int'(size_log2)>AW) begin error<=1; done<=1; end
                    else begin
                        n<=32'd1<<size_log2; lg<=size_log2; idx<=0; completed<=0;
                        half_len<=1; block_start<=0; offset_idx<=0; twiddle_idx<=0;
                        root_step<=(32'd1<<size_log2)>>1;
                        active_op<=op; active_inverse<=inverse; active_scale<=scale;
                        busy<=1; state<=op==0 ? REV_READ : MUL_READ;
                    end
                end
                REV_READ: begin
                    if(idx<rev_idx) begin data_reads<=data_reads+2; state<=REV_WRITE; end
                    else if(idx==n-1) state<=BF_READ;
                    else idx<=idx+1;
                end
                REV_WRITE: begin data_writes<=data_writes+2; idx<=idx+1; state<=REV_READ; end
                BF_READ: begin
                    if(offset_idx+1<half_len) begin
                        offset_idx<=offset_idx+1; twiddle_idx<=twiddle_idx+root_step;
                    end else begin
                        offset_idx<=0; twiddle_idx<=0;
                        if(block_start+(half_len<<1)<n) block_start<=block_start+(half_len<<1);
                        else state<=BF_DRAIN;
                    end
                end
                MUL_READ: begin
                    if(idx==n-1) state<=MUL_DRAIN;
                    else idx<=idx+1;
                end
                default: ;
            endcase
        end
    end
endmodule

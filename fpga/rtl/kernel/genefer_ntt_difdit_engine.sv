// No-bit-reversal NTT candidate; banked RAM and vector ports match stream engine.
// op0 dif=1: natural input -> bit-reversed spectrum (radix-2 DIF).
// op0 dif=0: bit-reversed input -> natural output (radix-2 DIT).
// Twiddle direction is selected by the caller's root table, not by dif.
// inverse=1 adds the caller's normalization scale; inverse=0 is unnormalized.
// op1/2/3 retain elementwise operations in the current physical ordering.
// A DIF forward + square + DIT inverse needs no explicit bit reversal.
// Six-stage shared butterfly; RAM read-to-write distance is seven cycles.
module genefer_ntt_difdit_engine #(
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
    input logic start, inverse, dif,
    input logic [1:0] op,
    input logic [4:0] size_log2,
    input logic [31:0] scale,
    output logic busy, done, error,
    output logic [63:0] cycles, butterflies, data_reads, data_writes,
                        root_reads, wait_cycles
);
    localparam int RW = AW > 1 ? AW-1 : 1;
    localparam int DEPTH = 1 << (AW-1);
    typedef enum logic [2:0] {IDLE, BF_READ,
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
    logic [31:0] n, idx, half_len, block_start, offset_idx;
    logic [31:0] root_step, twiddle_idx, completed;
    logic [4:0] lg;
    logic [1:0] active_op;
    logic active_inverse, active_dif;
    logic [31:0] active_scale;
    logic [AW-1:0] logical_a,logical_b;
    logic bank_a;
    logic read_bank_d,host_bank_d,bf_read_d,mul_read_d;
    logic [AW-1:0] tag_a [0:6];
    logic [AW-1:0] tag_b [0:6];
    logic bf_valid,mul_valid;
    logic [31:0] bf0,bf1,product,mul_lhs,mul_rhs;

    assign logical_a = state==BF_READ ? AW'(block_start+offset_idx) : AW'(idx);
    assign logical_b = AW'(block_start+offset_idx+half_len);
    assign bank_a = ^logical_a;
    assign mul_lhs = read_bank_d ? q1a : q0a;
    assign mul_rhs = active_op==1 ? mul_lhs : active_op==2 ? root_q : active_scale;
    assign read_data = host_bank_d ? q1a : q0a;
    genefer_ntt_difdit_butterfly32 #(.P(P),.Q(Q)) butterfly (
        .clk,.rst_n,.in_valid(bf_read_d),.dif(active_dif),
        .u(read_bank_d?q1a:q0a),.v(read_bank_d?q0a:q1a),.w(root_q),
        .out_valid(bf_valid),.y0(bf0),.y1(bf1)
    );
    genefer_montgomery_mul32_pipe #(.P(P),.Q(Q)) multiplier (
        .clk,.rst_n,.in_valid(mul_read_d),.lhs(mul_lhs),.rhs(mul_rhs),
        .out_valid(mul_valid),.result(product)
    );

    // Explicit two-port templates: port A host/read, port B streaming write.
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
            addr0b=RW'(((^tag_a[6]) ? tag_b[6] : tag_a[6])>>1);
            addr1b=RW'(((^tag_a[6]) ? tag_a[6] : tag_b[6])>>1);
            w0b=(^tag_a[6]) ? bf1 : bf0;
            w1b=(^tag_a[6]) ? bf0 : bf1;
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
    end
    // synthesis translate_on

    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE; busy<=0; done<=0; error<=0; read_valid<=0;
            n<=0; lg<=0; idx<=0; half_len<=0; block_start<=0; offset_idx<=0;
            root_step<=0; twiddle_idx<=0; completed<=0;
            active_op<=0; active_inverse<=0; active_dif<=0; active_scale<=0;
            read_bank_d<=0; host_bank_d<=0; bf_read_d<=0; mul_read_d<=0;
            cycles<=0; butterflies<=0; data_reads<=0; data_writes<=0;
            root_reads<=0; wait_cycles<=0;
            for(int k=0;k<7;k=k+1) begin tag_a[k]<=0; tag_b[k]<=0; end
        end else begin
            done<=0;
            read_valid<=state==IDLE && !start && read_en && !load_we;
            if(state==IDLE) host_bank_d<=^host_addr;
            bf_read_d<=state==BF_READ;
            mul_read_d<=state==MUL_READ;
            read_bank_d<=bank_a;
            tag_a[0]<=logical_a; tag_b[0]<=logical_b;
            for(int k=1;k<7;k=k+1) begin tag_a[k]<=tag_a[k-1]; tag_b[k]<=tag_b[k-1]; end
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
                    half_len<=active_dif ? half_len>>1 : half_len<<1;
                    root_step<=active_dif ? root_step<<1 : root_step>>1;
                    if((active_dif && half_len==1) || (!active_dif && (half_len<<1)==n)) begin
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
                        half_len<=dif ? (32'd1<<size_log2)>>1 : 1;
                        block_start<=0; offset_idx<=0; twiddle_idx<=0;
                        root_step<=dif ? 1 : (32'd1<<size_log2)>>1;
                        active_op<=op; active_inverse<=inverse; active_dif<=dif; active_scale<=scale;
                        busy<=1; state<=op==0 ? BF_READ : MUL_READ;
                    end
                end
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

// One shared Montgomery multiplier for both orders. Registered pre-add/subtract
// avoids placing an extra carry chain on the multiplier input path.
// Six register stages: input edge k -> output immediately after edge k+5.
// Both outputs hold while invalid; reset cancels all transactions.
module genefer_ntt_difdit_butterfly32 #(
    parameter logic [31:0] P=32'd2130706433,
    parameter logic [31:0] Q=32'd2164260865
) (
    input logic clk,rst_n,in_valid,dif,
    input logic [31:0] u,v,w,
    output logic out_valid,
    output logic [31:0] y0,y1
);
    logic pre_valid,product_valid;
    logic [31:0] pre_v,pre_w,product;
    logic [31:0] prefix_pipe [0:4];
    logic [4:0] dif_pipe;
    logic [32:0] pre_sum,post_sum;
    logic [31:0] pre_sum_reduced,post_sum_reduced;
    assign pre_sum={1'b0,u}+{1'b0,v};
    assign pre_sum_reduced=pre_sum>={1'b0,P} ? 32'(pre_sum-{1'b0,P}) : pre_sum[31:0];
    assign post_sum={1'b0,prefix_pipe[4]}+{1'b0,product};
    assign post_sum_reduced=post_sum>={1'b0,P} ? 32'(post_sum-{1'b0,P}) : post_sum[31:0];
    genefer_montgomery_mul32_pipe #(.P(P),.Q(Q)) multiplier (
        .clk,.rst_n,.in_valid(pre_valid),.lhs(pre_v),.rhs(pre_w),
        .out_valid(product_valid),.result(product)
    );
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            pre_valid<=0;pre_v<=0;pre_w<=0;dif_pipe<=0;
            out_valid<=0;y0<=0;y1<=0;
            for(int k=0;k<5;k=k+1) prefix_pipe[k]<=0;
        end else begin
            pre_valid<=in_valid;
            if(in_valid) begin
                pre_v<=dif ? (u>=v ? u-v : u+P-v) : v;
                pre_w<=w;
            end
            prefix_pipe[0]<=dif ? pre_sum_reduced : u;
            for(int k=1;k<5;k=k+1) prefix_pipe[k]<=prefix_pipe[k-1];
            dif_pipe<={dif_pipe[3:0],dif};
            out_valid<=product_valid;
            if(product_valid) begin
                y0<=dif_pipe[4] ? prefix_pipe[4] : post_sum_reduced;
                y1<=dif_pipe[4] ? product :
                    (prefix_pipe[4]>=product ? prefix_pipe[4]-product : prefix_pipe[4]+P-product);
            end
        end
    end
endmodule

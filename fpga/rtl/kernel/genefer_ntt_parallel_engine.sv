// Banked multi-lane DIF/DIT prototype. Same scalar host/order contract as
// genefer_ntt_difdit_engine; LANES is 1,2,4 or8. No full-array replication.
// K=2*LANES banks; bank address is XOR of KW-bit address chunks, row=a>>KW.
// For stage s, vary low KW bits except s%KW, plus bit s: one address/bank.
// root_reads counts physical root-bank reads, including duplicate broadcasts.
module genefer_ntt_parallel_engine #(
    parameter int AW=16,
    parameter int LANES=4,
    parameter logic [31:0] P=32'd2130706433,
    parameter logic [31:0] Q=32'd2164260865
) (
    input logic clk,rst_n,
    input logic load_we,root_we,read_en,
    input logic [AW-1:0] host_addr,
    input logic [31:0] write_data,
    output logic read_valid,
    output logic [31:0] read_data,
    input logic start,inverse,dif,
    input logic [1:0] op,
    input logic [4:0] size_log2,
    input logic [31:0] scale,
    output logic busy,done,error,
    output logic [63:0] cycles,butterflies,data_reads,data_writes,root_reads,wait_cycles
);
    localparam int LW=$clog2(LANES);
    localparam int KW=LW+1;
    localparam int BANKS=2*LANES;
    localparam int RW=AW>KW ? AW-KW : 1;
    localparam int DEPTH=1 << (AW>KW ? AW-KW : 0);
    typedef enum logic [2:0] {IDLE,BF_READ,BF_DRAIN,MUL_READ,MUL_DRAIN} state_t;
    state_t state;
    logic [31:0] n,group_index,completed,base_addr;
    logic [4:0] lg,stage_bit;
    logic [1:0] active_op;
    logic active_inverse,active_dif;
    logic [31:0] active_scale;
    logic [31:0] bf_lanes,mul_lanes,root_read_count;
    logic [KW-1:0] host_bank,host_bank_d;
    logic [RW-1:0] host_row;
    logic [BANKS-1:0] data_re,data_we,root_re;
    logic [RW-1:0] data_ra [0:BANKS-1];
    logic [RW-1:0] data_wa [0:BANKS-1];
    logic [RW-1:0] root_ra [0:BANKS-1];
    logic [31:0] data_w [0:BANKS-1],data_q [0:BANKS-1],root_q [0:BANKS-1];
    logic [AW-1:0] address_u [0:LANES-1],address_v [0:LANES-1],address_w [0:LANES-1];
    logic [KW-1:0] bank_u [0:LANES-1],bank_v [0:LANES-1],bank_w [0:LANES-1];
    logic [KW-1:0] bank_u_d [0:LANES-1],bank_v_d [0:LANES-1],bank_w_d [0:LANES-1];
    logic [AW-1:0] tag_u [0:6][0:LANES-1],tag_v [0:6][0:LANES-1];
    logic [LANES-1:0] bf_in_valid,mul_in_valid,bf_valid,mul_valid;
    logic [31:0] bf0 [0:LANES-1],bf1 [0:LANES-1],product [0:LANES-1];
    logic [31:0] mul_rhs [0:LANES-1];

    function automatic logic [KW-1:0] bank_of(input logic [AW-1:0] a);
        logic [KW-1:0] b;
        begin
            b=0;
            for(int j=0;j<AW;j=j+1) b[j%KW]=b[j%KW]^a[j];
            bank_of=b;
        end
    endfunction
    assign host_bank=bank_of(host_addr);
    assign host_row=RW'(host_addr>>KW);
    assign read_data=data_q[host_bank_d];
    assign bf_lanes=(n>>1)<LANES ? n>>1 : LANES;
    assign mul_lanes=n<LANES ? n : LANES;

    // Enumerate the fixed address bits from group_index. Remaining selected
    // bits are inserted by the lane index; stage_bit itself is zero for u.
    always_comb begin : addresses
        integer fixed_bit,lane_bit;
        logic [31:0] a;
        base_addr=0;fixed_bit=0;
        for(int j=0;j<AW;j=j+1) begin
            if(j<int'(lg) && j!=int'(stage_bit) &&
               !(j<KW && j!=(int'(stage_bit)%KW))) begin
                base_addr[j]=group_index[fixed_bit];fixed_bit=fixed_bit+1;
            end
        end
        for(int lane=0;lane<LANES;lane=lane+1) begin
            a=base_addr;lane_bit=0;
            for(int j=0;j<KW;j=j+1) begin
                if(j<int'(lg) && j!=(int'(stage_bit)%KW)) begin
                    a[j]=((32'(lane)>>lane_bit)&32'd1)!=0;lane_bit=lane_bit+1;
                end
            end
            if(state==MUL_READ) a=(group_index<<LW)+32'(lane);
            address_u[lane]=AW'(a);
            address_v[lane]=AW'(a^(32'd1<<stage_bit));
            address_w[lane]=state==MUL_READ ? AW'(a) :
                AW'((a&((32'd1<<stage_bit)-1))<<(lg-1-stage_bit));
            bank_u[lane]=bank_of(address_u[lane]);
            bank_v[lane]=bank_of(address_v[lane]);
            bank_w[lane]=bank_of(address_w[lane]);
        end
    end

    for(genvar lane=0;lane<LANES;lane=lane+1) begin : arithmetic
        genefer_ntt_difdit_butterfly32 #(.P(P),.Q(Q)) butterfly (
            .clk,.rst_n,.in_valid(bf_in_valid[lane]),.dif(active_dif),
            .u(data_q[bank_u_d[lane]]),.v(data_q[bank_v_d[lane]]),.w(root_q[bank_w_d[lane]]),
            .out_valid(bf_valid[lane]),.y0(bf0[lane]),.y1(bf1[lane])
        );
        assign mul_rhs[lane]=active_op==1 ? data_q[bank_u_d[lane]] :
                                   active_op==2 ? root_q[bank_w_d[lane]] : active_scale;
        genefer_montgomery_mul32_pipe #(.P(P),.Q(Q)) multiplier (
            .clk,.rst_n,.in_valid(mul_in_valid[lane]),.lhs(data_q[bank_u_d[lane]]),
            .rhs(mul_rhs[lane]),.out_valid(mul_valid[lane]),.result(product[lane])
        );
    end

    always_comb begin : memory_ports
        logic [KW-1:0] b;
        data_re=0;data_we=0;root_re=0;
        b=0;
        for(int bank=0;bank<BANKS;bank=bank+1) begin
            data_ra[bank]=0;data_wa[bank]=0;root_ra[bank]=0;data_w[bank]=0;
        end
        if(state==IDLE && !start) begin
            if(load_we) begin data_we[host_bank]=1;data_wa[host_bank]=host_row;data_w[host_bank]=write_data;end
            else if(read_en) begin data_re[host_bank]=1;data_ra[host_bank]=host_row;end
        end
        for(int lane=0;lane<LANES;lane=lane+1) begin
            if(state==BF_READ && 32'(lane)<bf_lanes) begin
                b=bank_u[lane];
                // synthesis translate_off
                if(data_re[b]) $fatal(1,"parallel data-read bank conflict u");
                // synthesis translate_on
                data_re[b]=1;data_ra[b]=RW'(address_u[lane]>>KW);
                b=bank_v[lane];
                // synthesis translate_off
                if(data_re[b]) $fatal(1,"parallel data-read bank conflict v");
                // synthesis translate_on
                data_re[b]=1;data_ra[b]=RW'(address_v[lane]>>KW);
                b=bank_w[lane];
                // synthesis translate_off
                if(root_re[b] && root_ra[b]!=RW'(address_w[lane]>>KW))
                    $fatal(1,"parallel root-read bank conflict");
                // synthesis translate_on
                root_re[b]=1;root_ra[b]=RW'(address_w[lane]>>KW);
            end
            if(state==MUL_READ && 32'(lane)<mul_lanes) begin
                b=bank_u[lane];
                // synthesis translate_off
                if(data_re[b]) $fatal(1,"parallel vector-read bank conflict");
                // synthesis translate_on
                data_re[b]=1;data_ra[b]=RW'(address_u[lane]>>KW);
                if(active_op==2) begin
                    b=bank_w[lane];root_re[b]=1;root_ra[b]=RW'(address_w[lane]>>KW);
                end
            end
            if((state==BF_READ || state==BF_DRAIN) && bf_valid[lane]) begin
                b=bank_of(tag_u[6][lane]);
                // synthesis translate_off
                if(data_we[b]) $fatal(1,"parallel data-write bank conflict u");
                // synthesis translate_on
                data_we[b]=1;data_wa[b]=RW'(tag_u[6][lane]>>KW);data_w[b]=bf0[lane];
                b=bank_of(tag_v[6][lane]);
                // synthesis translate_off
                if(data_we[b]) $fatal(1,"parallel data-write bank conflict v");
                // synthesis translate_on
                data_we[b]=1;data_wa[b]=RW'(tag_v[6][lane]>>KW);data_w[b]=bf1[lane];
            end
            if((state==MUL_READ || state==MUL_DRAIN) && mul_valid[lane]) begin
                b=bank_of(tag_u[4][lane]);
                // synthesis translate_off
                if(data_we[b]) $fatal(1,"parallel vector-write bank conflict");
                // synthesis translate_on
                data_we[b]=1;data_wa[b]=RW'(tag_u[4][lane]>>KW);data_w[b]=product[lane];
            end
        end
        root_read_count=0;
        for(int bank=0;bank<BANKS;bank=bank+1) root_read_count=root_read_count+32'(root_re[bank]);
    end
    for(genvar bank=0;bank<BANKS;bank=bank+1) begin : memories
        (* ramstyle="M20K, no_rw_check" *) logic [31:0] data_mem [0:DEPTH-1];
        (* ramstyle="M20K" *) logic [31:0] root_mem [0:DEPTH-1];
        always_ff @(posedge clk) if(rst_n) begin
            if(data_re[bank]) data_q[bank]<=data_mem[data_ra[bank]];
            if(data_we[bank]) data_mem[data_wa[bank]]<=data_w[bank];
            if(root_re[bank]) root_q[bank]<=root_mem[root_ra[bank]];
            if(state==IDLE && !start && root_we && host_bank==KW'(bank)) root_mem[host_row]<=write_data;
        end
        // synthesis translate_off
        always @(posedge clk) if(rst_n && data_re[bank] && data_we[bank] && data_ra[bank]==data_wa[bank])
            $fatal(1,"parallel mixed-port RAM collision");
        // synthesis translate_on
    end
    // synthesis translate_off
    initial begin
        if(LANES!=1 && LANES!=2 && LANES!=4 && LANES!=8) $fatal(1,"unsupported LANES");
        if(AW<1 || AW>16) $fatal(1,"unsupported AW");
    end
    // synthesis translate_on

    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE;busy<=0;done<=0;error<=0;read_valid<=0;
            n<=0;group_index<=0;completed<=0;lg<=0;stage_bit<=0;
            active_op<=0;active_inverse<=0;active_dif<=0;active_scale<=0;host_bank_d<=0;
            bf_in_valid<=0;mul_in_valid<=0;
            cycles<=0;butterflies<=0;data_reads<=0;data_writes<=0;root_reads<=0;wait_cycles<=0;
            for(int lane=0;lane<LANES;lane=lane+1) begin
                bank_u_d[lane]<=0;bank_v_d[lane]<=0;bank_w_d[lane]<=0;
                for(int t=0;t<7;t=t+1) begin tag_u[t][lane]<=0;tag_v[t][lane]<=0;end
            end
        end else begin
            done<=0;
            read_valid<=state==IDLE && !start && read_en && !load_we;
            if(state==IDLE) host_bank_d<=host_bank;
            for(int lane=0;lane<LANES;lane=lane+1) begin
                bf_in_valid[lane]<=state==BF_READ && 32'(lane)<bf_lanes;
                mul_in_valid[lane]<=state==MUL_READ && 32'(lane)<mul_lanes;
                bank_u_d[lane]<=bank_u[lane];bank_v_d[lane]<=bank_v[lane];bank_w_d[lane]<=bank_w[lane];
                tag_u[0][lane]<=address_u[lane];tag_v[0][lane]<=address_v[lane];
                for(int t=1;t<7;t=t+1) begin tag_u[t][lane]<=tag_u[t-1][lane];tag_v[t][lane]<=tag_v[t-1][lane];end
            end
            if(busy) cycles<=cycles+1;
            if(state==BF_READ) begin data_reads<=data_reads+64'(2*bf_lanes);root_reads<=root_reads+64'(root_read_count);end
            if(state==MUL_READ) begin data_reads<=data_reads+64'(mul_lanes);root_reads<=root_reads+64'(root_read_count);end
            if(state==BF_DRAIN || state==MUL_DRAIN) wait_cycles<=wait_cycles+1;
            if((state==BF_READ || state==BF_DRAIN) && bf_valid[0]) begin
                butterflies<=butterflies+64'(bf_lanes);data_writes<=data_writes+64'(2*bf_lanes);
                completed<=completed+bf_lanes;
                if(completed+bf_lanes==(n>>1)) begin
                    completed<=0;group_index<=0;
                    if((active_dif && stage_bit==0) || (!active_dif && stage_bit==lg-1)) begin
                        if(active_inverse) state<=MUL_READ;
                        else begin busy<=0;done<=1;state<=IDLE;end
                    end else begin stage_bit<=active_dif ? stage_bit-1 : stage_bit+1;state<=BF_READ;end
                end
            end
            if((state==MUL_READ || state==MUL_DRAIN) && mul_valid[0]) begin
                data_writes<=data_writes+64'(mul_lanes);completed<=completed+mul_lanes;
                if(completed+mul_lanes==n) begin busy<=0;done<=1;state<=IDLE;end
            end
            case(state)
                IDLE: if(start) begin
                    error<=0;cycles<=0;butterflies<=0;data_reads<=0;data_writes<=0;root_reads<=0;wait_cycles<=0;
                    if(size_log2<1 || int'(size_log2)>AW) begin error<=1;done<=1;end
                    else begin
                        n<=32'd1<<size_log2;lg<=size_log2;group_index<=0;completed<=0;
                        active_op<=op;active_inverse<=inverse;active_dif<=dif;active_scale<=scale;
                        stage_bit<=dif ? size_log2-1 : 0;busy<=1;
                        state<=op==0 ? BF_READ : MUL_READ;
                    end
                end
                BF_READ: if(((group_index+1)<<KW)>=n) state<=BF_DRAIN; else group_index<=group_index+1;
                MUL_READ: if(((group_index+1)<<LW)>=n) state<=MUL_DRAIN; else group_index<=group_index+1;
                default: ;
            endcase
        end
    end
endmodule

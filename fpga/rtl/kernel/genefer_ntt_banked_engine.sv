// Bank-centric cached DIF/DIT prototype. Frozen parallel/cache engines unchanged.
// Each butterfly lane owns a physical bank pair chosen from KW wiring patterns.
// Root distribution uses structured XOR/rotation/broadcast networks, not one
// BANKS-input mux per arithmetic lane. Pointwise routing uses two bank halves.
module genefer_ntt_banked_engine #(
    parameter int AW=16,
    parameter int LANES=4,
    parameter logic [31:0] P=32'd2130706433,
    parameter logic [31:0] Q=32'd2164260865
) (
    input logic clk,rst_n,load_we,root_we,read_en,
    input logic [AW-1:0] host_addr,
    input logic [31:0] write_data,
    output logic read_valid,
    output logic [31:0] read_data,
    input logic start,inverse,dif,
    input logic [1:0] root_phase,op,
    input logic [4:0] size_log2,
    input logic [31:0] scale,
    output logic busy,done,error,
    output logic [63:0] cycles,butterflies,data_reads,data_writes,root_reads,wait_cycles
);
    localparam int LW=$clog2(LANES),KW=LW+1,BANKS=2*LANES;
    localparam int PW=KW>1 ? $clog2(KW) : 1;
    localparam int RW=AW>KW ? AW-KW : 1;
    localparam int DEPTH=1 << (AW>KW ? AW-KW : 0);
    localparam int HALF_DEPTH=1 << (AW>KW+1 ? AW-KW-1 : 0);
    localparam int ROOT_DEPTH=2*DEPTH+2*HALF_DEPTH,RRW=$clog2(ROOT_DEPTH);
    typedef enum logic [2:0] {IDLE,BF_READ,BF_DRAIN,MUL_READ,MUL_DRAIN} state_t;
    state_t state;
    logic [31:0] n,group_index,completed,base_addr,point_base,root_base;
    logic [4:0] lg,stage_bit,root_shift,stage_bit_d;
    logic [PW-1:0] pairing,rotation,pairing_d,rotation_d;
    logic [KW-1:0] base_bank,root_base_bank,root_mask,base_bank_d,root_base_bank_d;
    logic orientation,orientation_d,point_half,point_half_d,low_stage_d;
    logic [6:0] orientation_pipe,point_half_pipe;
    logic [1:0] active_op;
    logic active_inverse,active_dif;
    logic [31:0] active_scale,bf_lanes,mul_lanes,root_read_count;
    logic [RRW-1:0] active_root_base,host_root_base;
    logic [KW-1:0] host_bank,host_bank_d;
    logic [RW-1:0] host_row;
    logic half_write_illegal;
    logic [BANKS-1:0] data_re,data_we,root_re;
    logic [RW-1:0] data_ra [0:BANKS-1],data_wa [0:BANKS-1];
    logic [RRW-1:0] root_ra [0:BANKS-1];
    logic [31:0] data_w [0:BANKS-1],data_q [0:BANKS-1],root_q [0:BANKS-1];
    logic [RW-1:0] row_tag [0:6][0:BANKS-1];
    logic [LANES-1:0] bf_in_valid,mul_in_valid,bf_valid,mul_valid;
    logic [31:0] bf0 [0:LANES-1],bf1 [0:LANES-1],product [0:LANES-1];
    logic [31:0] root_rotate_option [0:BANKS-1][0:KW-1];
    logic [31:0] root_rotated [0:BANKS-1];
    logic [31:0] root_clip_option [0:BANKS-1][0:KW-1];
    logic [31:0] root_clip [0:BANKS-1];

    function automatic logic [KW-1:0] bank_of(input logic [AW-1:0] a);
        logic [KW-1:0] b;
        begin b=0;for(int j=0;j<AW;j=j+1) b[j%KW]=b[j%KW]^a[j];bank_of=b;end
    endfunction
    function automatic logic [KW-1:0] ror(input logic [KW-1:0] b,input logic [PW-1:0] r);
        ror=(b>>r)|(b<<(KW-int'(r)));
    endfunction
    function automatic int insert_zero(input int a,p);
        insert_zero=(a&((1<<p)-1))|((a>>p)<<(p+1));
    endfunction
    function automatic int remove_bit(input int a,p);
        remove_bit=(a&((1<<p)-1))|((a>>(p+1))<<p);
    endfunction
    function automatic logic [RRW-1:0] phase_base(input logic [1:0] phase_id);
        case(phase_id)
            0: phase_base=0;
            1: phase_base=RRW'(DEPTH);
            2: phase_base=RRW'(DEPTH+HALF_DEPTH);
            default: phase_base=RRW'(DEPTH+2*HALF_DEPTH);
        endcase
    endfunction
    assign host_bank=bank_of(host_addr);
    assign host_row=RW'(host_addr>>KW);
    assign host_root_base=phase_base(root_phase);
    assign half_write_illegal=(root_phase==1 || root_phase==2) && host_addr[AW-1];
    assign read_data=data_q[host_bank_d];
    assign bf_lanes=(n>>1)<LANES ? n>>1 : LANES;
    assign mul_lanes=n<LANES ? n : LANES;
    assign pairing=PW'(int'(stage_bit)%KW);
    assign root_shift=lg-1-stage_bit;
    assign rotation=PW'(int'(root_shift)%KW);
    assign base_bank=bank_of(AW'(base_addr));
    assign orientation=base_bank[pairing];
    assign point_base=group_index<<LW;
    assign point_half=(bank_of(AW'(point_base))&KW'(1<<LW))!=0;
    assign root_base=(base_addr&((32'd1<<stage_bit)-1))<<root_shift;
    assign root_base_bank=bank_of(AW'(root_base));
    assign root_mask=int'(stage_bit)<KW ? KW'((32'd1<<stage_bit)-1) : ~(KW'(1)<<pairing);
    always_comb begin : fixed_address_bits
        integer fixed_bit;
        base_addr=0;fixed_bit=0;
        for(int j=0;j<AW;j=j+1) begin
            if(j<int'(lg) && j!=int'(stage_bit) && !(j<KW && j!=int'(pairing))) begin
                base_addr[j]=group_index[fixed_bit];fixed_bit=fixed_bit+1;
            end
        end
    end

    // Root q -> XOR fixed root contribution -> rotate index bits -> early-stage
    // broadcast -> XOR fixed data-bank contribution. Every XOR dimension is a
    // layer of two-input muxes; rotation/broadcast select among KW fixed wires.
    for(genvar d=0;d<=KW;d=d+1) begin : root_xor_stages
        logic [31:0] words [0:BANKS-1];
        for(genvar b=0;b<BANKS;b=b+1) begin : banks
            if(d==0) assign words[b]=root_q[b];
            else assign words[b]=root_base_bank_d[d-1] ? root_xor_stages[d-1].words[b^(1<<(d-1))] : root_xor_stages[d-1].words[b];
        end
    end
    for(genvar d=0;d<=KW;d=d+1) begin : root_lane_xor_stages
        logic [31:0] words [0:BANKS-1];
        for(genvar b=0;b<BANKS;b=b+1) begin : banks
            if(d==0) assign words[b]=root_clip[b];
            else assign words[b]=base_bank_d[d-1] ? root_lane_xor_stages[d-1].words[b^(1<<(d-1))] : root_lane_xor_stages[d-1].words[b];
        end
    end
    for(genvar b=0;b<BANKS;b=b+1) begin : root_route
        for(genvar d=0;d<KW;d=d+1) begin : dimensions
            localparam int ROT=((b<<d)|(b>>(KW-d)))&(BANKS-1);
            assign root_rotate_option[b][d]=root_xor_stages[KW].words[ROT];
            assign root_clip_option[b][d]=root_rotated[b&((1<<d)-1)];
        end
        assign root_rotated[b]=root_rotate_option[b][rotation_d];
        assign root_clip[b]=low_stage_d ? root_clip_option[b][PW'(stage_bit_d)] : root_rotated[b];
    end
    for(genvar lane=0;lane<LANES;lane=lane+1) begin : arithmetic
        logic [31:0] data_lo [0:KW-1],data_hi [0:KW-1],root_lo [0:KW-1],root_hi [0:KW-1];
        logic [31:0] u,v,w,mul_lhs,mul_rhs;
        for(genvar p=0;p<KW;p=p+1) begin : pair_patterns
            localparam int LO=insert_zero(lane,p),HI=LO|(1<<p);
            assign data_lo[p]=data_q[LO];assign data_hi[p]=data_q[HI];
            assign root_lo[p]=root_lane_xor_stages[KW].words[LO];assign root_hi[p]=root_lane_xor_stages[KW].words[HI];
        end
        assign u=orientation_d ? data_hi[pairing_d] : data_lo[pairing_d];
        assign v=orientation_d ? data_lo[pairing_d] : data_hi[pairing_d];
        assign w=orientation_d ? root_hi[pairing_d] : root_lo[pairing_d];
        genefer_ntt_difdit_butterfly32 #(.P(P),.Q(Q)) butterfly (
            .clk,.rst_n,.in_valid(bf_in_valid[lane]),.dif(active_dif),.u,.v,.w,
            .out_valid(bf_valid[lane]),.y0(bf0[lane]),.y1(bf1[lane])
        );
        assign mul_lhs=point_half_d ? data_q[lane+LANES] : data_q[lane];
        assign mul_rhs=active_op==1 ? mul_lhs : active_op==2 ?
            (point_half_d ? root_q[lane+LANES] : root_q[lane]) : active_scale;
        genefer_montgomery_mul32_pipe #(.P(P),.Q(Q)) multiplier (
            .clk,.rst_n,.in_valid(mul_in_valid[lane]),.lhs(mul_lhs),.rhs(mul_rhs),
            .out_valid(mul_valid[lane]),.result(product[lane])
        );
    end

    for(genvar bank=0;bank<BANKS;bank=bank+1) begin : memories
        (* ramstyle="M20K, no_rw_check" *) logic [31:0] data_mem [0:DEPTH-1];
        (* ramstyle="M20K" *) logic [31:0] root_mem [0:ROOT_DEPTH-1];
        logic [31:0] bf_write_option [0:KW-1];
        logic [KW-1:0] bf_valid_option,root_variable;
        logic [31:0] bf_address,root_address;
        for(genvar p=0;p<KW;p=p+1) begin : write_patterns
            localparam int LANE=remove_bit(bank,p);
            assign bf_write_option[p]=(orientation_pipe[6]==1'((bank>>p)&1)) ? bf0[LANE] : bf1[LANE];
            assign bf_valid_option[p]=bf_valid[LANE];
        end
        assign bf_address=base_addr|((((32'(bank)>>pairing)&1)^32'(orientation))<<stage_bit);
        assign root_variable=ror(KW'(bank)^root_base_bank,rotation);
        assign root_address=root_base|(32'(root_variable)<<root_shift);
        always_comb begin
            data_re[bank]=0;data_we[bank]=0;root_re[bank]=0;
            data_ra[bank]=0;data_wa[bank]=0;root_ra[bank]=0;data_w[bank]=0;
            if(state==IDLE && !start && host_bank==KW'(bank)) begin
                if(load_we) begin data_we[bank]=1;data_wa[bank]=host_row;data_w[bank]=write_data;end
                else if(read_en) begin data_re[bank]=1;data_ra[bank]=host_row;end
            end
            if(state==BF_READ) begin
                data_re[bank]=32'(bank)<n;data_ra[bank]=RW'(bf_address>>KW);
                root_re[bank]=(root_variable&~root_mask)==0;
                root_ra[bank]=active_root_base+RRW'(root_address>>KW);
            end
            if(state==MUL_READ && 1'(bank/LANES)==point_half && 32'(bank%LANES)<mul_lanes) begin
                data_re[bank]=1;data_ra[bank]=RW'(point_base>>KW);
                root_re[bank]=active_op==2;root_ra[bank]=active_root_base+RRW'(point_base>>KW);
            end
            if((state==BF_READ || state==BF_DRAIN) && bf_valid_option[pairing] && 32'(bank)<n) begin
                data_we[bank]=1;data_wa[bank]=row_tag[6][bank];data_w[bank]=bf_write_option[pairing];
            end
            if((state==MUL_READ || state==MUL_DRAIN) && mul_valid[bank%LANES] && 1'(bank/LANES)==point_half_pipe[4]) begin
                data_we[bank]=1;data_wa[bank]=row_tag[4][bank];data_w[bank]=product[bank%LANES];
            end
        end
        always_ff @(posedge clk) if(rst_n) begin
            if(data_re[bank]) data_q[bank]<=data_mem[data_ra[bank]];
            if(data_we[bank]) data_mem[data_wa[bank]]<=data_w[bank];
            if(root_re[bank]) root_q[bank]<=root_mem[root_ra[bank]];
            if(state==IDLE && !start && root_we && !half_write_illegal && host_bank==KW'(bank))
                root_mem[host_root_base+RRW'(host_row)]<=write_data;
        end
        // synthesis translate_off
        always @(posedge clk) if(rst_n) begin
            if(data_re[bank] && data_we[bank] && data_ra[bank]==data_wa[bank]) $fatal(1,"bank-centric mixed-port RAM collision");
            if(state==BF_READ && root_re[bank] && (bank_of(AW'(root_address))!=KW'(bank) || root_address>=(n>>1)))
                $fatal(1,"bank-centric root schedule mismatch");
        end
        // synthesis translate_on
    end
    always_comb begin
        root_read_count=0;
        for(int bank=0;bank<BANKS;bank=bank+1) root_read_count=root_read_count+32'(root_re[bank]);
    end
    // synthesis translate_off
    initial begin
        if(LANES<1 || LANES>16 || (LANES&(LANES-1))!=0) $fatal(1,"unsupported LANES");
        if(AW<1 || AW>16) $fatal(1,"unsupported AW");
    end
    // synthesis translate_on
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE;busy<=0;done<=0;error<=0;read_valid<=0;
            n<=0;group_index<=0;completed<=0;lg<=0;stage_bit<=0;stage_bit_d<=0;
            pairing_d<=0;rotation_d<=0;base_bank_d<=0;root_base_bank_d<=0;
            orientation_d<=0;point_half_d<=0;low_stage_d<=0;orientation_pipe<=0;point_half_pipe<=0;
            active_op<=0;active_inverse<=0;active_dif<=0;active_scale<=0;host_bank_d<=0;active_root_base<=0;
            bf_in_valid<=0;mul_in_valid<=0;
            cycles<=0;butterflies<=0;data_reads<=0;data_writes<=0;root_reads<=0;wait_cycles<=0;
            for(int t=0;t<7;t=t+1) for(int b=0;b<BANKS;b=b+1) row_tag[t][b]<=0;
        end else begin
            done<=0;read_valid<=state==IDLE && !start && read_en && !load_we;
            if(state==IDLE) host_bank_d<=host_bank;
            pairing_d<=pairing;rotation_d<=rotation;stage_bit_d<=stage_bit;
            base_bank_d<=base_bank;root_base_bank_d<=root_base_bank;
            orientation_d<=orientation;point_half_d<=point_half;low_stage_d<=int'(stage_bit)<KW;
            orientation_pipe<={orientation_pipe[5:0],orientation};point_half_pipe<={point_half_pipe[5:0],point_half};
            for(int b=0;b<BANKS;b=b+1) begin
                row_tag[0][b]<=data_ra[b];
                for(int t=1;t<7;t=t+1) row_tag[t][b]<=row_tag[t-1][b];
            end
            for(int lane=0;lane<LANES;lane=lane+1) begin
                bf_in_valid[lane]<=state==BF_READ && 32'(lane)<bf_lanes;
                mul_in_valid[lane]<=state==MUL_READ && 32'(lane)<mul_lanes;
            end
            if(busy) cycles<=cycles+1;
            if(state==BF_READ) begin data_reads<=data_reads+64'(2*bf_lanes);root_reads<=root_reads+64'(root_read_count);end
            if(state==MUL_READ) begin data_reads<=data_reads+64'(mul_lanes);root_reads<=root_reads+64'(root_read_count);end
            if(state==BF_DRAIN || state==MUL_DRAIN) wait_cycles<=wait_cycles+1;
            if((state==BF_READ || state==BF_DRAIN) && bf_valid[0]) begin
                butterflies<=butterflies+64'(bf_lanes);data_writes<=data_writes+64'(2*bf_lanes);completed<=completed+bf_lanes;
                if(completed+bf_lanes==(n>>1)) begin
                    completed<=0;group_index<=0;
                    if((active_dif && stage_bit==0) || (!active_dif && stage_bit==lg-1)) begin
                        if(active_inverse) state<=MUL_READ;else begin busy<=0;done<=1;state<=IDLE;end
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
                    if(size_log2<1 || int'(size_log2)>AW || (op==2 && (root_phase==1 || root_phase==2))) begin error<=1;done<=1;end
                    else begin
                        n<=32'd1<<size_log2;lg<=size_log2;group_index<=0;completed<=0;
                        active_op<=op;active_inverse<=inverse;active_dif<=dif;active_scale<=scale;active_root_base<=phase_base(root_phase);
                        stage_bit<=dif ? size_log2-1 : 0;busy<=1;state<=op==0 ? BF_READ : MUL_READ;
                    end
                end
                BF_READ: if(((group_index+1)<<KW)>=n) state<=BF_DRAIN;else group_index<=group_index+1;
                MUL_READ: if(((group_index+1)<<LW)>=n) state<=MUL_DRAIN;else group_index<=group_index+1;
                default: ;
            endcase
        end
    end
endmodule

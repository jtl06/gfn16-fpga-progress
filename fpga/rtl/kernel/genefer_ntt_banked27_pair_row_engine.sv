// Row-only variant: setup-decoded data rows; root routing and timing unchanged.
// Experimental adjacent-stage fusion; one data store, one shared array.
// See NTT-PAIR-BANKED-DESIGN.md. Frozen engines/helpers are unchanged.
module genefer_ntt_banked27_pair_row_engine #(
    parameter int AW=16,
    parameter int LANES=4,
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] Q=32'd4190109697
) (
    input logic clk,rst_n,load_we,root_we,read_en,
    input logic [AW-1:0] host_addr,
    input logic [31:0] write_data,
    output logic read_valid,
    output logic [31:0] read_data,
    input logic vector_load_we,vector_read_en,
    input logic [AW-1:0] vector_addr,
    input logic [LANES-1:0] vector_lane_mask,
    input logic [LANES*32-1:0] vector_write_data,
    output logic vector_read_valid,host_error,
    output logic [LANES-1:0] vector_read_mask,
    output logic [LANES*32-1:0] vector_read_data,
    input logic start,inverse,dif,
    input logic [1:0] root_phase,op,
    input logic [4:0] size_log2,
    input logic [31:0] scale,
    output logic busy,done,error,
    output logic [63:0] cycles,butterflies,data_reads,data_writes,root_reads,wait_cycles
);
    localparam int LW=$clog2(LANES),KW=LW+1,BANKS=2*LANES;
    localparam int PW=KW>1 ? $clog2(KW) : 1;
    localparam int SIW=AW>1 ? $clog2(AW) : 1;
    localparam int RW=AW>KW ? AW-KW : 1;
    localparam int DEPTH=1 << (AW>KW ? AW-KW : 0);
    localparam int HALF_DEPTH=1 << (AW>KW+1 ? AW-KW-1 : 0);
    localparam int ROOT_DEPTH=2*DEPTH+2*HALF_DEPTH,RRW=$clog2(ROOT_DEPTH);
    localparam int MID_DEPTH=2*HALF_DEPTH,MRW=$clog2(MID_DEPTH);
    typedef enum logic [3:0] {IDLE,STAGE_SETUP,BF_READ,BF_DRAIN,PAIR_RUN,MUL_READ,MUL_DRAIN,FAULT_DRAIN} state_t;
    state_t state;
    logic [31:0] n,group_index,completed,completed_group,lg_groups,read_group;
    logic [31:0] base_addr,point_base,root_base,bf_lanes,mul_lanes,root_read_count;
    logic [4:0] lg,stage_bit,second_stage,read_stage;
    logic active_inverse,active_dif,pair_mode,setup_pair,root_second;
    logic [1:0] active_op;
    logic [31:0] active_scale;
    logic [SIW-1:0] representatives[0:KW-1],fixed_source[0:AW-1];
    logic [AW-1:0] fixed_mask;
    logic [RW-1:0] row_masks[0:1],transform_row[0:BANKS-1];
    logic [PW-1:0] row_coordinates[0:1];
    logic [PW-1:0] layer_pairing[0:1],layer_rotation[0:1];
    logic [4:0] layer_shift[0:1];
    logic [KW-1:0] layer_mask[0:1];
    logic [PW-1:0] pairing,rotation,pairing_d,rotation_d,pairing_pipe[0:6];
    logic [4:0] root_shift;
    logic [KW-1:0] root_mask,root_mask_d,base_bank,folded_root_bank,folded_root_bank_d;
    logic orientation,orientation_d,point_half,point_half_d,second_d;
    logic [6:0] orientation_pipe,point_half_pipe;
    logic [31:0] held[0:BANKS-1],transform_result[0:BANKS-1];
    logic [AW-1:0] issue_group_d,group_pipe[0:5];
    logic [1:0] issue_kind_d,kind_pipe[0:5];
    logic [5:0] valid_pipe;
    logic transform_read,first_data_read,hold_good,pair_write,single_write,point_write;
    logic all_bf_valid,any_bf_valid,all_mul_valid,any_mul_valid;
    logic fault_now,fault_reg,pair_rst_n;
    logic [3:0] fault_drain;
    logic pair_start,pair_busy,pair_done,pair_error,pair_root_read,pair_root_second;
    logic pair_issue,pair_issue_second,pair_hold,pair_commit;
    logic [AW-1:0] pair_root_group,pair_issue_group,pair_hold_group,pair_commit_group;
    logic [AW+4:0] pair_cycles;
    logic [RRW-1:0] active_root_base,host_root_base;
    logic [KW-1:0] host_bank,host_bank_d,vector_base_bank,vector_base_bank_d;
    logic [RW-1:0] host_row;
    logic half_write_illegal,vector_request,vector_ok;
    logic [31:0] host_n;
    logic [LANES-1:0] effective_mask;
    logic [BANKS-1:0] data_re,data_we,root_re;
    logic [RW-1:0] data_ra[0:BANKS-1],data_wa[0:BANKS-1],row_tag[0:6][0:BANKS-1];
    logic [RRW-1:0] root_ra[0:BANKS-1];
    logic [31:0] data_w[0:BANKS-1],data_q[0:BANKS-1],root_q[0:BANKS-1];
    logic [LANES-1:0] bf_in_valid,mul_in_valid,bf_valid,mul_valid;
    logic [31:0] bf0[0:LANES-1],bf1[0:LANES-1],product[0:LANES-1];
    logic [31:0] root_rotate_option[0:BANKS-1][0:KW-1],root_rotated[0:BANKS-1];

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
    function automatic logic [KW-1:0] rol(input logic [KW-1:0] b,input logic [PW-1:0] r);
        rol=(b<<r)|(b>>(KW-int'(r)));
    endfunction
    function automatic int rep_for(input int r,s,input bit paired,input bit descending);
        int other;
        begin
            other=descending ? s-1 : s+1;
            if(r==s%KW) rep_for=s;
            else if(paired && r==other%KW) rep_for=other;
            else rep_for=r;
        end
    endfunction
    function automatic bit is_fixed(input int j,s,input bit paired,input bit descending);
        bit chosen;
        begin
            chosen=0;
            for(int r=0;r<KW;r=r+1) if(rep_for(r,s,paired,descending)==j) chosen=1;
            is_fixed=!chosen;
        end
    endfunction
    function automatic int source_for(input int j,s,input bit paired,input bit descending);
        int count;
        begin
            count=0;
            for(int k=0;k<j;k=k+1) if(is_fixed(k,s,paired,descending)) count=count+1;
            source_for=count;
        end
    endfunction
    // synthesis translate_off
    function automatic logic [31:0] bank_address(input logic [KW-1:0] b);
        logic [31:0] a;
        logic [KW-1:0] variable_bits;
        begin
            a=base_addr;variable_bits=b^base_bank;
            for(int r=0;r<KW;r=r+1)
                if(r<int'(lg)) a=a|(32'(variable_bits[r])<<representatives[r]);
            bank_address=a;
        end
    endfunction
    // synthesis translate_on
    assign setup_pair=LANES>1 && (active_dif ? stage_bit>=1 : stage_bit+1<lg);
    assign lg_groups=(n>>KW)!=0 ? n>>KW : 32'd1;
    assign pair_start=state==STAGE_SETUP && setup_pair && !fault_reg;
    assign pair_rst_n=rst_n && !fault_reg;
    genefer_ntt_pair_schedule #(.GROUP_AW(AW)) pair_schedule (
        .clk,.rst_n(pair_rst_n),.start(pair_start),.group_count((AW+1)'(lg_groups)),
        .busy(pair_busy),.done(pair_done),.error(pair_error),.root_read(pair_root_read),
        .root_second(pair_root_second),.root_group(pair_root_group),
        .issue(pair_issue),.issue_second(pair_issue_second),.issue_group(pair_issue_group),
        .hold_first(pair_hold),.hold_group(pair_hold_group),.commit(pair_commit),
        .commit_group(pair_commit_group),.active_cycles(pair_cycles)
    );
    assign vector_request=vector_load_we || vector_read_en;
    assign host_n=(size_log2>=1 && int'(size_log2)<=AW) ? 32'd1<<size_log2 : 0;
    assign vector_ok=host_n!=0 && (32'(vector_addr)&32'(LANES-1))==0 && 32'(vector_addr)<host_n;
    assign vector_base_bank=bank_of(vector_addr);
    for(genvar h=0;h<LANES;h=h+1) begin : vector_masks
        assign effective_mask[h]=vector_lane_mask[h] && (32'(vector_addr)+32'(h))<host_n;
        assign vector_read_data[h*32+:32]=vector_read_route[LW].words[h];
    end
    // Contiguous aligned logical groups become an XOR permutation within one
    // physical bank half. Host vector routing is O(LANES*log LANES), not a
    // separate BANKS-way mux for every host lane.
    for(genvar d=0;d<=LW;d=d+1) begin : vector_write_route
        logic [31:0] words [0:LANES-1];
        logic [LANES-1:0] mask;
        for(genvar h=0;h<LANES;h=h+1) begin : lanes
            if(d==0) begin
                assign words[h]=vector_write_data[h*32+:32];assign mask[h]=effective_mask[h];
            end else begin
                assign words[h]=vector_base_bank[d-1] ? vector_write_route[d-1].words[h^(1<<(d-1))] : vector_write_route[d-1].words[h];
                assign mask[h]=vector_base_bank[d-1] ? vector_write_route[d-1].mask[h^(1<<(d-1))] : vector_write_route[d-1].mask[h];
            end
        end
    end
    for(genvar d=0;d<=LW;d=d+1) begin : vector_read_route
        logic [31:0] words [0:LANES-1];
        for(genvar h=0;h<LANES;h=h+1) begin : lanes
            if(d==0) assign words[h]=vector_base_bank_d[LW] ? data_q[h+LANES] : data_q[h];
            else assign words[h]=vector_base_bank_d[d-1] ? vector_read_route[d-1].words[h^(1<<(d-1))] : vector_read_route[d-1].words[h];
        end
    end
    assign host_bank=bank_of(host_addr);
    assign host_row=RW'(host_addr>>KW);
    assign host_root_base=phase_base(root_phase);
    assign half_write_illegal=(root_phase==1 || root_phase==2) && host_addr[AW-1];
    assign read_data=data_q[host_bank_d];
    assign bf_lanes=(n>>1)<LANES ? n>>1 : LANES;
    assign mul_lanes=n<LANES ? n : LANES;
    assign root_second=state==PAIR_RUN && pair_root_second;
    assign read_group=state==PAIR_RUN ? 32'(pair_root_group) : group_index;
    assign read_stage=root_second ? second_stage : stage_bit;
    assign pairing=layer_pairing[root_second];
    assign rotation=layer_rotation[root_second];
    assign root_shift=layer_shift[root_second];
    assign root_mask=layer_mask[root_second];
    assign base_bank=bank_of(AW'(base_addr));
    assign orientation=base_bank[pairing];
    assign point_base=group_index<<LW;
    assign point_half=(bank_of(AW'(point_base))&KW'(1<<LW))!=0;
    assign root_base=(base_addr&((32'd1<<read_stage)-1))<<root_shift;
    assign folded_root_bank=bank_of(AW'(root_base)) ^ rol(base_bank&root_mask,rotation);
    assign transform_read=(state==BF_READ || (state==PAIR_RUN && pair_root_read)) && !fault_reg && !fault_now;
    assign first_data_read=transform_read && !root_second;
    always_comb begin
        base_addr=0;
        for(int j=0;j<AW;j=j+1)
            base_addr[j]=fixed_mask[j] ? read_group[5'(fixed_source[j])] : 1'b0;
    end
    // Generalized folded root route: XOR, fixed rotation, arbitrary-bit mask.
    for(genvar d=0;d<=KW;d=d+1) begin : root_xor_stages
        logic [31:0] words[0:BANKS-1];
        for(genvar b=0;b<BANKS;b=b+1) begin : banks
            if(d==0) assign words[b]=root_q[b];
            else assign words[b]=folded_root_bank_d[d-1] ? root_xor_stages[d-1].words[b^(1<<(d-1))] : root_xor_stages[d-1].words[b];
        end
    end
    for(genvar b=0;b<BANKS;b=b+1) begin : root_route
        for(genvar d=0;d<KW;d=d+1) begin : dimensions
            localparam int ROT=((b<<d)|(b>>(KW-d)))&(BANKS-1);
            assign root_rotate_option[b][d]=root_xor_stages[KW].words[ROT];
        end
        assign root_rotated[b]=root_rotate_option[b][rotation_d];
    end
    for(genvar d=0;d<=KW;d=d+1) begin : root_clip_stages
        logic [31:0] words[0:BANKS-1];
        for(genvar b=0;b<BANKS;b=b+1) begin : banks
            if(d==0) assign words[b]=root_rotated[b];
            else assign words[b]=root_mask_d[d-1] ? root_clip_stages[d-1].words[b] : root_clip_stages[d-1].words[b&~(1<<(d-1))];
        end
    end
    always_comb begin
        any_bf_valid=|bf_valid;any_mul_valid=|mul_valid;
        all_bf_valid=1;all_mul_valid=1;
        for(int lane=0;lane<LANES;lane=lane+1) begin
            if(32'(lane)<bf_lanes) all_bf_valid=all_bf_valid && bf_valid[lane];
            if(32'(lane)<mul_lanes) all_mul_valid=all_mul_valid && mul_valid[lane];
        end
        hold_good=state==PAIR_RUN && pair_hold && all_bf_valid && valid_pipe[5] &&
                  kind_pipe[5]==1 && group_pipe[5]==pair_hold_group;
        pair_write=state==PAIR_RUN && pair_commit && all_bf_valid && valid_pipe[5] &&
                   kind_pipe[5]==2 && group_pipe[5]==pair_commit_group;
        single_write=(state==BF_READ || state==BF_DRAIN) && any_bf_valid && all_bf_valid &&
                     valid_pipe[5] && kind_pipe[5]==0 && 32'(group_pipe[5])==completed_group;
        point_write=(state==MUL_READ || state==MUL_DRAIN) && any_mul_valid && all_mul_valid &&
                    valid_pipe[5] && kind_pipe[5]==3 && 32'(group_pipe[5])==completed_group;
        fault_now=0;
        if(state==PAIR_RUN) begin
            if(pair_error || (pair_hold && !hold_good) || (pair_commit && !pair_write) ||
               (any_bf_valid && !(pair_hold || pair_commit))) fault_now=1;
            if(pair_issue && (!bf_in_valid[0] || issue_group_d!=pair_issue_group ||
                second_d!=pair_issue_second)) fault_now=1;
        end
        if((state==BF_READ || state==BF_DRAIN) && (valid_pipe[5] || any_bf_valid || any_mul_valid) && !single_write) fault_now=1;
        if((state==MUL_READ || state==MUL_DRAIN) && (valid_pipe[5] || any_bf_valid || any_mul_valid) && !point_write) fault_now=1;
    end

    for(genvar lane=0;lane<LANES;lane=lane+1) begin : arithmetic
        logic [31:0] data_lo [0:KW-1],data_hi [0:KW-1],root_lo [0:KW-1],root_hi [0:KW-1];
        logic [31:0] u,v,w,mul_lhs,mul_rhs;
        logic shared_valid;
        logic [5:0] point_type_pipe;
        for(genvar p=0;p<KW;p=p+1) begin : pair_patterns
            localparam int LO=insert_zero(lane,p),HI=LO|(1<<p);
            assign data_lo[p]=second_d ? held[LO] : data_q[LO];assign data_hi[p]=second_d ? held[HI] : data_q[HI];
            assign root_lo[p]=root_clip_stages[KW].words[LO];assign root_hi[p]=root_clip_stages[KW].words[HI];
        end
        assign u=orientation_d ? data_hi[pairing_d] : data_lo[pairing_d];
        assign v=orientation_d ? data_lo[pairing_d] : data_hi[pairing_d];
        assign w=orientation_d ? root_hi[pairing_d] : root_lo[pairing_d];
        genefer_ntt_difdit_butterfly27 #(.P(P),.Q(Q)) butterfly (
            .clk,.rst_n,.in_valid((bf_in_valid[lane] || mul_in_valid[lane]) && !fault_reg && !fault_now),
            .dif(bf_in_valid[lane] && active_dif),
            .u(bf_in_valid[lane] ? u : 32'd0),
            .v(bf_in_valid[lane] ? v : mul_lhs),
            .w(bf_in_valid[lane] ? w : mul_rhs),
            .out_valid(shared_valid),.y0(bf0[lane]),.y1(bf1[lane])
        );
        assign mul_lhs=point_half_d ? data_q[lane+LANES] : data_q[lane];
        assign mul_rhs=active_op==1 ? mul_lhs : active_op==2 ?
            (point_half_d ? root_q[lane+LANES] : root_q[lane]) : active_scale;
        assign bf_valid[lane]=shared_valid && !point_type_pipe[5];
        assign mul_valid[lane]=shared_valid && point_type_pipe[5];
        assign product[lane]=bf0[lane];
        always_ff @(posedge clk or negedge rst_n) begin
            if(!rst_n) point_type_pipe<=0;
            else point_type_pipe<={point_type_pipe[4:0],mul_in_valid[lane] && !fault_reg && !fault_now};
        end
        // synthesis translate_off
        always @(posedge clk) if(rst_n && bf_in_valid[lane] && mul_in_valid[lane])
            $fatal(1,"shared arithmetic request collision");
        // synthesis translate_on
    end

    for(genvar bank=0;bank<BANKS;bank=bank+1) begin : memories
        logic [31:0] bf_write_option [0:KW-1];
        logic [KW-1:0] bf_valid_option,root_variable;
        logic [31:0] root_address;
        logic [KW-1:0] row_variable;
        for(genvar p=0;p<KW;p=p+1) begin : write_patterns
            localparam int LANE=remove_bit(bank,p);
            assign bf_write_option[p]=(orientation_pipe[6]==1'((bank>>p)&1)) ? bf0[LANE] : bf1[LANE];
            assign bf_valid_option[p]=bf_valid[LANE];
        end
        assign row_variable=KW'(bank)^base_bank;
        assign transform_row[bank]=RW'(base_addr>>KW) |
            (row_variable[row_coordinates[0]] ? row_masks[0] : RW'(0)) |
            (row_variable[row_coordinates[1]] ? row_masks[1] : RW'(0));
        // synthesis translate_off
        logic [31:0] bf_address;
        assign bf_address=bank_address(KW'(bank));
        always_ff @(posedge clk) if(rst_n && transform_read && 32'(bank)<n)
            if(transform_row[bank]!=RW'(bank_address(KW'(bank))>>KW))
                $fatal(1,"row-only decode identity mismatch");
        // synthesis translate_on
        assign transform_result[bank]=bf_write_option[pairing_pipe[6]];
        assign root_variable=ror(KW'(bank)^bank_of(AW'(root_base)),rotation);
        always_comb begin
            root_address=root_base;
            for(int r=0;r<KW;r=r+1)
                if(root_mask[r]) root_address=root_address|(32'(root_variable[r])<<(5'(representatives[r])+root_shift));
        end
        always_comb begin
            data_re[bank]=0;data_we[bank]=0;root_re[bank]=0;
            data_ra[bank]=0;data_wa[bank]=0;root_ra[bank]=0;data_w[bank]=0;
            if(state==IDLE && !start) begin
                if(vector_request) begin
                    if(vector_ok && 1'(bank/LANES)==vector_base_bank[LW] && vector_write_route[LW].mask[bank%LANES]) begin
                        data_we[bank]=vector_load_we;data_re[bank]=!vector_load_we;
                        data_wa[bank]=RW'(vector_addr>>KW);data_ra[bank]=RW'(vector_addr>>KW);
                        data_w[bank]=vector_write_route[LW].words[bank%LANES];
                    end
                end else if(host_bank==KW'(bank)) begin
                    if(load_we) begin data_we[bank]=1;data_wa[bank]=host_row;data_w[bank]=write_data;end
                    else if(read_en) begin data_re[bank]=1;data_ra[bank]=host_row;end
                end
            end
            if(transform_read) begin
                data_re[bank]=first_data_read && 32'(bank)<n;data_ra[bank]=transform_row[bank];
                root_re[bank]=(root_variable&~root_mask)==0;
                root_ra[bank]=active_root_base+RRW'(root_address>>KW);
            end
            if(state==MUL_READ && !fault_reg && !fault_now && 1'(bank/LANES)==point_half && 32'(bank%LANES)<mul_lanes) begin
                data_re[bank]=1;data_ra[bank]=RW'(point_base>>KW);
                root_re[bank]=active_op==2;root_ra[bank]=active_root_base+RRW'(point_base>>KW);
            end
            if((single_write || pair_write) && !fault_reg && !fault_now && 32'(bank)<n) begin
                data_we[bank]=1;data_wa[bank]=row_tag[6][bank];data_w[bank]=transform_result[bank];
            end
            if(point_write && !fault_reg && !fault_now && mul_valid[bank%LANES] && 1'(bank/LANES)==point_half_pipe[6]) begin
                data_we[bank]=1;data_wa[bank]=row_tag[6][bank];data_w[bank]=product[bank%LANES];
            end
        end
        // Isolate RAM extraction in a standalone leaf module; no timing change.
        logic [31:0] data_read_q,root_read_q;
        logic data_read_en,data_write_en,root_read_en,root_write_en;
        logic [RW-1:0] data_read_addr,data_write_addr;
        logic [RRW-1:0] root_read_addr,root_write_addr;
        logic [31:0] data_write_word;
        assign data_q[bank]=data_read_q;
        assign root_q[bank]=root_read_q;
        assign data_read_en=data_re[bank];
        assign data_write_en=data_we[bank];
        assign root_read_en=root_re[bank];
        assign root_write_en=state==IDLE && !start && !vector_request && root_we &&
                              !half_write_illegal && host_bank==KW'(bank);
        assign data_read_addr=data_ra[bank];
        assign data_write_addr=data_wa[bank];
        assign data_write_word=data_w[bank];
        assign root_read_addr=root_ra[bank];
        assign root_write_addr=host_root_base+RRW'(host_row);
        genefer_sdp_ram32 #(.AW(RW),.DEPTH(DEPTH)) data_ram (
            .clk,.rst_n,.read_en(data_read_en),.write_en(data_write_en),
            .read_addr(data_read_addr),.write_addr(data_write_addr),
            .write_data(data_write_word),.read_data(data_read_q)
        );
        logic [31:0] twist_q,middle_q,post_q;
        logic read_twist,read_middle,read_post;
        logic [MRW-1:0] middle_read_addr,middle_write_addr;
        logic [RW-1:0] post_read_addr,post_write_addr;
        assign read_twist=active_root_base==0;
        assign read_post=active_root_base==RRW'(DEPTH+2*HALF_DEPTH);
        assign read_middle=!read_twist && !read_post;
        assign root_read_q=read_twist ? twist_q : read_post ? post_q : middle_q;
        assign middle_read_addr=MRW'(root_read_addr-RRW'(DEPTH));
        assign middle_write_addr=MRW'(root_write_addr-RRW'(DEPTH));
        assign post_read_addr=RW'(root_read_addr-RRW'(DEPTH+2*HALF_DEPTH));
        assign post_write_addr=RW'(root_write_addr-RRW'(DEPTH+2*HALF_DEPTH));
        genefer_sdp_ram32 #(.AW(RW),.DEPTH(DEPTH)) twist_ram (
            .clk,.rst_n,.read_en(root_read_en && read_twist),
            .write_en(root_write_en && root_phase==0),
            .read_addr(RW'(root_read_addr)),.write_addr(RW'(root_write_addr)),
            .write_data(write_data),.read_data(twist_q)
        );
        genefer_sdp_ram32 #(.AW(MRW),.DEPTH(MID_DEPTH)) middle_ram (
            .clk,.rst_n,.read_en(root_read_en && read_middle),
            .write_en(root_write_en && (root_phase==1 || root_phase==2)),
            .read_addr(middle_read_addr),.write_addr(middle_write_addr),
            .write_data(write_data),.read_data(middle_q)
        );
        genefer_sdp_ram32 #(.AW(RW),.DEPTH(DEPTH)) post_ram (
            .clk,.rst_n,.read_en(root_read_en && read_post),
            .write_en(root_write_en && root_phase==3),
            .read_addr(post_read_addr),.write_addr(post_write_addr),
            .write_data(write_data),.read_data(post_q)
        );
        // synthesis translate_off
        always @(posedge clk) if(rst_n) begin : verify_bank_ports
            logic [31:0] expected_base,expected_address;
            logic [KW-1:0] variable_bits;
            if(data_we[bank] && data_w[bank]>=P) $fatal(1,"noncanonical NTT27 data write");
            if(root_write_en && write_data>=P) $fatal(1,"noncanonical NTT27 root write");
            if(data_re[bank] && data_we[bank] && data_ra[bank]==data_wa[bank]) $fatal(1,"bank-centric mixed-port RAM collision");
            if(transform_read && root_re[bank] && (bank_of(AW'(root_address))!=KW'(bank) || root_address>=(n>>1)))
                $fatal(1,"bank-centric root schedule mismatch");
            if(first_data_read && 32'(bank)<n && (bank_of(AW'(bf_address))!=KW'(bank) || bf_address>=n))
                $fatal(1,"pair data bank geometry mismatch");
            if(state!=IDLE && (fault_now || fault_reg) && data_we[bank])
                $fatal(1,"unsafe pair write during fault quarantine");
            if((pair_write || single_write) && !fault_now && !fault_reg && 32'(bank)<n) begin
                expected_base=0;
                for(int j=0;j<AW;j=j+1)
                    if(fixed_mask[j]) expected_base[j]=group_pipe[5][fixed_source[j]];
                variable_bits=KW'(bank)^bank_of(AW'(expected_base));
                expected_address=expected_base;
                for(int r=0;r<KW;r=r+1)
                    if(r<int'(lg)) expected_address=expected_address|(32'(variable_bits[r])<<representatives[r]);
                if(data_wa[bank]!=RW'(expected_address>>KW))
                    $fatal(1,"pair data row tag mismatch");
            end
        end
        // synthesis translate_on
    end
    always_comb begin
        root_read_count=0;
        for(int bank=0;bank<BANKS;bank=bank+1) root_read_count=root_read_count+32'(root_re[bank]);
    end
    // synthesis translate_off
    always @(posedge clk) if(rst_n) begin
        if(state==MUL_READ && !fault_now && !fault_reg && root_read_count!=(active_op==2 ? mul_lanes : 0))
            $fatal(1,"pointwise root count disagrees with physical ports");
    end
    initial begin
        if(LANES<1 || LANES>64 || (LANES&(LANES-1))!=0) $fatal(1,"unsupported LANES");
        if(AW<1 || AW>16) $fatal(1,"unsupported AW");
    end
    // synthesis translate_on
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE;busy<=0;done<=0;error<=0;read_valid<=0;
            vector_read_valid<=0;vector_read_mask<=0;host_error<=0;vector_base_bank_d<=0;
            n<=0;group_index<=0;completed<=0;completed_group<=0;lg<=0;stage_bit<=0;second_stage<=0;
            pair_mode<=0;pairing_d<=0;rotation_d<=0;root_mask_d<=0;folded_root_bank_d<=0;
            fixed_mask<=0;orientation_d<=0;point_half_d<=0;second_d<=0;
            orientation_pipe<=0;point_half_pipe<=0;issue_group_d<=0;issue_kind_d<=0;valid_pipe<=0;
            fault_reg<=0;fault_drain<=0;
            active_op<=0;active_inverse<=0;active_dif<=0;active_scale<=0;host_bank_d<=0;active_root_base<=0;
            bf_in_valid<=0;mul_in_valid<=0;
            cycles<=0;butterflies<=0;data_reads<=0;data_writes<=0;root_reads<=0;wait_cycles<=0;
            for(int i=0;i<2;i=i+1) begin layer_pairing[i]<=0;layer_rotation[i]<=0;layer_shift[i]<=0;layer_mask[i]<=0;row_masks[i]<=0;row_coordinates[i]<=0;end
            for(int r=0;r<KW;r=r+1) representatives[r]<=0;
            for(int j=0;j<AW;j=j+1) fixed_source[j]<=0;
            for(int t=0;t<7;t=t+1) begin
                pairing_pipe[t]<=0;
                for(int b=0;b<BANKS;b=b+1) row_tag[t][b]<=0;
            end
            for(int b=0;b<BANKS;b=b+1) held[b]<=0;
            for(int t=0;t<6;t=t+1) begin group_pipe[t]<=0;kind_pipe[t]<=0;end
        end else begin
            done<=0;read_valid<=state==IDLE && !start && !vector_request && read_en && !load_we;
            vector_read_valid<=state==IDLE && !start && vector_read_en && !vector_load_we && vector_ok;
            vector_read_mask<=state==IDLE && !start && vector_read_en && !vector_load_we && vector_ok ? effective_mask : '0;
            host_error<=state==IDLE && !start && vector_request && !vector_ok;
            if(state==IDLE && !start && vector_read_en && !vector_load_we && vector_ok)
                vector_base_bank_d<=vector_base_bank;
            if(state==IDLE) host_bank_d<=host_bank;
            pairing_d<=pairing;rotation_d<=rotation;root_mask_d<=root_mask;folded_root_bank_d<=folded_root_bank;
            orientation_d<=orientation;point_half_d<=point_half;second_d<=root_second;
            issue_group_d<=AW'(state==MUL_READ ? group_index : read_group);
            issue_kind_d<=state==PAIR_RUN ? (root_second ? 2'd2 : 2'd1) : state==BF_READ ? 2'd0 : 2'd3;
            valid_pipe<={valid_pipe[4:0],(bf_in_valid[0] || mul_in_valid[0]) && !fault_reg && !fault_now};
            group_pipe[0]<=issue_group_d;kind_pipe[0]<=issue_kind_d;
            for(int t=1;t<6;t=t+1) begin group_pipe[t]<=group_pipe[t-1];kind_pipe[t]<=kind_pipe[t-1];end
            orientation_pipe<={orientation_pipe[5:0],orientation};
            point_half_pipe<={point_half_pipe[5:0],point_half};
            pairing_pipe[0]<=pairing;
            for(int t=1;t<7;t=t+1) pairing_pipe[t]<=pairing_pipe[t-1];
            for(int b=0;b<BANKS;b=b+1) begin
                // B-root event reconstructs DATA rows from that same pair group.
                // These are never root_address rows or the A stream's counter.
                row_tag[0][b]<=transform_read ? transform_row[b] : data_ra[b];
                for(int t=1;t<7;t=t+1) row_tag[t][b]<=row_tag[t-1][b];
                if(hold_good && !fault_now && !fault_reg && 32'(b)<n) held[b]<=transform_result[b];
            end
            for(int lane=0;lane<LANES;lane=lane+1) begin
                bf_in_valid[lane]<=transform_read && 32'(lane)<bf_lanes;
                mul_in_valid[lane]<=state==MUL_READ && !fault_reg && !fault_now && 32'(lane)<mul_lanes;
            end
            if(busy) cycles<=cycles+1;
            if(transform_read) begin
                root_reads<=root_reads+64'(root_read_count);
                if(first_data_read) data_reads<=data_reads+64'(2*bf_lanes);
            end
            if(state==MUL_READ && !fault_reg && !fault_now) begin
                data_reads<=data_reads+64'(mul_lanes);
                root_reads<=root_reads+(active_op==2 ? 64'(mul_lanes) : 64'd0);
            end
            if(state==BF_DRAIN || state==MUL_DRAIN || (state==PAIR_RUN && !pair_root_read))
                wait_cycles<=wait_cycles+1;
            if(!fault_now && !fault_reg) begin
                if(hold_good) butterflies<=butterflies+64'(bf_lanes);
                if(pair_write || single_write) begin
                    butterflies<=butterflies+64'(bf_lanes);
                    data_writes<=data_writes+64'(2*bf_lanes);
                    completed<=completed+bf_lanes;completed_group<=completed_group+1;
                    if((pair_write && 32'(pair_commit_group)+1==lg_groups) ||
                       (single_write && completed+bf_lanes==(n>>1))) begin
                        completed<=0;completed_group<=0;group_index<=0;
                        if((active_dif && (pair_mode ? second_stage : stage_bit)==0) ||
                           (!active_dif && (pair_mode ? second_stage : stage_bit)==lg-1)) begin
                            if(active_inverse) state<=MUL_READ;
                            else begin busy<=0;done<=1;state<=IDLE;end
                        end else begin
                            stage_bit<=active_dif ? stage_bit-(pair_mode ? 5'd2 : 5'd1) : stage_bit+(pair_mode ? 5'd2 : 5'd1);
                            state<=STAGE_SETUP;
                        end
                    end
                end
                if(point_write) begin
                    data_writes<=data_writes+64'(mul_lanes);completed<=completed+mul_lanes;completed_group<=completed_group+1;
                    if(completed+mul_lanes==n) begin busy<=0;done<=1;state<=IDLE;end
                end
            end
            case(state)
                IDLE: if(start) begin
                    error<=0;fault_reg<=0;cycles<=0;butterflies<=0;data_reads<=0;data_writes<=0;root_reads<=0;wait_cycles<=0;
                    if(size_log2<1 || int'(size_log2)>AW || (op==2 && (root_phase==1 || root_phase==2))) begin error<=1;done<=1;end
                    else begin
                        n<=32'd1<<size_log2;lg<=size_log2;group_index<=0;completed<=0;completed_group<=0;
                        active_op<=op;active_inverse<=inverse;active_dif<=dif;active_scale<=scale;active_root_base<=phase_base(root_phase);
                        stage_bit<=dif ? size_log2-1 : 0;busy<=1;state<=op==0 ? STAGE_SETUP : MUL_READ;
                    end
                end
                STAGE_SETUP: begin
                    pair_mode<=setup_pair;
                    second_stage<=setup_pair ? (active_dif ? stage_bit-1'b1 : stage_bit+1'b1) : stage_bit;
                    for(int r=0;r<KW;r=r+1) representatives[r]<=SIW'(rep_for(r,int'(stage_bit),setup_pair,active_dif));
                    for(int j=0;j<AW;j=j+1) begin
                        fixed_mask[j]<=is_fixed(j,int'(stage_bit),setup_pair,active_dif);
                        fixed_source[j]<=SIW'(source_for(j,int'(stage_bit),setup_pair,active_dif));
                    end
                    for(int layer=0;layer<2;layer=layer+1) begin : decode_layers
                        integer s,shift;
                        s=int'(stage_bit);
                        if(layer==1 && setup_pair) s=active_dif ? s-1 : s+1;
                        shift=int'(lg)-1-s;
                        layer_pairing[layer]<=PW'(s%KW);layer_rotation[layer]<=PW'(shift%KW);
                        layer_shift[layer]<=5'(shift);
                        row_coordinates[layer]<=PW'(s%KW);
                        row_masks[layer]<=((layer==0 || setup_pair) && s>=KW) ? (RW'(1)<<(s-KW)) : RW'(0);
                        for(int r=0;r<KW;r=r+1)
                            layer_mask[layer][r]<=r<int'(lg) && rep_for(r,int'(stage_bit),setup_pair,active_dif)<s;
                    end
                    state<=setup_pair ? PAIR_RUN : BF_READ;
                end
                BF_READ: if(((group_index+1)<<KW)>=n) state<=BF_DRAIN;else group_index<=group_index+1;
                MUL_READ: if(((group_index+1)<<LW)>=n) state<=MUL_DRAIN;else group_index<=group_index+1;
                FAULT_DRAIN: begin
                    if(fault_drain==1) begin busy<=0;done<=1;state<=IDLE;fault_drain<=0;end
                    else fault_drain<=fault_drain-1'b1;
                end
                default: ;
            endcase
            // Seven complete edges after detection; the detecting edge is not
            // included. All memory writes and new arithmetic are already gated.
            if(fault_now && !fault_reg) begin
                fault_reg<=1;error<=1;fault_drain<=7;state<=FAULT_DRAIN;
            end
        end
    end
endmodule

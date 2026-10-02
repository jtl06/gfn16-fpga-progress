// Experimental27-bit prime basis, Montgomery radix remains2^32.
// Full32-bit host words must be canonical residues<P. No rawdigit conversion.
// Simulation assertions enforce this precondition; production needs a validated producer.
// Wide routing candidate: supports up to 64 arithmetic and host lanes.
// Frozen 4/16-lane shared engine is unchanged; same modulus and schedule.
// Shared-multiplier candidate: pointwise work uses DIT(0,lhs,rhs), retaining y0.
// One Montgomery pipeline per lane; output-kind tags are six clocks deep.
// Both butterfly and pointwise RAM read-to-write distances are seven clocks.
// Control-predecode candidate: one explicit setup cycle per transform stage.
// Stage descriptors and root-counter increments are registered off the issue path.
// Vector/scalar/cache APIs and arithmetic pipelines match the frozen vector engine.
// Vector-host candidate. Scalar/root requests lose priority to any vector
// request; invalid vector requests do not fall back to scalar access.
// Vector lane h is bits [32*h+:32], logical address vector_addr+h.
// Power-of-two root-group comparison; frozen modulemem candidate unchanged.
// Root storage is twist D, combined forward/inverse 2H, post D per bank.
// Resource/timing benefit, if any, must be measured against inferred3D RAM.
// Bank-centric cached DIF/DIT prototype. Frozen parallel/cache engines unchanged.
// Each butterfly lane owns a physical bank pair chosen from KW wiring patterns.
// Root distribution uses structured XOR/rotation/broadcast networks, not one
// BANKS-input mux per arithmetic lane. Pointwise routing uses two bank halves.
module genefer_ntt_banked27_engine #(
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
    typedef enum logic [2:0] {IDLE,STAGE_SETUP,BF_READ,BF_DRAIN,MUL_READ,MUL_DRAIN} state_t;
    state_t state;
    logic [31:0] n,group_index,completed,base_addr,point_base,root_base;
    logic [4:0] lg,stage_bit,root_shift,stage_bit_d,setup_root_shift;
    logic [PW-1:0] pairing,rotation,pairing_d,rotation_d;
    logic [KW-1:0] base_bank,root_base_bank,root_mask,base_bank_d,root_base_bank_d;
    logic orientation,orientation_d,point_half,point_half_d,low_stage_d;
    logic [6:0] orientation_pipe,point_half_pipe;
    logic [1:0] active_op;
    logic active_inverse,active_dif;
    logic [31:0] active_scale,bf_lanes,mul_lanes,root_read_count;
    logic [31:0] stage_toggle_mask,stage_low_mask;
    logic [KW-1:0] stage_root_count;
    logic stage_low;
    logic [AW-1:0] fixed_mask;
    logic [SIW-1:0] fixed_source [0:AW-1];
    logic [AW-1:0] fixed_mask_options [0:AW-1];
    logic [SIW-1:0] fixed_source_options [0:AW-1][0:AW-1];
    logic [RRW-1:0] active_root_base,host_root_base;
    logic [KW-1:0] host_bank,host_bank_d;
    logic [RW-1:0] host_row;
    logic half_write_illegal;
    logic vector_request,vector_ok;
    logic [31:0] host_n;
    logic [LANES-1:0] effective_mask;
    logic [KW-1:0] vector_base_bank,vector_base_bank_d;
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
    function automatic bit fixed_position(input int s,j);
        fixed_position=j!=s && !(j<KW && j!=(s%KW));
    endfunction
    function automatic int fixed_index(input int s,j);
        integer count;
        begin
            count=0;
            for(int i=0;i<j;i=i+1) if(fixed_position(s,i)) count=count+1;
            fixed_index=fixed_position(s,j) ? count : 0;
        end
    endfunction
    for(genvar s=0;s<AW;s=s+1) begin : stage_mapping
        for(genvar j=0;j<AW;j=j+1) begin : bits
            assign fixed_mask_options[s][j]=fixed_position(s,j);
            assign fixed_source_options[j][s]=SIW'(fixed_index(s,j));
        end
    end
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
    assign setup_root_shift=lg-1-stage_bit;
    assign base_bank=bank_of(AW'(base_addr));
    assign orientation=base_bank[pairing];
    assign point_base=group_index<<LW;
    assign point_half=(bank_of(AW'(point_base))&KW'(1<<LW))!=0;
    assign root_base=(base_addr&stage_low_mask)<<root_shift;
    assign root_base_bank=bank_of(AW'(root_base));
    // Runtime sizes below AW need no extra masking: group_index never reaches
    // the high fixed bits. The independent small-N oracle checks this contract.
    always_comb begin : fixed_address_bits
        base_addr=0;
        for(int j=0;j<AW;j=j+1)
            base_addr[j]=fixed_mask[j] ? group_index[5'(fixed_source[j])] : 1'b0;
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
        logic shared_valid;
        logic [5:0] point_type_pipe;
        for(genvar p=0;p<KW;p=p+1) begin : pair_patterns
            localparam int LO=insert_zero(lane,p),HI=LO|(1<<p);
            assign data_lo[p]=data_q[LO];assign data_hi[p]=data_q[HI];
            assign root_lo[p]=root_lane_xor_stages[KW].words[LO];assign root_hi[p]=root_lane_xor_stages[KW].words[HI];
        end
        assign u=orientation_d ? data_hi[pairing_d] : data_lo[pairing_d];
        assign v=orientation_d ? data_lo[pairing_d] : data_hi[pairing_d];
        assign w=orientation_d ? root_hi[pairing_d] : root_lo[pairing_d];
        genefer_ntt_difdit_butterfly27 #(.P(P),.Q(Q)) butterfly (
            .clk,.rst_n,.in_valid(bf_in_valid[lane] || mul_in_valid[lane]),
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
            else point_type_pipe<={point_type_pipe[4:0],mul_in_valid[lane]};
        end
        // synthesis translate_off
        always @(posedge clk) if(rst_n && bf_in_valid[lane] && mul_in_valid[lane])
            $fatal(1,"shared arithmetic request collision");
        // synthesis translate_on
    end

    for(genvar bank=0;bank<BANKS;bank=bank+1) begin : memories
        logic [31:0] bf_write_option [0:KW-1];
        logic [KW-1:0] bf_valid_option,root_variable;
        logic [31:0] bf_address,root_address;
        for(genvar p=0;p<KW;p=p+1) begin : write_patterns
            localparam int LANE=remove_bit(bank,p);
            assign bf_write_option[p]=(orientation_pipe[6]==1'((bank>>p)&1)) ? bf0[LANE] : bf1[LANE];
            assign bf_valid_option[p]=bf_valid[LANE];
        end
        assign bf_address=base_addr|((1'(bank>>pairing)^orientation) ? stage_toggle_mask : 32'd0);
        assign root_variable=ror(KW'(bank)^root_base_bank,rotation);
        assign root_address=root_base|(32'(root_variable)<<root_shift);
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
            if((state==MUL_READ || state==MUL_DRAIN) && mul_valid[bank%LANES] && 1'(bank/LANES)==point_half_pipe[6]) begin
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
        always @(posedge clk) if(rst_n) begin
            if(data_we[bank] && data_w[bank]>=P) $fatal(1,"noncanonical NTT27 data write");
            if(root_write_en && write_data>=P) $fatal(1,"noncanonical NTT27 root write");
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
    always @(posedge clk) if(rst_n) begin
        if(state==BF_READ && root_read_count!=32'(stage_root_count))
            $fatal(1,"predecoded root count disagrees with physical ports");
        if(state==MUL_READ && root_read_count!=(active_op==2 ? mul_lanes : 0))
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
            n<=0;group_index<=0;completed<=0;lg<=0;stage_bit<=0;stage_bit_d<=0;
            pairing_d<=0;rotation_d<=0;base_bank_d<=0;root_base_bank_d<=0;
            pairing<=0;rotation<=0;root_shift<=0;root_mask<=0;stage_root_count<=0;stage_low<=0;
            stage_toggle_mask<=0;stage_low_mask<=0;fixed_mask<=0;
            for(int j=0;j<AW;j=j+1) fixed_source[j]<=0;
            orientation_d<=0;point_half_d<=0;low_stage_d<=0;orientation_pipe<=0;point_half_pipe<=0;
            active_op<=0;active_inverse<=0;active_dif<=0;active_scale<=0;host_bank_d<=0;active_root_base<=0;
            bf_in_valid<=0;mul_in_valid<=0;
            cycles<=0;butterflies<=0;data_reads<=0;data_writes<=0;root_reads<=0;wait_cycles<=0;
            for(int t=0;t<7;t=t+1) for(int b=0;b<BANKS;b=b+1) row_tag[t][b]<=0;
        end else begin
            done<=0;read_valid<=state==IDLE && !start && !vector_request && read_en && !load_we;
            vector_read_valid<=state==IDLE && !start && vector_read_en && !vector_load_we && vector_ok;
            vector_read_mask<=state==IDLE && !start && vector_read_en && !vector_load_we && vector_ok ? effective_mask : '0;
            host_error<=state==IDLE && !start && vector_request && !vector_ok;
            if(state==IDLE && !start && vector_read_en && !vector_load_we && vector_ok)
                vector_base_bank_d<=vector_base_bank;
            if(state==IDLE) host_bank_d<=host_bank;
            pairing_d<=pairing;rotation_d<=rotation;stage_bit_d<=stage_bit;
            base_bank_d<=base_bank;root_base_bank_d<=root_base_bank;
            orientation_d<=orientation;point_half_d<=point_half;low_stage_d<=stage_low;
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
            if(state==BF_READ) begin data_reads<=data_reads+64'(2*bf_lanes);root_reads<=root_reads+64'(stage_root_count);end
            if(state==MUL_READ) begin data_reads<=data_reads+64'(mul_lanes);root_reads<=root_reads+(active_op==2 ? 64'(mul_lanes) : 64'd0);end
            if(state==BF_DRAIN || state==MUL_DRAIN) wait_cycles<=wait_cycles+1;
            if((state==BF_READ || state==BF_DRAIN) && bf_valid[0]) begin
                butterflies<=butterflies+64'(bf_lanes);data_writes<=data_writes+64'(2*bf_lanes);completed<=completed+bf_lanes;
                if(completed+bf_lanes==(n>>1)) begin
                    completed<=0;group_index<=0;
                    if((active_dif && stage_bit==0) || (!active_dif && stage_bit==lg-1)) begin
                        if(active_inverse) state<=MUL_READ;else begin busy<=0;done<=1;state<=IDLE;end
                    end else begin stage_bit<=active_dif ? stage_bit-1 : stage_bit+1;state<=STAGE_SETUP;end
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
                        stage_bit<=dif ? size_log2-1 : 0;busy<=1;state<=op==0 ? STAGE_SETUP : MUL_READ;
                    end
                end
                STAGE_SETUP: begin
                    pairing<=PW'(int'(stage_bit)%KW);
                    root_shift<=setup_root_shift;
                    rotation<=PW'(int'(setup_root_shift)%KW);
                    root_mask<=int'(stage_bit)<KW ? KW'((32'd1<<stage_bit)-1) :
                                ~(KW'(1)<<PW'(int'(stage_bit)%KW));
                    stage_low<=int'(stage_bit)<KW;
                    stage_toggle_mask<=32'd1<<stage_bit;
                    stage_low_mask<=(32'd1<<stage_bit)-1;
                    stage_root_count<=int'(stage_bit)<LW ? KW'(1)<<stage_bit : KW'(LANES);
                    fixed_mask<=fixed_mask_options[SIW'(stage_bit)];
                    for(int j=0;j<AW;j=j+1) fixed_source[j]<=fixed_source_options[j][SIW'(stage_bit)];
                    state<=BF_READ;
                end
                BF_READ: if(((group_index+1)<<KW)>=n) state<=BF_DRAIN;else group_index<=group_index+1;
                MUL_READ: if(((group_index+1)<<LW)>=n) state<=MUL_DRAIN;else group_index<=group_index+1;
                default: ;
            endcase
        end
    end
endmodule

module genefer_ntt_difdit_butterfly27 #(
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] Q=32'd4190109697
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
    genefer_montgomery_mul27_sparse_pipe #(.P(P),.Q(Q)) multiplier (
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
    // synthesis translate_off
    always @(posedge clk) if(rst_n && in_valid && (u>=P || v>=P || w>=P))
        $fatal(1,"noncanonical NTT27 butterfly input");
    // synthesis translate_on
endmodule

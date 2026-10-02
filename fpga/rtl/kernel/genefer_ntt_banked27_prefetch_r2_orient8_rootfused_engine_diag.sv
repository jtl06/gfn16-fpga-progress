// Isolated format2 experiment; source/model checks are not RTL validation.
// Isolated generated-root27 NTT. No arbitrary root_we cache interface.
// Ordered, size/field/format-pinned compact seed profile replaces full root RAM.
// Separate candidate: inactive-bank next-stage seed prefetch. Frozen arithmetic retained.
module genefer_ntt_banked27_prefetch_r2_orient8_rootfused_engine_diag #(
    parameter int AW=16,
    parameter int LANES=4,
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] Q=32'd4190109697
) (
    input logic clk,rst_n,load_we,read_en,
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
    input logic profile_begin,profile_we,profile_commit,
    input logic [4:0] profile_size_log2,
    input logic [31:0] profile_modulus,profile_data,
    input logic [7:0] profile_format,
    input logic [15:0] profile_addr,
    output logic profile_loaded,profile_loading,profile_error,
    output logic [4:0] profile_loaded_size,
    output logic [15:0] profile_next_addr,
    output logic [63:0] seed_setup_cycles,
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
    localparam int SEED_WORDS=4*LANES+1,PROFILE_WORDS=(2*AW+2)*SEED_WORDS;
    localparam int PAW=$clog2(PROFILE_WORDS);
    import genefer_ntt_rootfused_diag_types::*;
    state_t state;
    logic [31:0] n,group_index,completed,base_addr,point_base,root_base;
    logic [4:0] lg,stage_bit,root_shift,stage_bit_d,setup_root_shift;
    logic [PW-1:0] pairing,rotation,pairing_d,rotation_d;
    logic [KW-1:0] base_bank,root_base_bank,root_mask,base_bank_d,root_base_bank_d;
    logic orientation,point_half,point_half_d,low_stage_d;
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

    logic [1:0] phase_reg;
    logic issue_fire,needs_roots,seed_bank_reg;
    logic [8:0] seed_issue,seed_tag;
    logic [31:0] seed_step,profile_q;
    logic profile_read_valid,profile_write_accept;
    logic [PAW-1:0] profile_ram_addr;
    logic [31:0] profile_key;
    logic [4:0] upload_size;
    logic [16:0] generator_groups,generator_period;
    logic [6:0] generator_active;
    logic [2:0] generator_contexts;
    logic generator_ready,generator_valid,generator_busy,generator_done,generator_error,generator_seed_error;
    logic [LANES*32-1:0] generated_roots;
    logic [LANES-1:0] generated_mask;
    logic [31:0] generated_tag;
    prefetch_t prefetch_state;
    logic first_stage,prefetch_bank,seed_loading;
    logic [4:0] prefetch_stage,prefetch_lg,next_stage;
    logic [1:0] prefetch_phase;
    logic [31:0] prefetch_key,prefetch_step,load_key;
    logic [6:0] prefetch_active,load_active,next_active;
    logic [2:0] prefetch_contexts,load_contexts,next_contexts;
    logic [16:0] next_period;
    logic has_next_stage,prefetch_matches;
    logic [31:0] host_write_words[0:LANES-1],host_read_words[0:LANES-1];
    logic [LANES-1:0] host_write_mask;
    logic [31:0] root_words[0:LANES-1];
    genefer_ntt_rootfused_diag_row_tag_pipeline #(.AW(AW),.LANES(LANES),.P(P),.Q(Q)) diagnostic_row_tag_pipeline (
        .clk,.rst_n,.data_ra,.row_tag
    );
    assign next_stage=active_dif ? stage_bit-5'd1 : stage_bit+5'd1;
    assign has_next_stage=active_op==0 && !(active_dif ? stage_bit==0 : stage_bit==lg-1);
    assign next_active=int'(next_stage)<LW ? 7'd1<<next_stage : 7'(LANES);
    assign next_period=int'(next_stage)<KW ? 17'd1 : 17'd1<<(int'(next_stage)-KW+1);
    always_comb begin
        next_contexts=generator_groups<4 ? 3'(generator_groups) : 3'd4;
        if(next_period<17'(next_contexts))next_contexts=3'(next_period);
    end
    assign seed_loading=state==ROOT_LOAD || prefetch_state==PF_LOAD;
    assign load_key=prefetch_state==PF_LOAD ? prefetch_key : profile_key;
    assign load_active=prefetch_state==PF_LOAD ? prefetch_active : generator_active;
    assign load_contexts=prefetch_state==PF_LOAD ? prefetch_contexts : generator_contexts;
    assign prefetch_matches=prefetch_bank==seed_bank_reg && prefetch_stage==stage_bit &&
        prefetch_lg==lg && prefetch_phase==phase_reg;
    logic [31:0] issued_group_d;
    logic [16:0] generated_group;
    logic [63:0] generator_cycles;
    assign needs_roots=state==BF_READ || (state==MUL_READ && active_op==2);
    assign issue_fire=(state==BF_READ || state==MUL_READ) && (!needs_roots || generator_ready);
    assign generator_groups=17'(active_op==0 ? ((n+32'(BANKS)-1)>>KW) : ((n+32'(LANES)-1)>>LW));
    assign generator_active=active_op==0 ? 7'(stage_root_count) : 7'(mul_lanes);
    assign generator_period=active_op!=0 ? 17'd0 : int'(stage_bit)<KW ? 17'd1 : 17'd1<<(int'(stage_bit)-KW+1);
    always_comb begin
        generator_contexts=generator_groups<4 ? 3'(generator_groups) : 3'd4;
        if(generator_period!=0 && generator_period<17'(generator_contexts))
            generator_contexts=3'(generator_period);
        case(phase_reg)
            0:profile_key=0;
            1:profile_key=1+32'(stage_bit);
            2:profile_key=1+32'(AW)+32'(stage_bit);
            default:profile_key=1+2*32'(AW);
        endcase
    end
    assign profile_write_accept=state==IDLE && !start && !profile_begin && profile_we &&
        profile_loading && profile_addr==profile_next_addr && int'(profile_addr)<PROFILE_WORDS && profile_data<P;
    assign profile_ram_addr=profile_write_accept ? PAW'(profile_addr) :
        PAW'(load_key*32'(SEED_WORDS)+32'(seed_issue));
    genefer_sp_ram #(.WIDTH(32),.AW(PAW),.DEPTH(PROFILE_WORDS)) compact_profile (
        .clk,.rst_n,.en(profile_write_accept || (seed_loading && int'(seed_issue)<SEED_WORDS)),
        .write_en(profile_write_accept),.addr(profile_ram_addr),.write_data(profile_data),.read_data(profile_q)
    );
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            profile_loaded<=0;profile_loading<=0;profile_error<=0;profile_loaded_size<=0;profile_next_addr<=0;upload_size<=0;
        end else begin
            profile_error<=0;
            if(!(state==IDLE && start) && (profile_begin || profile_we || profile_commit))begin
                if(state!=IDLE)profile_error<=1;
                else if(profile_begin)begin
                    if(profile_size_log2<1 || int'(profile_size_log2)>AW || profile_modulus!=P || profile_format!=8'd2)profile_error<=1;
                    else begin profile_loaded<=0;profile_loading<=1;profile_next_addr<=0;upload_size<=profile_size_log2;end
                end else if(profile_we)begin
                    if(profile_write_accept)profile_next_addr<=profile_next_addr+1;
                    else profile_error<=1;
                end else if(profile_commit)begin
                    if(profile_loading && int'(profile_next_addr)==PROFILE_WORDS)begin
                        profile_loaded<=1;profile_loading<=0;profile_loaded_size<=upload_size;
                    end else profile_error<=1;
                end
            end
        end
    end
    genefer_root_recurrence27 #(.LANES(LANES),.P(P),.Q(Q),.TAG_W(32)) generated (
        .clk,.rst_n,.seed_we(seed_loading && profile_read_valid && int'(seed_tag)<4*LANES),
        .seed_clear(state==ROOT_CLEAR || prefetch_state==PF_CLEAR),
        .seed_bank(prefetch_state==PF_CLEAR || prefetch_state==PF_LOAD ? prefetch_bank : seed_bank_reg),
        .seed_context(2'(seed_tag>>LW)),.seed_lane(7'(int'(seed_tag)&(LANES-1))),.seed_data(profile_q),
        .start(state==ROOT_START),.config_bank(seed_bank_reg),.config_groups(generator_groups),
        .config_period(generator_period),.config_active_lanes(generator_active),.config_step(seed_step),
        .request_valid(needs_roots && issue_fire),.request_ready(generator_ready),.request_tag(group_index),
        .root_valid(generator_valid),.roots(generated_roots),.root_mask(generated_mask),
        .root_tag(generated_tag),.root_group(generated_group),.busy(generator_busy),
        .done(generator_done),.error(generator_error),.seed_error(generator_seed_error),.cycles(generator_cycles)
    );
    // synthesis translate_off
    always @(posedge clk)if(rst_n)begin
        if(generator_seed_error)$fatal(1,"generated NTT seed loader error");
        if((state==STAGE_SETUP || state==ROOT_WAIT) && !first_stage &&
           prefetch_state==PF_READY && !prefetch_matches)$fatal(1,"prefetch descriptor mismatch");
        if(generator_busy && (prefetch_state==PF_CLEAR || prefetch_state==PF_LOAD) &&
           prefetch_bank==seed_bank_reg && (state==BF_READ || state==BF_DRAIN))
            $fatal(1,"prefetch active-bank collision");
        if((bf_in_valid[0] || (mul_in_valid[0] && active_op==2)) && !generator_valid)
            $fatal(1,"generated NTT root/data valid mismatch");
        if(generator_valid && (generated_tag!=issued_group_d || 32'(generated_group)!=issued_group_d))
            $fatal(1,"generated NTT root tag mismatch");
        for(int j=0;j<LANES;j=j+1)
            if(generator_valid && generated_mask[j]!=(j<int'(generator_active)))
                $fatal(1,"generated NTT root mask mismatch");
    end
    // synthesis translate_on

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
        assign vector_read_data[h*32+:32]=host_read_words[h];
    end
    // Contiguous aligned logical groups become an XOR permutation within one
    // physical bank half. Host vector routing is O(LANES*log LANES), not a
    // separate BANKS-way mux for every host lane.
    genefer_ntt_rootfused_diag_host_write_route #(.AW(AW),.LANES(LANES),.P(P),.Q(Q)) diagnostic_host_write_route (
        .vector_base_bank,.vector_write_data,.effective_mask,.host_write_words,.host_write_mask
    );
    genefer_ntt_rootfused_diag_host_read_route #(.AW(AW),.LANES(LANES),.P(P),.Q(Q)) diagnostic_host_read_route (
        .vector_base_bank_d,.data_q,.host_read_words
    );
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

    // Fuse early-stage root reuse into the existing XOR dimensions.
    // Source index = (lane XOR route_xor) AND root_lane_mask.
    // Constant-index seed inputs; no extra register, latency or data mux layer.
    logic [LW:0] point_bank_d;
    genefer_ntt_rootfused_diag_root_clip_route #(.AW(AW),.LANES(LANES),.P(P),.Q(Q)) diagnostic_root_clip_route (
        .active_op,.low_stage_d,.stage_bit_d,.base_bank_d,.pairing_d,.point_bank_d,.generated_roots,.root_words
    );
    // Same-edge replicas: eight arithmetic lanes per driver, no new latency.
    localparam int ORIENT_TILE_LANES=8,ORIENT_TILES=(LANES+ORIENT_TILE_LANES-1)/ORIENT_TILE_LANES;
    for(genvar tile=0;tile<ORIENT_TILES;tile=tile+1) begin : orientation_tiles
        (* preserve, dont_merge *) logic orientation_q;
        always_ff @(posedge clk or negedge rst_n) begin
            if(!rst_n) orientation_q<=0;
            else orientation_q<=orientation;
        end
    end
    for(genvar lane=0;lane<LANES;lane=lane+1) begin : arithmetic
        logic [31:0] u,v,w,mul_lhs,mul_rhs;
        logic shared_valid;
        logic [5:0] point_type_pipe;
        genefer_ntt_rootfused_diag_butterfly_read_route #(.AW(AW),.LANES(LANES),.LANE(lane),.P(P),.Q(Q)) diagnostic_read_pair (
            .data_q,.pairing_d,.orientation_q(orientation_tiles[lane/ORIENT_TILE_LANES].orientation_q),.u,.v
        );
        assign w=root_words[lane];
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
            root_words[lane] : active_scale;
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
        logic [31:0] bf_address,root_address;
        logic [KW-1:0] root_variable;
        genefer_ntt_rootfused_diag_bank_access_route #(.AW(AW),.LANES(LANES),.BANK(bank),.P(P),.Q(Q)) diagnostic_access (
            .active_op,.active_root_base,.base_addr,.bf0,.bf1,.bf_valid,.host_bank,.host_row,.host_write_mask,.host_write_words,.issue_fire,.load_we,.mul_lanes,.mul_valid,.n,.orientation,.orientation_pipe,.pairing,.point_base,.point_half,.point_half_pipe,.product,.read_en,.root_base,.root_base_bank,.root_mask,.root_shift,.rotation,.row_tag,.stage_toggle_mask,.start,.state,.vector_addr,.vector_base_bank,.vector_load_we,.vector_ok,.vector_request,.write_data,.data_re(data_re[bank]),.data_we(data_we[bank]),.root_re(root_re[bank]),.data_ra(data_ra[bank]),.data_wa(data_wa[bank]),.root_ra(root_ra[bank]),.data_w(data_w[bank]),.bf_address,.root_address,.root_variable
        );
        genefer_sdp_ram32 #(.AW(RW),.DEPTH(DEPTH)) data_ram (
            .clk,.rst_n,.read_en(data_re[bank]),.write_en(data_we[bank]),
            .read_addr(data_ra[bank]),.write_addr(data_wa[bank]),
            .write_data(data_w[bank]),.read_data(data_q[bank])
        );
        // synthesis translate_off
        always @(posedge clk) if(rst_n) begin
            if(data_we[bank] && data_w[bank]>=P) $fatal(1,"noncanonical NTT27 data write");
            if(data_re[bank] && data_we[bank] && data_ra[bank]==data_wa[bank]) $fatal(1,"bank-centric mixed-port RAM collision");
            if(state==BF_READ && issue_fire && root_re[bank] && (bank_of(AW'(root_address))!=KW'(bank) || root_address>=(n>>1)))
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
        if(state==BF_READ && issue_fire && root_read_count!=32'(stage_root_count))
            $fatal(1,"predecoded root count disagrees with physical ports");
        if(state==MUL_READ && issue_fire && root_read_count!=(active_op==2 ? mul_lanes : 0))
            $fatal(1,"pointwise root count disagrees with physical ports");
    end
    initial begin
        if(LANES<1 || LANES>64 || (LANES&(LANES-1))!=0) $fatal(1,"unsupported LANES");
        if(AW<1 || AW>16) $fatal(1,"unsupported AW");
    end
    // synthesis translate_on
    genefer_ntt_rootfused_diag_stage_phase_control #(.AW(AW),.LANES(LANES),.P(P),.Q(Q)) diagnostic_stage_phase_control (
        .base_bank,.bf_lanes,.bf_valid,.clk,.dif,.effective_mask,.fixed_mask_options,.fixed_source_options,.generator_done,.generator_error,.has_next_stage,.host_bank,.inverse,.issue_fire,.load_active,.load_contexts,.load_we,.mul_lanes,.mul_valid,.next_active,.next_contexts,.next_stage,.op,.orientation,.point_base,.point_half,.prefetch_matches,.profile_loaded,.profile_loaded_size,.profile_q,.read_en,.root_base_bank,.root_phase,.rst_n,.scale,.seed_loading,.setup_root_shift,.size_log2,.start,.vector_base_bank,.vector_load_we,.vector_ok,.vector_read_en,.vector_request,.active_dif,.active_inverse,.active_op,.active_root_base,.active_scale,.base_bank_d,.bf_in_valid,.busy,.butterflies,.completed,.cycles,.data_reads,.data_writes,.done,.error,.first_stage,.fixed_mask,.fixed_source,.group_index,.host_bank_d,.host_error,.issued_group_d,.lg,.low_stage_d,.mul_in_valid,.n,.orientation_pipe,.pairing,.pairing_d,.phase_reg,.point_bank_d,.point_half_d,.point_half_pipe,.prefetch_active,.prefetch_bank,.prefetch_contexts,.prefetch_key,.prefetch_lg,.prefetch_phase,.prefetch_stage,.prefetch_state,.prefetch_step,.profile_read_valid,.read_valid,.root_base_bank_d,.root_mask,.root_reads,.root_shift,.rotation,.rotation_d,.seed_bank_reg,.seed_issue,.seed_setup_cycles,.seed_step,.seed_tag,.stage_bit,.stage_bit_d,.stage_low,.stage_low_mask,.stage_root_count,.stage_toggle_mask,.state,.vector_base_bank_d,.vector_read_mask,.vector_read_valid,.wait_cycles
    );
endmodule

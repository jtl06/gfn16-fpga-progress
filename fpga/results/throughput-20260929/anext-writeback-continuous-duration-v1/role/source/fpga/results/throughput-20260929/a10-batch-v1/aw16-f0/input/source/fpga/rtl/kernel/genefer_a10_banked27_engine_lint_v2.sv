// SOURCE-ONLY additive A10 canonical fixed-ROM engine; G4 host/data geometry retained.
module genefer_a10_banked27_engine_v1 #(
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
    input logic profile_begin,profile_we,profile_commit,profile_abort,
    input logic [4:0] profile_size_log2,
    input logic [31:0] profile_modulus,profile_data,
    input logic [7:0] profile_format,
    input logic [15:0] profile_addr,
    output logic profile_loaded,profile_loading,profile_error,
    output logic [4:0] profile_loaded_size,
    output logic [15:0] profile_next_addr,
    output logic [63:0] seed_setup_cycles,root_rom_reads,normalization_products,
    output logic [31:0] profile_epoch,
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
    localparam int ISSUES=(1<<AW)>BANKS ? (1<<AW)/BANKS : 1;
    localparam int IW=ISSUES>1 ? $clog2(ISSUES) : 1;
    localparam int PROFILE_WORDS=4;
    typedef enum logic [2:0] {IDLE,STAGE_SETUP,BF_READ,BF_DRAIN,MUL_READ,MUL_DRAIN} state_t;
    state_t state;
    logic [31:0] n,group_index,completed,base_addr,point_base;
    logic [4:0] lg,stage_bit;
    logic [PW-1:0] pairing,pairing_d;
    logic [KW-1:0] base_bank,host_bank,host_bank_d,vector_base_bank,vector_base_bank_d;
    logic [RW-1:0] host_row;
    logic orientation,orientation_d,point_half,point_half_d;
    logic [7:0] orientation_pipe;
    logic [6:0] point_half_pipe;
    logic [1:0] active_op;
    logic active_inverse,descending;
    logic [31:0] bf_lanes,mul_lanes,stage_toggle_mask,stage_root_count;
    logic [AW-1:0] fixed_mask,fixed_mask_options[0:AW-1];
    logic [SIW-1:0] fixed_source[0:AW-1],fixed_source_options[0:AW-1][0:AW-1];
    logic vector_request,vector_ok,profile_request,issue_fire,bf_read_delay;
    logic [31:0] host_n,normalization,profile_psi,expected_header;
    logic [LANES-1:0] effective_mask;
    logic [BANKS-1:0] data_re,data_we;
    logic [RW-1:0] data_ra[0:BANKS-1],data_wa[0:BANKS-1];
    logic [31:0] data_w[0:BANKS-1],data_q[0:BANKS-1],data_destination[0:BANKS-1];
    logic [RW-1:0] row_tag[0:7][0:BANKS-1];
    logic [LANES-1:0] bf_in_valid,mul_in_valid,bf_valid,mul_valid,arith_error;
    logic [31:0] bf0[0:LANES-1],bf1[0:LANES-1],product[0:LANES-1];
    logic lookup_ready,lookup_valid,lookup_error;
    logic [LANES*27-1:0] lookup_roots;
    logic [31:0] lookup_tag,issue_tag_d,issue_tag_destination;
    assign profile_request=profile_begin || profile_we || profile_commit || profile_abort;
    assign issue_fire=(state==BF_READ && lookup_ready) || state==MUL_READ;
    assign seed_setup_cycles=64'd0;
    genefer_a10_profile3_constants_v1 #(.AW(AW),.P(P)) profile_constants (
        .address(profile_addr),.word(expected_header),.normalization,.psi(profile_psi)
    );
    // Every begin attempt/abort invalidates cache eligibility and advances epoch.
    // Any malformed transaction abandons the partial header. Reset aborts work.
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            profile_loaded<=0;profile_loading<=0;profile_error<=0;
            profile_loaded_size<=0;profile_next_addr<=0;profile_epoch<=0;
        end else begin
            profile_error<=0;
            if(profile_begin || profile_abort)begin
                profile_loaded<=0;profile_loading<=0;profile_loaded_size<=0;profile_next_addr<=0;
                profile_epoch<=profile_epoch+1;
            end
            if(profile_request)begin
                if(state!=IDLE || start ||
                   (int'(profile_begin)+int'(profile_we)+int'(profile_commit)+int'(profile_abort))!=1)begin
                    profile_error<=1;profile_loaded<=0;profile_loading<=0;
                end else if(profile_abort)begin end
                else if(profile_begin)begin
                    if(profile_size_log2!=5'(AW) || profile_modulus!=P || profile_format!=8'd3)
                        profile_error<=1;
                    else profile_loading<=1;
                end else if(profile_we)begin
                    if(profile_loading && profile_addr==profile_next_addr &&
                       int'(profile_addr)<PROFILE_WORDS && profile_data==expected_header)
                        profile_next_addr<=profile_next_addr+1;
                    else begin profile_error<=1;profile_loaded<=0;profile_loading<=0;end
                end else if(profile_commit)begin
                    if(profile_loading && profile_next_addr==16'(PROFILE_WORDS))begin
                        profile_loaded<=1;profile_loading<=0;profile_loaded_size<=5'(AW);
                    end else begin profile_error<=1;profile_loaded<=0;profile_loading<=0;end
                end
            end
        end
    end
    genefer_a10_packed_root_lookup_bound_v1 #(.AW(AW),.LANES(LANES),.P(P)) roots (
        .clk,.rst_n,.request_valid(state==BF_READ && issue_fire),.inverse(active_inverse),
        .stage(stage_bit),.issue_index(IW'(group_index)),.request_tag(group_index),
        .request_ready(lookup_ready),.out_valid(lookup_valid),.out_error(lookup_error),
        .out_tag(lookup_tag),.roots(lookup_roots)
    );
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
    assign read_data=data_q[host_bank_d];
    assign bf_lanes=(n>>1)<LANES ? n>>1 : LANES;
    assign mul_lanes=n<LANES ? n : LANES;
    assign base_bank=bank_of(AW'(base_addr));
    assign orientation=base_bank[pairing];
    assign point_base=group_index<<LW;
    assign point_half=(bank_of(AW'(point_base))&KW'(1<<LW))!=0;
    always_comb begin : fixed_address_bits
        base_addr=0;
        for(int j=0;j<AW;j=j+1)
            base_addr[j]=fixed_mask[j] ? group_index[5'(fixed_source[j])] : 1'b0;
    end
    // Root ROM q and bank RAM q are launched at E0 and registered together E1.
    // The existing eight-lane orientation fanout boundaries are retained E1.
    localparam int ORIENT_TILE_LANES=8,ORIENT_TILES=(LANES+ORIENT_TILE_LANES-1)/ORIENT_TILE_LANES;
    for(genvar tile=0;tile<ORIENT_TILES;tile=tile+1)begin: orientation_tiles
        (* preserve,dont_merge *) logic orientation_q;
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)orientation_q<=0;
            else if(bf_read_delay)orientation_q<=orientation_d;
        end
    end
    for(genvar lane=0;lane<LANES;lane=lane+1)begin: arithmetic
        logic [31:0] data_lo[0:KW-1],data_hi[0:KW-1];
        logic [31:0] u,v,w,mul_lhs;
        logic shared_valid;
        logic [5:0] point_type_pipe;
        for(genvar p=0;p<KW;p=p+1)begin: pair_patterns
            localparam int LO=insert_zero(lane,p),HI=LO|(1<<p);
            assign data_lo[p]=data_destination[LO];assign data_hi[p]=data_destination[HI];
        end
        assign u=orientation_tiles[lane/ORIENT_TILE_LANES].orientation_q ? data_hi[pairing_d] : data_lo[pairing_d];
        assign v=orientation_tiles[lane/ORIENT_TILE_LANES].orientation_q ? data_lo[pairing_d] : data_hi[pairing_d];
        assign w={5'd0,lookup_roots[lane*27+:27]};
        assign mul_lhs=point_half_d ? data_q[lane+LANES] : data_q[lane];
        genefer_a10_canonical_butterfly_v1 #(.P(P),.Q(Q)) butterfly (
            .clk,.rst_n,.in_valid(bf_in_valid[lane] || mul_in_valid[lane]),
            .gs(bf_in_valid[lane] && active_inverse),
            .normalize_upper(bf_in_valid[lane] && active_inverse && stage_bit==5'(AW-1)),
            .u(bf_in_valid[lane] ? u : 32'd0),
            .v(bf_in_valid[lane] ? v : mul_lhs),
            .w(bf_in_valid[lane] ? w : mul_lhs),.normalization(normalization),
            .out_valid(shared_valid),.out_error(arith_error[lane]),.y0(bf0[lane]),.y1(bf1[lane])
        );
        assign bf_valid[lane]=shared_valid && !point_type_pipe[5];
        assign mul_valid[lane]=shared_valid && point_type_pipe[5];
        assign product[lane]=bf0[lane];
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)point_type_pipe<=0;
            else point_type_pipe<={point_type_pipe[4:0],mul_in_valid[lane]};
        end
    end
    for(genvar bank=0;bank<BANKS;bank=bank+1)begin: memories
        logic [31:0] bf_write_option[0:KW-1];
        logic [KW-1:0] bf_valid_option;
        logic [31:0] bf_address;
        for(genvar p=0;p<KW;p=p+1)begin: write_patterns
            localparam int LANE=remove_bit(bank,p);
            assign bf_write_option[p]=(orientation_pipe[7]==1'((bank>>p)&1)) ? bf0[LANE] : bf1[LANE];
            assign bf_valid_option[p]=bf_valid[LANE];
        end
        assign bf_address=base_addr|((1'(bank>>pairing)^orientation) ? stage_toggle_mask : 32'd0);
        always_comb begin
            data_re[bank]=0;data_we[bank]=0;
            data_ra[bank]=0;data_wa[bank]=0;data_w[bank]=0;
            if(state==IDLE && !start && !profile_request)begin
                if(vector_request)begin
                    if(vector_ok && 1'(bank/LANES)==vector_base_bank[LW] && vector_write_route[LW].mask[bank%LANES])begin
                        data_we[bank]=vector_load_we;data_re[bank]=!vector_load_we;
                        data_wa[bank]=RW'(vector_addr>>KW);data_ra[bank]=RW'(vector_addr>>KW);
                        data_w[bank]=vector_write_route[LW].words[bank%LANES];
                    end
                end else if(host_bank==KW'(bank))begin
                    if(load_we)begin data_we[bank]=1;data_wa[bank]=host_row;data_w[bank]=write_data;end
                    else if(read_en)begin data_re[bank]=1;data_ra[bank]=host_row;end
                end
            end
            if(state==BF_READ && issue_fire)begin
                data_re[bank]=32'(bank)<n;data_ra[bank]=RW'(bf_address>>KW);
            end
            if(state==MUL_READ && issue_fire && 1'(bank/LANES)==point_half && 32'(bank%LANES)<mul_lanes)begin
                data_re[bank]=1;data_ra[bank]=RW'(point_base>>KW);
            end
            if((state==BF_READ || state==BF_DRAIN) && bf_valid_option[pairing] && 32'(bank)<n)begin
                data_we[bank]=1;data_wa[bank]=row_tag[7][bank];data_w[bank]=bf_write_option[pairing];
            end
            if((state==MUL_READ || state==MUL_DRAIN) && mul_valid[bank%LANES] && 1'(bank/LANES)==point_half_pipe[6])begin
                data_we[bank]=1;data_wa[bank]=row_tag[6][bank];data_w[bank]=product[bank%LANES];
            end
        end
        genefer_sdp_ram32 #(.AW(RW),.DEPTH(DEPTH)) data_ram (
            .clk,.rst_n,.read_en(data_re[bank]),.write_en(data_we[bank]),
            .read_addr(data_ra[bank]),.write_addr(data_wa[bank]),
            .write_data(data_w[bank]),.read_data(data_q[bank])
        );
        always_ff @(posedge clk)if(rst_n && bf_read_delay)data_destination[bank]<=data_q[bank];
        // synthesis translate_off
        always @(posedge clk)if(rst_n)begin
            if(data_we[bank] && data_w[bank]>=P)$fatal(1,"A10_NONCANONICAL_WRITE");
            if(data_re[bank] && data_we[bank] && data_ra[bank]==data_wa[bank])$fatal(1,"A10_RAM_COLLISION");
        end
        // synthesis translate_on
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;busy<=0;done<=0;error<=0;read_valid<=0;
            vector_read_valid<=0;vector_read_mask<=0;host_error<=0;vector_base_bank_d<=0;
            n<=0;group_index<=0;completed<=0;lg<=0;stage_bit<=0;
            pairing<=0;pairing_d<=0;stage_root_count<=0;stage_toggle_mask<=0;fixed_mask<=0;
            for(int j=0;j<AW;j=j+1)fixed_source[j]<=0;
            orientation_d<=0;orientation_pipe<=0;point_half_d<=0;point_half_pipe<=0;
            active_op<=0;active_inverse<=0;descending<=0;host_bank_d<=0;
            bf_read_delay<=0;bf_in_valid<=0;mul_in_valid<=0;issue_tag_d<=0;issue_tag_destination<=0;
            cycles<=0;butterflies<=0;data_reads<=0;data_writes<=0;root_reads<=0;wait_cycles<=0;
            root_rom_reads<=0;normalization_products<=0;
            for(int t=0;t<8;t=t+1)for(int b=0;b<BANKS;b=b+1)row_tag[t][b]<=0;
        end else begin
            done<=0;
            read_valid<=state==IDLE && !start && !profile_request && !vector_request && read_en && !load_we;
            vector_read_valid<=state==IDLE && !start && !profile_request && vector_read_en && !vector_load_we && vector_ok;
            vector_read_mask<=state==IDLE && !start && !profile_request && vector_read_en && !vector_load_we && vector_ok ? effective_mask : '0;
            host_error<=state==IDLE && !start && !profile_request && vector_request && !vector_ok;
            if(state==IDLE && !start && !profile_request && vector_read_en && !vector_load_we && vector_ok)
                vector_base_bank_d<=vector_base_bank;
            if(state==IDLE)host_bank_d<=host_bank;
            pairing_d<=pairing;point_half_d<=point_half;orientation_d<=orientation;
            orientation_pipe<={orientation_pipe[6:0],orientation};
            point_half_pipe<={point_half_pipe[5:0],point_half};
            bf_read_delay<=state==BF_READ && issue_fire;
            if(state==BF_READ && issue_fire)issue_tag_d<=group_index;
            if(bf_read_delay)issue_tag_destination<=issue_tag_d;
            for(int b=0;b<BANKS;b=b+1)begin
                row_tag[0][b]<=data_ra[b];
                for(int t=1;t<8;t=t+1)row_tag[t][b]<=row_tag[t-1][b];
            end
            for(int lane=0;lane<LANES;lane=lane+1)begin
                bf_in_valid[lane]<=bf_read_delay && 32'(lane)<bf_lanes;
                mul_in_valid[lane]<=state==MUL_READ && issue_fire && 32'(lane)<mul_lanes;
            end
            if(busy)cycles<=cycles+1;
            if(state==BF_READ && issue_fire)begin
                data_reads<=data_reads+64'(2*bf_lanes);root_reads<=root_reads+64'(stage_root_count);
                // Depth1 constants require no ROM read; other stages one wide read.
                if((int'(stage_bit)<KW && ISSUES>1) ||
                   (int'(stage_bit)>=KW && int'(stage_bit)<AW-1))root_rom_reads<=root_rom_reads+1;
            end
            if(state==MUL_READ && issue_fire)data_reads<=data_reads+64'(mul_lanes);
            if(state==BF_DRAIN || state==MUL_DRAIN)wait_cycles<=wait_cycles+1;
            if((state==BF_READ || state==BF_DRAIN) && bf_valid[0])begin
                butterflies<=butterflies+64'(bf_lanes);data_writes<=data_writes+64'(2*bf_lanes);completed<=completed+bf_lanes;
                if(active_inverse && stage_bit==5'(AW-1))normalization_products<=normalization_products+64'(bf_lanes);
                if(completed+bf_lanes==(n>>1))begin
                    completed<=0;group_index<=0;
                    if((descending && stage_bit==0) || (!descending && stage_bit==lg-1))begin
                        busy<=0;done<=1;state<=IDLE;
                    end else begin stage_bit<=descending ? stage_bit-1 : stage_bit+1;state<=STAGE_SETUP;end
                end
            end
            if((state==MUL_READ || state==MUL_DRAIN) && mul_valid[0])begin
                data_writes<=data_writes+64'(mul_lanes);completed<=completed+mul_lanes;
                if(completed+mul_lanes==n)begin busy<=0;done<=1;state<=IDLE;end
            end
            case(state)
                IDLE:if(start)begin
                    error<=0;cycles<=0;butterflies<=0;data_reads<=0;data_writes<=0;root_reads<=0;wait_cycles<=0;
                    root_rom_reads<=0;normalization_products<=0;
                    if(size_log2!=5'(AW) || (op!=0 && op!=1) || scale!=0 ||
                       (op==0 && (dif!=inverse || root_phase!=(inverse ? 2'd2 : 2'd1))) ||
                       (op==1 && (inverse || root_phase!=0)) ||
                       !profile_loaded || profile_loading || profile_error || profile_request ||
                       profile_loaded_size!=5'(AW) || profile_next_addr!=16'(PROFILE_WORDS) ||
                       load_we || read_en || vector_request || read_valid || vector_read_valid)begin error<=1;done<=1;end
                    else begin
                        n<=32'd1<<AW;lg<=5'(AW);group_index<=0;completed<=0;
                        active_op<=op;active_inverse<=inverse;descending<=!inverse;
                        stage_bit<=inverse ? 5'd0 : 5'(AW-1);busy<=1;state<=op==0 ? STAGE_SETUP : MUL_READ;
                    end
                end
                STAGE_SETUP:begin
                    pairing<=PW'(int'(stage_bit)%KW);
                    stage_toggle_mask<=32'd1<<stage_bit;
                    // Merged group roots depend on upper bits, not low cyclic period.
                    stage_root_count<=32'(1<<((AW<KW ? AW : KW)>int'(stage_bit)+1 ?
                        (AW<KW ? AW : KW)-int'(stage_bit)-1 : 0));
                    fixed_mask<=fixed_mask_options[SIW'(stage_bit)];
                    for(int j=0;j<AW;j=j+1)fixed_source[j]<=fixed_source_options[j][SIW'(stage_bit)];
                    state<=BF_READ;
                end
                BF_READ:if(issue_fire)begin if(((group_index+1)<<KW)>=n)state<=BF_DRAIN;else group_index<=group_index+1;end
                MUL_READ:if(issue_fire)begin if(((group_index+1)<<LW)>=n)state<=MUL_DRAIN;else group_index<=group_index+1;end
                default:;
            endcase
            // A profile abort/change or pipeline fault quarantines the data image.
            // Pending outputs cannot commit after state leaves READ/DRAIN; reload.
            if(busy && (profile_request || profile_error || lookup_error || (|arith_error)))begin
                state<=IDLE;busy<=0;done<=1;error<=1;
            end
        end
    end
    // synthesis translate_off
    initial begin
        if(AW<1 || AW>16 || LANES!=64)$fatal(1,"A10_ENGINE_GEOMETRY");
        if(32'(64'(P)*64'(Q))!=1)$fatal(1,"A10_ENGINE_FIELD_INVERSE");
    end
    always @(posedge clk)if(rst_n)begin
        if(bf_in_valid[0] && (!lookup_valid || lookup_tag!=issue_tag_destination))
            $fatal(1,"A10_ROOT_DATA_TAG_ALIGNMENT");
        for(int j=0;j<LANES;j=j+1)if(bf_in_valid[j] && mul_in_valid[j])$fatal(1,"A10_SHARED_ARITH_COLLISION");
    end
    // synthesis translate_on
endmodule


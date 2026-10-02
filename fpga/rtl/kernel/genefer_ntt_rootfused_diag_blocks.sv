// A5 diagnostic hierarchy only; literal frozen bodies, no new attributes.

package genefer_ntt_rootfused_diag_types;
    typedef enum logic [3:0] {IDLE,STAGE_SETUP,ROOT_CLEAR,ROOT_LOAD,ROOT_START,BF_READ,BF_DRAIN,MUL_READ,MUL_DRAIN,ROOT_WAIT} state_t;
    typedef enum logic [1:0] {PF_IDLE,PF_CLEAR,PF_LOAD,PF_READY} prefetch_t;
endpackage

module genefer_ntt_rootfused_diag_host_write_route #(parameter int AW=16,LANES=64,LANE=0,BANK=0,
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697) (
    input logic [KW-1:0] vector_base_bank,
    input logic [LANES*32-1:0] vector_write_data,
    input logic [LANES-1:0] effective_mask,
    output logic [31:0] host_write_words [0:LANES-1],
    output logic [LANES-1:0] host_write_mask
);
    import genefer_ntt_rootfused_diag_types::*;
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
    for(genvar h=0;h<LANES;h=h+1)begin
        assign host_write_words[h]=vector_write_route[LW].words[h];
        assign host_write_mask[h]=vector_write_route[LW].mask[h];
    end
endmodule

module genefer_ntt_rootfused_diag_host_read_route #(parameter int AW=16,LANES=64,LANE=0,BANK=0,
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697) (
    input logic [KW-1:0] vector_base_bank_d,
    input logic [31:0] data_q [0:BANKS-1],
    output logic [31:0] host_read_words [0:LANES-1]
);
    import genefer_ntt_rootfused_diag_types::*;
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
    for(genvar d=0;d<=LW;d=d+1) begin : vector_read_route
        logic [31:0] words [0:LANES-1];
        for(genvar h=0;h<LANES;h=h+1) begin : lanes
            if(d==0) assign words[h]=vector_base_bank_d[LW] ? data_q[h+LANES] : data_q[h];
            else assign words[h]=vector_base_bank_d[d-1] ? vector_read_route[d-1].words[h^(1<<(d-1))] : vector_read_route[d-1].words[h];
        end
    end
    for(genvar h=0;h<LANES;h=h+1)begin
        assign host_read_words[h]=vector_read_route[LW].words[h];
    end
endmodule

module genefer_ntt_rootfused_diag_root_clip_route #(parameter int AW=16,LANES=64,LANE=0,BANK=0,
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697) (
    input logic [1:0] active_op,
    input logic low_stage_d,
    input logic [4:0] stage_bit_d,
    input logic [KW-1:0] base_bank_d,
    input logic [PW-1:0] pairing_d,
    input logic [LW:0] point_bank_d,
    input logic [LANES*32-1:0] generated_roots,
    output logic [31:0] root_words [0:LANES-1]
);
    import genefer_ntt_rootfused_diag_types::*;
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
    function automatic int remove_bit(input int a,p);
        remove_bit=(a&((1<<p)-1))|((a>>(p+1))<<p);
    endfunction
    logic [KW-1:0] route_xor,root_lane_mask;
    assign root_lane_mask=(active_op==0 && low_stage_d) ?
        KW'((32'd1<<stage_bit_d)-32'd1) : {KW{1'b1}};
    assign route_xor=active_op==0 ? (low_stage_d ? base_bank_d :
        KW'(remove_bit(int'(base_bank_d),int'(pairing_d)))) : KW'(point_bank_d);
    for(genvar d=0;d<=LW;d=d+1)begin: generated_route
        logic [31:0] words[0:LANES-1];
        for(genvar j=0;j<LANES;j=j+1)begin: lanes
            if(d==0)assign words[j]=generated_roots[j*32+:32];
            else begin : fused_clip_xor
                logic select_neighbor;
                if((j&(1<<(d-1)))==0)
                    assign select_neighbor=root_lane_mask[d-1] & route_xor[d-1];
                else
                    assign select_neighbor=~root_lane_mask[d-1] | route_xor[d-1];
                assign words[j]=select_neighbor ? generated_route[d-1].words[j^(1<<(d-1))] :
                                                 generated_route[d-1].words[j];
            end
        end
    end
    for(genvar j=0;j<LANES;j=j+1)assign root_words[j]=generated_route[LW].words[j];
endmodule

module genefer_ntt_rootfused_diag_butterfly_read_route #(parameter int AW=16,LANES=64,LANE=0,BANK=0,
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697) (
    input logic [31:0] data_q [0:BANKS-1],
    input logic [PW-1:0] pairing_d,
    input logic orientation_q,
    output logic [31:0] u,
    output logic [31:0] v
);
    import genefer_ntt_rootfused_diag_types::*;
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
    function automatic int insert_zero(input int a,p);
        insert_zero=(a&((1<<p)-1))|((a>>p)<<(p+1));
    endfunction
        logic [31:0] data_lo [0:KW-1],data_hi [0:KW-1];
        for(genvar p=0;p<KW;p=p+1) begin : pair_patterns
            localparam int LO=insert_zero(LANE,p),HI=LO|(1<<p);
            assign data_lo[p]=data_q[LO];assign data_hi[p]=data_q[HI];
        end
        assign u=orientation_q ? data_hi[pairing_d] : data_lo[pairing_d];
        assign v=orientation_q ? data_lo[pairing_d] : data_hi[pairing_d];
endmodule

module genefer_ntt_rootfused_diag_bank_access_route #(parameter int AW=16,LANES=64,LANE=0,BANK=0,
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697) (
    input logic [1:0] active_op,
    input logic [RRW-1:0] active_root_base,
    input logic [31:0] base_addr,
    input logic [31:0] bf0 [0:LANES-1],
    input logic [31:0] bf1 [0:LANES-1],
    input logic [LANES-1:0] bf_valid,
    input logic [KW-1:0] host_bank,
    input logic [RW-1:0] host_row,
    input logic [LANES-1:0] host_write_mask,
    input logic [31:0] host_write_words [0:LANES-1],
    input logic issue_fire,
    input logic load_we,
    input logic [31:0] mul_lanes,
    input logic [LANES-1:0] mul_valid,
    input logic [31:0] n,
    input logic orientation,
    input logic [6:0] orientation_pipe,
    input logic [PW-1:0] pairing,
    input logic [31:0] point_base,
    input logic point_half,
    input logic [6:0] point_half_pipe,
    input logic [31:0] product [0:LANES-1],
    input logic read_en,
    input logic [31:0] root_base,
    input logic [KW-1:0] root_base_bank,
    input logic [KW-1:0] root_mask,
    input logic [4:0] root_shift,
    input logic [PW-1:0] rotation,
    input logic [RW-1:0] row_tag [0:6][0:BANKS-1],
    input logic [31:0] stage_toggle_mask,
    input logic start,
    input genefer_ntt_rootfused_diag_types::state_t state,
    input logic [AW-1:0] vector_addr,
    input logic [KW-1:0] vector_base_bank,
    input logic vector_load_we,
    input logic vector_ok,
    input logic vector_request,
    input logic [31:0] write_data,
    output logic data_re,
    output logic data_we,
    output logic root_re,
    output logic [RW-1:0] data_ra,
    output logic [RW-1:0] data_wa,
    output logic [RRW-1:0] root_ra,
    output logic [31:0] data_w,
    output logic [31:0] bf_address,
    output logic [31:0] root_address,
    output logic [KW-1:0] root_variable
);
    import genefer_ntt_rootfused_diag_types::*;
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
    function automatic int remove_bit(input int a,p);
        remove_bit=(a&((1<<p)-1))|((a>>(p+1))<<p);
    endfunction
    function automatic logic [KW-1:0] ror(input logic [KW-1:0] b,input logic [PW-1:0] r);
        ror=(b>>r)|(b<<(KW-int'(r)));
    endfunction
        logic [31:0] bf_write_option [0:KW-1];
        logic [KW-1:0] bf_valid_option;
        for(genvar p=0;p<KW;p=p+1) begin : write_patterns
            localparam int LANE=remove_bit(BANK,p);
            assign bf_write_option[p]=(orientation_pipe[6]==1'((BANK>>p)&1)) ? bf0[LANE] : bf1[LANE];
            assign bf_valid_option[p]=bf_valid[LANE];
        end
        assign bf_address=base_addr|((1'(BANK>>pairing)^orientation) ? stage_toggle_mask : 32'd0);
        assign root_variable=ror(KW'(BANK)^root_base_bank,rotation);
        assign root_address=root_base|(32'(root_variable)<<root_shift);
        always_comb begin
            data_re=0;data_we=0;root_re=0;
            data_ra=0;data_wa=0;root_ra=0;data_w=0;
            if(state==IDLE && !start) begin
                if(vector_request) begin
                    if(vector_ok && 1'(BANK/LANES)==vector_base_bank[LW] && host_write_mask[BANK%LANES]) begin
                        data_we=vector_load_we;data_re=!vector_load_we;
                        data_wa=RW'(vector_addr>>KW);data_ra=RW'(vector_addr>>KW);
                        data_w=host_write_words[BANK%LANES];
                    end
                end else if(host_bank==KW'(BANK)) begin
                    if(load_we) begin data_we=1;data_wa=host_row;data_w=write_data;end
                    else if(read_en) begin data_re=1;data_ra=host_row;end
                end
            end
            if(state==BF_READ && issue_fire) begin
                data_re=32'(BANK)<n;data_ra=RW'(bf_address>>KW);
                root_re=(root_variable&~root_mask)==0;
                root_ra=active_root_base+RRW'(root_address>>KW);
            end
            if(state==MUL_READ && issue_fire && 1'(BANK/LANES)==point_half && 32'(BANK%LANES)<mul_lanes) begin
                data_re=1;data_ra=RW'(point_base>>KW);
                root_re=active_op==2;root_ra=active_root_base+RRW'(point_base>>KW);
            end
            if((state==BF_READ || state==BF_DRAIN) && bf_valid_option[pairing] && 32'(BANK)<n) begin
                data_we=1;data_wa=row_tag[6][BANK];data_w=bf_write_option[pairing];
            end
            if((state==MUL_READ || state==MUL_DRAIN) && mul_valid[BANK%LANES] && 1'(BANK/LANES)==point_half_pipe[6]) begin
                data_we=1;data_wa=row_tag[6][BANK];data_w=product[BANK%LANES];
            end
        end
endmodule

module genefer_ntt_rootfused_diag_row_tag_pipeline #(parameter int AW=16,LANES=64,LANE=0,BANK=0,
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697) (
    input logic clk,
    input logic rst_n,
    input logic [RW-1:0] data_ra [0:BANKS-1],
    output logic [RW-1:0] row_tag [0:6][0:BANKS-1]
);
    import genefer_ntt_rootfused_diag_types::*;
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
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            for(int t=0;t<7;t=t+1) for(int b=0;b<BANKS;b=b+1) row_tag[t][b]<=0;
        end else begin
            for(int b=0;b<BANKS;b=b+1) begin
                row_tag[0][b]<=data_ra[b];
                for(int t=1;t<7;t=t+1) row_tag[t][b]<=row_tag[t-1][b];
            end
        end
    end
endmodule

module genefer_ntt_rootfused_diag_stage_phase_control #(parameter int AW=16,LANES=64,LANE=0,BANK=0,
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697) (
    input logic [KW-1:0] base_bank,
    input logic [31:0] bf_lanes,
    input logic [LANES-1:0] bf_valid,
    input logic clk,
    input logic dif,
    input logic [LANES-1:0] effective_mask,
    input logic [AW-1:0] fixed_mask_options [0:AW-1],
    input logic [SIW-1:0] fixed_source_options [0:AW-1][0:AW-1],
    input logic generator_done,
    input logic generator_error,
    input logic has_next_stage,
    input logic [KW-1:0] host_bank,
    input logic inverse,
    input logic issue_fire,
    input logic [6:0] load_active,
    input logic [2:0] load_contexts,
    input logic load_we,
    input logic [31:0] mul_lanes,
    input logic [LANES-1:0] mul_valid,
    input logic [6:0] next_active,
    input logic [2:0] next_contexts,
    input logic [4:0] next_stage,
    input logic [1:0] op,
    input logic orientation,
    input logic [31:0] point_base,
    input logic point_half,
    input logic prefetch_matches,
    input logic profile_loaded,
    input logic [4:0] profile_loaded_size,
    input logic [31:0] profile_q,
    input logic read_en,
    input logic [KW-1:0] root_base_bank,
    input logic [1:0] root_phase,
    input logic rst_n,
    input logic [31:0] scale,
    input logic seed_loading,
    input logic [4:0] setup_root_shift,
    input logic [4:0] size_log2,
    input logic start,
    input logic [KW-1:0] vector_base_bank,
    input logic vector_load_we,
    input logic vector_ok,
    input logic vector_read_en,
    input logic vector_request,
    output logic active_dif,
    output logic active_inverse,
    output logic [1:0] active_op,
    output logic [RRW-1:0] active_root_base,
    output logic [31:0] active_scale,
    output logic [KW-1:0] base_bank_d,
    output logic [LANES-1:0] bf_in_valid,
    output logic busy,
    output logic [63:0] butterflies,
    output logic [31:0] completed,
    output logic [63:0] cycles,
    output logic [63:0] data_reads,
    output logic [63:0] data_writes,
    output logic done,
    output logic error,
    output logic first_stage,
    output logic [AW-1:0] fixed_mask,
    output logic [SIW-1:0] fixed_source [0:AW-1],
    output logic [31:0] group_index,
    output logic [KW-1:0] host_bank_d,
    output logic host_error,
    output logic [31:0] issued_group_d,
    output logic [4:0] lg,
    output logic low_stage_d,
    output logic [LANES-1:0] mul_in_valid,
    output logic [31:0] n,
    output logic [6:0] orientation_pipe,
    output logic [PW-1:0] pairing,
    output logic [PW-1:0] pairing_d,
    output logic [1:0] phase_reg,
    output logic [LW:0] point_bank_d,
    output logic point_half_d,
    output logic [6:0] point_half_pipe,
    output logic [6:0] prefetch_active,
    output logic prefetch_bank,
    output logic [2:0] prefetch_contexts,
    output logic [31:0] prefetch_key,
    output logic [4:0] prefetch_lg,
    output logic [1:0] prefetch_phase,
    output logic [4:0] prefetch_stage,
    output genefer_ntt_rootfused_diag_types::prefetch_t prefetch_state,
    output logic [31:0] prefetch_step,
    output logic profile_read_valid,
    output logic read_valid,
    output logic [KW-1:0] root_base_bank_d,
    output logic [KW-1:0] root_mask,
    output logic [63:0] root_reads,
    output logic [4:0] root_shift,
    output logic [PW-1:0] rotation,
    output logic [PW-1:0] rotation_d,
    output logic seed_bank_reg,
    output logic [8:0] seed_issue,
    output logic [63:0] seed_setup_cycles,
    output logic [31:0] seed_step,
    output logic [8:0] seed_tag,
    output logic [4:0] stage_bit,
    output logic [4:0] stage_bit_d,
    output logic stage_low,
    output logic [31:0] stage_low_mask,
    output logic [KW-1:0] stage_root_count,
    output logic [31:0] stage_toggle_mask,
    output genefer_ntt_rootfused_diag_types::state_t state,
    output logic [KW-1:0] vector_base_bank_d,
    output logic [LANES-1:0] vector_read_mask,
    output logic vector_read_valid,
    output logic [63:0] wait_cycles
);
    import genefer_ntt_rootfused_diag_types::*;
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
    function automatic logic [KW-1:0] bank_of(input logic [AW-1:0] a);
        logic [KW-1:0] b;
        begin b=0;for(int j=0;j<AW;j=j+1) b[j%KW]=b[j%KW]^a[j];bank_of=b;end
    endfunction
    function automatic logic [RRW-1:0] phase_base(input logic [1:0] phase_id);
        case(phase_id)
            0: phase_base=0;
            1: phase_base=RRW'(DEPTH);
            2: phase_base=RRW'(DEPTH+HALF_DEPTH);
            default: phase_base=RRW'(DEPTH+2*HALF_DEPTH);
        endcase
    endfunction
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE;busy<=0;done<=0;error<=0;read_valid<=0;
            vector_read_valid<=0;vector_read_mask<=0;host_error<=0;vector_base_bank_d<=0;
            n<=0;group_index<=0;completed<=0;lg<=0;stage_bit<=0;stage_bit_d<=0;
            pairing_d<=0;rotation_d<=0;base_bank_d<=0;root_base_bank_d<=0;
            pairing<=0;rotation<=0;root_shift<=0;root_mask<=0;stage_root_count<=0;stage_low<=0;
            stage_toggle_mask<=0;stage_low_mask<=0;fixed_mask<=0;
            for(int j=0;j<AW;j=j+1) fixed_source[j]<=0;
            point_half_d<=0;low_stage_d<=0;orientation_pipe<=0;point_half_pipe<=0;
            active_op<=0;active_inverse<=0;active_dif<=0;active_scale<=0;host_bank_d<=0;active_root_base<=0;
            phase_reg<=0;seed_bank_reg<=0;seed_issue<=0;seed_tag<=0;profile_read_valid<=0;
            seed_step<=0;point_bank_d<=0;seed_setup_cycles<=0;issued_group_d<=0;
            prefetch_state<=PF_IDLE;first_stage<=1;prefetch_bank<=0;prefetch_stage<=0;
            prefetch_lg<=0;prefetch_phase<=0;prefetch_key<=0;prefetch_step<=0;
            prefetch_active<=0;prefetch_contexts<=0;
            bf_in_valid<=0;mul_in_valid<=0;
            cycles<=0;butterflies<=0;data_reads<=0;data_writes<=0;root_reads<=0;wait_cycles<=0;
        end else begin
            profile_read_valid<=seed_loading && int'(seed_issue)<SEED_WORDS;
            seed_tag<=seed_issue;
            if(issue_fire)issued_group_d<=group_index;
            point_bank_d<=bank_of(AW'(point_base));
            if(busy && (state==ROOT_CLEAR || state==ROOT_LOAD || state==ROOT_START || state==ROOT_WAIT))
                seed_setup_cycles<=seed_setup_cycles+1;
            // The profile cannot change while busy. Background descriptor is captured
            // at ROOT_START and independent of current-stage metadata thereafter.
            if(prefetch_state==PF_CLEAR)begin seed_issue<=0;prefetch_state<=PF_LOAD;end
            if(seed_loading)begin
                if(int'(seed_issue)<SEED_WORDS)begin
                    if(int'(seed_issue)==4*LANES)seed_issue<=9'(SEED_WORDS);
                    else if((int'(seed_issue)&(LANES-1))+1<int'(load_active))seed_issue<=seed_issue+1;
                    else if((int'(seed_issue)>>LW)+1<int'(load_contexts))
                        seed_issue<=9'(((int'(seed_issue)>>LW)+1)<<LW);
                    else seed_issue<=9'(4*LANES);
                end
                if(profile_read_valid && int'(seed_tag)==4*LANES)begin
                    if(prefetch_state==PF_LOAD)begin prefetch_step<=profile_q;prefetch_state<=PF_READY;end
                    else begin seed_step<=profile_q;state<=ROOT_START;end
                end
            end
            done<=0;read_valid<=state==IDLE && !start && !vector_request && read_en && !load_we;
            vector_read_valid<=state==IDLE && !start && vector_read_en && !vector_load_we && vector_ok;
            vector_read_mask<=state==IDLE && !start && vector_read_en && !vector_load_we && vector_ok ? effective_mask : '0;
            host_error<=state==IDLE && !start && vector_request && !vector_ok;
            if(state==IDLE && !start && vector_read_en && !vector_load_we && vector_ok)
                vector_base_bank_d<=vector_base_bank;
            if(state==IDLE) host_bank_d<=host_bank;
            pairing_d<=pairing;rotation_d<=rotation;stage_bit_d<=stage_bit;
            base_bank_d<=base_bank;root_base_bank_d<=root_base_bank;
            point_half_d<=point_half;low_stage_d<=stage_low;
            orientation_pipe<={orientation_pipe[5:0],orientation};point_half_pipe<={point_half_pipe[5:0],point_half};
            for(int lane=0;lane<LANES;lane=lane+1) begin
                bf_in_valid[lane]<=state==BF_READ && issue_fire && 32'(lane)<bf_lanes;
                mul_in_valid[lane]<=state==MUL_READ && issue_fire && 32'(lane)<mul_lanes;
            end
            if(busy) cycles<=cycles+1;
            if(state==BF_READ && issue_fire) begin data_reads<=data_reads+64'(2*bf_lanes);root_reads<=root_reads+64'(stage_root_count);end
            if(state==MUL_READ && issue_fire) begin data_reads<=data_reads+64'(mul_lanes);root_reads<=root_reads+(active_op==2 ? 64'(mul_lanes) : 64'd0);end
            if(state==BF_DRAIN || state==MUL_DRAIN) wait_cycles<=wait_cycles+1;
            if((state==BF_READ || state==BF_DRAIN) && bf_valid[0]) begin
                butterflies<=butterflies+64'(bf_lanes);data_writes<=data_writes+64'(2*bf_lanes);completed<=completed+bf_lanes;
                if(completed+bf_lanes==(n>>1)) begin
                    completed<=0;group_index<=0;
                    if((active_dif && stage_bit==0) || (!active_dif && stage_bit==lg-1)) begin
                        if(active_inverse) state<=MUL_READ;else begin busy<=0;done<=1;state<=IDLE;end
                    end else begin stage_bit<=active_dif ? stage_bit-1 : stage_bit+1;seed_bank_reg<=!seed_bank_reg;state<=STAGE_SETUP;end
                end
            end
            if((state==MUL_READ || state==MUL_DRAIN) && mul_valid[0]) begin
                data_writes<=data_writes+64'(mul_lanes);completed<=completed+mul_lanes;
                if(completed+mul_lanes==n) begin busy<=0;done<=1;state<=IDLE;end
            end
            case(state)
                IDLE: if(start) begin
                    prefetch_state<=PF_IDLE;first_stage<=1;profile_read_valid<=0;
                    error<=0;cycles<=0;butterflies<=0;data_reads<=0;data_writes<=0;root_reads<=0;wait_cycles<=0;seed_setup_cycles<=0;
                    if(size_log2<1 || int'(size_log2)>AW ||
                       (op==0 && root_phase!=1 && root_phase!=2) ||
                       (op==2 && root_phase!=0 && root_phase!=3) ||
                       ((op==0 || op==2) && (!profile_loaded || profile_loaded_size!=size_log2)) ||
                       ((op==3 || (op==0 && inverse)) && scale>=P)) begin error<=1;done<=1;end
                    else begin
                        n<=32'd1<<size_log2;lg<=size_log2;group_index<=0;completed<=0;
                        active_op<=op;active_inverse<=inverse;active_dif<=dif;active_scale<=scale;active_root_base<=phase_base(root_phase);phase_reg<=root_phase;seed_bank_reg<=0;
                        stage_bit<=dif ? size_log2-1 : 0;busy<=1;state<=op==0 ? STAGE_SETUP : op==2 ? ROOT_CLEAR : MUL_READ;
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
                    if(first_stage)state<=ROOT_CLEAR;
                    else if(prefetch_state==PF_READY && prefetch_matches)begin
                        seed_step<=prefetch_step;prefetch_state<=PF_IDLE;state<=ROOT_START;
                    end else state<=ROOT_WAIT;
                end
                ROOT_WAIT:if(prefetch_state==PF_READY && prefetch_matches)begin
                    seed_step<=prefetch_step;prefetch_state<=PF_IDLE;state<=ROOT_START;
                end
                ROOT_CLEAR:begin seed_issue<=0;state<=ROOT_LOAD;end
                ROOT_START:begin
                    first_stage<=0;state<=active_op==0 ? BF_READ : MUL_READ;
                    if(has_next_stage)begin
                        prefetch_state<=PF_CLEAR;prefetch_bank<=!seed_bank_reg;
                        prefetch_stage<=next_stage;prefetch_lg<=lg;prefetch_phase<=phase_reg;
                        prefetch_key<=phase_reg==1 ? 1+32'(next_stage) : 1+32'(AW)+32'(next_stage);
                        prefetch_active<=next_active;prefetch_contexts<=next_contexts;
                    end
                end
                BF_READ: if(issue_fire)begin if(((group_index+1)<<KW)>=n) state<=BF_DRAIN;else group_index<=group_index+1;end
                MUL_READ: if(issue_fire)begin if(((group_index+1)<<LW)>=n) state<=MUL_DRAIN;else group_index<=group_index+1;end
                default: ;
            endcase
            if(busy && generator_done && generator_error)begin state<=IDLE;busy<=0;done<=1;error<=1;prefetch_state<=PF_IDLE;profile_read_valid<=0;end
        end
    end
endmodule

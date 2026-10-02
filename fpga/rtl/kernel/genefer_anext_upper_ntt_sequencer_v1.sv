// Additive isolated Track-A three-field sequencer; no CRT/carry or host image.
// A10 format3 three-phase cases are exact-delta guarded. New block-port A10
// engine retains canonical arithmetic. Caller owns ordinary-residue prefill.
// Start excludes every block request/pending response; cancel/failure quarantine
// reset eligibility/children, never RAM contents. Reload after cancel or error.
module genefer_anext_upper_ntt_sequencer_v1 #(parameter int AW=16) (
    input logic clk,rst_n,cancel,start_ntt,
    output logic ready,busy,done,error,profile_cache_valid,profile_coherent,
    output logic [63:0] cycles,ntt_cycles,root_cycles,seed_setup_cycles,
    output logic profile_loads,profile_hits,
    output logic [15:0] profile_words_loaded,
    input logic block_read_en,block_write_en,
    input logic [AW-1:0] block_read_offset,block_write_offset,
    input logic [15:0] block_read_mask,block_write_mask,
    input logic [1535:0] block_write_words,
    output logic [2:0] block_read_valid,
    output logic [47:0] block_read_masks,
    output logic [3*AW-1:0] block_read_offsets,
    output logic [1535:0] block_read_words,
    output logic block_error
);
    localparam int NTT_LANES=64;
    localparam logic [31:0] P[0:2]='{32'd104857601,32'd69206017,32'd67239937};
    localparam logic [31:0] Q[0:2]='{32'd4190109697,32'd4225761281,32'd4227727361};
    localparam int PROFILE_WORDS=4;
    typedef enum logic [3:0] {IDLE,PROFILE_BEGIN,PROFILE_ROM_START,PROFILE_STREAM,
        PROFILE_COMMIT,PROFILE_CHECK,NTT_START,NTT_WAIT,FAILED} state_t;
    state_t state;
    logic [2:0] step;
    logic [1:0] root_phase,ntt_op;
    logic [2:0] rom_valid,rom_done,rom_busy,profile_loaded,profile_loading,profile_error;
    logic [4:0] profile_size[0:2];
    logic [15:0] profile_next[0:2],rom_addr[0:2];
    logic [31:0] rom_data[0:2],expected_header[0:2];
    logic [2:0] ntt_busy,ntt_done,ntt_error,ntt_host_error,block_errors;
    logic [63:0] child_seed_cycles[0:2];
    wire children_rst_n=rst_n && !cancel && state!=FAILED;
    wire block_request=block_read_en || block_write_en;
    assign block_error=(|block_errors) || (|ntt_host_error) || (start_ntt && block_request);
    assign profile_coherent=(&profile_loaded) && !(|profile_loading) &&
        profile_size[0]==5'(AW) && profile_size[1]==5'(AW) && profile_size[2]==5'(AW) &&
        profile_next[0]==16'(PROFILE_WORDS) && profile_next[1]==16'(PROFILE_WORDS) &&
        profile_next[2]==16'(PROFILE_WORDS);
    assign root_phase=step==0 ? 2'd1 : step==2 ? 2'd2 : 2'd0;
    assign ntt_op=step==1 ? 2'd1 : 2'd0;
    wire core_fault=(|ntt_host_error) || (|block_errors) || (|profile_error) || (|ntt_error) ||
        (profile_cache_valid && !profile_coherent) ||
        (ntt_done!=0 && ntt_done!=3'b111) ||
        ((&ntt_done) && (child_seed_cycles[0]!=child_seed_cycles[1] || child_seed_cycles[0]!=child_seed_cycles[2]));
    assign ready=rst_n && !cancel && state==IDLE && !(|ntt_busy) && !(|rom_busy) &&
        !(|profile_loading) && !(|block_read_valid) && !core_fault && !block_request &&
        (!profile_cache_valid || profile_coherent);
    for(genvar f=0;f<3;f=f+1)begin: field_lane
        genefer_a10_profile3_constants_v1 #(.AW(AW),.P(P[f])) header_contract (
            .address(profile_words_loaded),.word(expected_header[f]),.normalization(),.psi()
        );
        genefer_a10_profile3_rom_v1 #(.AW(AW),.P(P[f])) roots (
            .clk,.rst_n(children_rst_n),.start(state==PROFILE_ROM_START),
            .busy(rom_busy[f]),.done(rom_done[f]),.word_valid(rom_valid[f]),
            .word_addr(rom_addr[f]),.word_data(rom_data[f])
        );
        genefer_anext_upper_block_engine_v1 #(
            .AW(AW),.LANES(NTT_LANES),.P(P[f]),.Q(Q[f])) engine (
            .clk,.rst_n(children_rst_n),.load_we(1'b0),.read_en(1'b0),
            .host_addr({AW{1'b0}}),.write_data(32'd0),.read_valid(),.read_data(),
            .vector_load_we(1'b0),.vector_read_en(1'b0),.vector_addr({AW{1'b0}}),
            .vector_lane_mask(64'd0),.vector_write_data(2048'd0),.vector_read_valid(),
            .host_error(ntt_host_error[f]),.vector_read_mask(),.vector_read_data(),
            .block_external_conflict(1'b0),.block_read_en(block_read_en && !start_ntt),.block_write_en(block_write_en && !start_ntt),
            .block_read_offset,.block_write_offset,.block_read_mask,.block_write_mask,
            .block_write_words(block_write_words[f*512+:512]),
            .block_read_valid(block_read_valid[f]),.block_error(block_errors[f]),
            .block_read_offset_out(block_read_offsets[f*AW+:AW]),
            .block_read_mask_out(block_read_masks[f*16+:16]),.block_read_words(block_read_words[f*512+:512]),
            .profile_begin(state==PROFILE_BEGIN),.profile_we(state==PROFILE_STREAM && rom_valid[f]),
            .profile_commit(state==PROFILE_COMMIT),.profile_abort(1'b0),.profile_size_log2(5'(AW)),
            .profile_modulus(P[f]),.profile_format(8'd3),.profile_addr(rom_addr[f]),.profile_data(rom_data[f]),
            .profile_loaded(profile_loaded[f]),.profile_loading(profile_loading[f]),
            .profile_error(profile_error[f]),.profile_loaded_size(profile_size[f]),
            .profile_next_addr(profile_next[f]),.seed_setup_cycles(child_seed_cycles[f]),
            .root_rom_reads(),.normalization_products(),.profile_epoch(),
            .start(state==NTT_START),.inverse(step==2),.dif(step==2),.root_phase,.op(ntt_op),
            .size_log2(5'(AW)),.scale(32'd0),.busy(ntt_busy[f]),.done(ntt_done[f]),.error(ntt_error[f]),
            .cycles(),.butterflies(),.data_reads(),.data_writes(),.root_reads(),.wait_cycles()
        );
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;step<=0;busy<=0;done<=0;error<=0;
            cycles<=0;root_cycles<=0;ntt_cycles<=0;seed_setup_cycles<=0;
            profile_loads<=0;profile_hits<=0;profile_cache_valid<=0;profile_words_loaded<=0;
        end else begin
            done<=0;
            if(busy)cycles<=cycles+1;
            case(state)
                IDLE: if(start_ntt)begin
                    cycles<=0;root_cycles<=0;ntt_cycles<=0;seed_setup_cycles<=0;
                    profile_loads<=0;profile_hits<=0;profile_words_loaded<=0;step<=0;
                    if(ready)begin
                        busy<=1;error<=0;
                        if(profile_cache_valid)begin state<=NTT_START;profile_hits<=1;end
                        else state<=PROFILE_BEGIN;
                    end else begin
                        state<=FAILED;busy<=0;done<=1;error<=1;profile_cache_valid<=0;
                    end
                end
                PROFILE_BEGIN: begin root_cycles<=root_cycles+1;state<=PROFILE_ROM_START;end
                PROFILE_ROM_START: begin
                    root_cycles<=root_cycles+1;state<=PROFILE_STREAM;
                    if(profile_loading!=3'b111 || (|profile_loaded))begin
                        error<=1;done<=1;busy<=0;state<=FAILED;profile_cache_valid<=0;
                    end
                end
                PROFILE_STREAM: begin
                    root_cycles<=root_cycles+1;
                    // At the edge seeing old ROM done, child accepts the last word.
                    // COMMIT asserts only on the following edge, never on this one.
                    if(&rom_valid)begin
                        profile_words_loaded<=profile_words_loaded+1;
                        if(&rom_done)state<=PROFILE_COMMIT;
                    end
                    if((rom_valid!=0 && rom_valid!=3'b111) ||
                       (rom_done!=0 && rom_done!=3'b111) ||
                       ((|rom_done) && !(&rom_valid)) ||
                       (profile_words_loaded!=0 && !(&rom_valid)) ||
                       ((&rom_valid) && (rom_addr[0]!=profile_words_loaded ||
                         rom_addr[1]!=profile_words_loaded || rom_addr[2]!=profile_words_loaded ||
                         int'(profile_words_loaded)>=PROFILE_WORDS ||
                         rom_data[0]!=expected_header[0] || rom_data[1]!=expected_header[1] || rom_data[2]!=expected_header[2] ||
                         ((&rom_done)!=(int'(profile_words_loaded)==PROFILE_WORDS-1)))))begin
                        error<=1;done<=1;busy<=0;state<=FAILED;profile_cache_valid<=0;
                    end
                end
                PROFILE_COMMIT: begin root_cycles<=root_cycles+1;state<=PROFILE_CHECK;end
                PROFILE_CHECK: begin
                    root_cycles<=root_cycles+1;
                    if(profile_coherent)begin
                        profile_cache_valid<=1;profile_loads<=1;state<=NTT_START;
                    end else begin error<=1;done<=1;busy<=0;state<=FAILED;profile_cache_valid<=0;end
                end
                NTT_START: begin ntt_cycles<=ntt_cycles+1; state<=NTT_WAIT; end
                NTT_WAIT: begin
                    ntt_cycles<=ntt_cycles+1;
                    if(&ntt_done) begin
                        seed_setup_cycles<=seed_setup_cycles+child_seed_cycles[0];
                        if(|ntt_error) begin error<=1; done<=1; busy<=0; state<=FAILED; profile_cache_valid<=0; end
                        else if(step==2) begin state<=IDLE;busy<=0;done<=1;end
                        else begin
                            step<=step+1;
                            state<=NTT_START;
                        end
                    end
                end
                FAILED: ;
                default:begin state<=FAILED;busy<=0;done<=1;error<=1;profile_cache_valid<=0;end
            endcase
            if((busy && core_fault) || (busy && start_ntt))begin
                state<=FAILED;busy<=0;done<=1;error<=1;profile_cache_valid<=0;
            end
            if(cancel)begin
                state<=IDLE;step<=0;busy<=0;done<=0;error<=0;profile_cache_valid<=0;
                cycles<=0;root_cycles<=0;ntt_cycles<=0;seed_setup_cycles<=0;
                profile_loads<=0;profile_hits<=0;profile_words_loaded<=0;
            end
        end
    end
    // synthesis translate_off
    initial if(AW<5 || AW>16)$fatal(1,"ANEXT_NTT_SEQUENCER_GEOMETRY");
    // synthesis translate_on
endmodule

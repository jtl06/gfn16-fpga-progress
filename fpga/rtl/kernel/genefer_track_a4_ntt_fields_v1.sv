// Provisional three-field sequencer extracted from frozen T5 phase/profile order.
// Arithmetic engines are additive guarded route-v2 derivatives; no carry here.
module genefer_track_a4_ntt_fields_v1 #(parameter int AW=16) (
    input logic clk,rst_n,cancel,start_ntt,
    output logic busy,done,error,profile_cache_valid,profile_coherent,
    output logic [63:0] ntt_cycles,root_cycles,seed_setup_cycles,
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
    localparam int LANES=64,WORDS=(2*AW+2)*(4*LANES+1);
    localparam logic [31:0] PRIME[0:2]='{32'd104857601,32'd69206017,32'd67239937};
    localparam logic [31:0] Q[0:2]='{32'd4190109697,32'd4225761281,32'd4227727361};
    localparam logic [31:0] GENERATOR[0:2]='{32'd3,32'd5,32'd10};
    typedef enum logic [3:0] {IDLE,PROFILE_BEGIN,ROM_START,PROFILE_STREAM,PROFILE_COMMIT,
        PROFILE_CHECK,NTT_START,NTT_WAIT,FAILED} state_t;
    state_t state;
    logic [2:0] step;
    logic [15:0] profile_words;
    logic [2:0] rom_valid,rom_done,rom_busy,loaded,loading,profile_error;
    logic [15:0] rom_addr[0:2],profile_next[0:2];
    logic [31:0] rom_data[0:2];
    logic [4:0] profile_size[0:2];
    logic [2:0] ntt_busy,ntt_done,ntt_error,block_errors,host_errors;
    logic [63:0] child_seed[0:2];
    wire children_rst_n=rst_n && !cancel;
    wire [1:0] phase=step==0 ? 2'd0 : step==1 ? 2'd1 : step==3 ? 2'd2 : 2'd3;
    wire [1:0] operation=step==0 || step==4 ? 2'd2 : step==2 ? 2'd1 : 2'd0;
    assign block_error=(|block_errors) || (|host_errors);
    assign profile_coherent=(&loaded) && !(|loading) && profile_size[0]==5'(AW) &&
        profile_size[1]==5'(AW) && profile_size[2]==5'(AW) &&
        profile_next[0]==16'(WORDS) && profile_next[1]==16'(WORDS) && profile_next[2]==16'(WORDS);
    wire fault=(|profile_error) || block_error || (profile_cache_valid && !profile_coherent) ||
        (ntt_done!=0 && !(&ntt_done)) || (|ntt_error) ||
        ((&ntt_done) && (child_seed[0]!=child_seed[1] || child_seed[0]!=child_seed[2]));
    for(genvar f=0;f<3;f=f+1)begin: fields
        genefer_root_profile27_r2_rom #(.AW(AW),.LANES(LANES),.P(PRIME[f]),.GENERATOR(GENERATOR[f])) roots (
            .clk,.rst_n(children_rst_n),.start(state==ROM_START),.busy(rom_busy[f]),.done(rom_done[f]),
            .word_valid(rom_valid[f]),.word_addr(rom_addr[f]),.word_data(rom_data[f])
        );
        genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_blockroute_v2_engine #(
            .AW(AW),.LANES(LANES),.HOST_LANES(16),.P(PRIME[f]),.Q(Q[f])) engine (
            .clk,.rst_n(children_rst_n),.load_we(1'b0),.read_en(1'b0),.host_addr({AW{1'b0}}),.write_data(32'd0),.read_valid(),.read_data(),
            .vector_load_we(1'b0),.vector_read_en(1'b0),.vector_addr({AW{1'b0}}),.vector_lane_mask(16'd0),
            .vector_write_data(512'd0),.vector_read_valid(),.host_error(host_errors[f]),.vector_read_mask(),.vector_read_data(),
            .block_read_en,.block_write_en,.block_read_offset,.block_write_offset,.block_read_mask,.block_write_mask,
            .block_write_words(block_write_words[f*512+:512]),.block_read_valid(block_read_valid[f]),.block_error(block_errors[f]),
            .block_read_offset_out(block_read_offsets[f*AW+:AW]),.block_read_mask_out(block_read_masks[f*16+:16]),
            .block_read_words(block_read_words[f*512+:512]),
            .profile_begin(state==PROFILE_BEGIN),.profile_we(state==PROFILE_STREAM && rom_valid[f]),
            .profile_commit(state==PROFILE_COMMIT),.profile_size_log2(5'(AW)),.profile_modulus(PRIME[f]),
            .profile_data(rom_data[f]),.profile_format(8'd2),.profile_addr(rom_addr[f]),
            .profile_loaded(loaded[f]),.profile_loading(loading[f]),.profile_error(profile_error[f]),
            .profile_loaded_size(profile_size[f]),.profile_next_addr(profile_next[f]),.seed_setup_cycles(child_seed[f]),
            .start(state==NTT_START && !fault),.inverse(1'b0),.dif(step==1),.root_phase(phase),.op(operation),
            .size_log2(5'(AW)),.scale(32'd0),.busy(ntt_busy[f]),.done(ntt_done[f]),.error(ntt_error[f]),
            .cycles(),.butterflies(),.data_reads(),.data_writes(),.root_reads(),.wait_cycles()
        );
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;step<=0;profile_words<=0;busy<=0;done<=0;error<=0;
            profile_cache_valid<=0;ntt_cycles<=0;root_cycles<=0;seed_setup_cycles<=0;
        end else begin
            done<=0;
            if(state==IDLE && start_ntt)begin
                busy<=1;error<=0;step<=0;profile_words<=0;ntt_cycles<=0;root_cycles<=0;seed_setup_cycles<=0;
                if(profile_cache_valid && profile_coherent)state<=NTT_START;
                else if(profile_cache_valid || (|ntt_busy))begin state<=FAILED;error<=1;busy<=0;end
                else state<=PROFILE_BEGIN;
            end
            case(state)
                PROFILE_BEGIN:begin root_cycles<=root_cycles+1'b1;state<=ROM_START;end
                ROM_START:begin root_cycles<=root_cycles+1'b1;state<=PROFILE_STREAM;end
                PROFILE_STREAM:begin
                    root_cycles<=root_cycles+1'b1;
                    if(&rom_valid)profile_words<=profile_words+1'b1;
                    if(&rom_done)state<=PROFILE_COMMIT;
                    if((rom_valid!=0 && !(&rom_valid)) || (rom_done!=0 && !(&rom_done)) ||
                       ((|rom_done) && !(&rom_valid)) || (profile_words!=0 && !(&rom_valid)) ||
                       ((&rom_valid) && (rom_addr[0]!=profile_words || rom_addr[1]!=profile_words || rom_addr[2]!=profile_words ||
                           int'(profile_words)>=WORDS || rom_data[0]>=PRIME[0] || rom_data[1]>=PRIME[1] || rom_data[2]>=PRIME[2] ||
                           ((&rom_done)!=(int'(profile_words)==WORDS-1)))))begin
                        state<=FAILED;error<=1;busy<=0;profile_cache_valid<=0;
                    end
                end
                PROFILE_COMMIT:begin root_cycles<=root_cycles+1'b1;state<=PROFILE_CHECK;end
                PROFILE_CHECK:begin
                    root_cycles<=root_cycles+1'b1;
                    if(profile_coherent)begin profile_cache_valid<=1;state<=NTT_START;end
                    else begin state<=FAILED;error<=1;busy<=0;profile_cache_valid<=0;end
                end
                NTT_START:begin ntt_cycles<=ntt_cycles+1'b1;state<=NTT_WAIT;end
                NTT_WAIT:begin
                    ntt_cycles<=ntt_cycles+1'b1;
                    if(&ntt_done)begin
                        seed_setup_cycles<=seed_setup_cycles+child_seed[0];
                        if(step==4)begin state<=IDLE;busy<=0;done<=1;end
                        else begin step<=step+1'b1;state<=NTT_START;end
                    end
                end
                default:;
            endcase
            if((busy && fault) || (busy && start_ntt))begin
                state<=FAILED;busy<=0;done<=0;error<=1;profile_cache_valid<=0;
            end
            if(cancel)begin state<=IDLE;busy<=0;done<=0;error<=0;profile_cache_valid<=0;end
        end
    end
endmodule

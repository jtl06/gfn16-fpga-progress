// Isolated format2 experiment; source/model checks are not RTL validation.
// LOCAL UNVALIDATED RTL: format2 R2-twist/input-fusion clone of prefetch9824.
// All digit reducers/guards retained; standalone conversion multipliers removed.
// Precision streaming carry, original61-stage CRT and prefetch schedule unchanged.
// Precision carry keeps canonical digits in signed32 RAM, streams guarded96-bit
// coefficients directly, and retains the external sign-extended96 read contract.
// Autonomous fixed-size squareDup in Z/(base^(2^AW)+1), AW in [1,16].
// Host loads canonical signed32 digits while idle; -1 is the special residue.
// Result remains in carry RAM and can feed the next start without host traffic.
// Reset aborts all work; reload every digit after reset or any reported error.
module genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rowcompact_resetprobe #(
    parameter int AW=16,
    parameter int NTT_LANES=64
) (
    input logic clk, rst_n, load_we, read_en, start,
    input logic [AW-1:0] host_addr,
    input logic signed [31:0] write_data,
    input logic [31:0] base,
    input logic double_bit,
    output logic read_valid,
    output logic signed [95:0] read_data,
    output logic busy, done, error,
    output logic [63:0] cycles, conversion_cycles, root_cycles, ntt_cycles,
                        crt_cycles, carry_cycles,
    output logic [6:0] carry_passes,
    output logic profile_cache_valid,
    output logic profile_loads,profile_hits,
    output logic [15:0] profile_words_loaded,
    output logic [63:0] seed_setup_cycles
);
    // Atomic27/R=2^32, format2 R2-twist roots,64 arithmetic lanes/16 host lanes.
    // Diagnostics describe one compact bundle per field, not four full tables.
    localparam bit DIFDIT=1, PREFIX_CARRY=1, ROOT_CACHE=1, BANKED_NTT=1, VECTOR_IO=1, FAST_ARITH=1;
    localparam int CARRY_LANES=16;
    localparam int N=1<<AW;
    localparam int IO_WIDTH=VECTOR_IO ? CARRY_LANES : 1;
    localparam bit USE_HOST_ADAPTER=FAST_ARITH && VECTOR_IO && NTT_LANES==64 && CARRY_LANES==16;
    localparam int IO_STEP=N<IO_WIDTH ? N : IO_WIDTH;
    localparam logic [IO_WIDTH-1:0] IO_MASK={IO_WIDTH{1'b1}} >> (IO_WIDTH-IO_STEP);
    localparam logic [31:0] P[0:2]='{32'd104857601,32'd69206017,32'd67239937};
    localparam logic [31:0] Q[0:2]='{32'd4190109697,32'd4225761281,32'd4227727361};
    localparam logic [31:0] R2[0:2]='{32'd45971250,32'd50081300,32'd63576045};
    localparam logic [31:0] G[0:2]='{32'd3,32'd5,32'd10};
    localparam int PROFILE_WORDS=(2*AW+2)*(4*NTT_LANES+1);
    typedef enum logic [3:0] {IDLE,CONVERT,PROFILE_BEGIN,PROFILE_ROM_START,PROFILE_STREAM,
        PROFILE_COMMIT,PROFILE_CHECK,NTT_START,NTT_WAIT,RESIDUES,CARRY_START,CARRY_WAIT,FAILED} state_t;
    state_t state;
    logic carry_stream_ready,residue_issue;
    logic [31:0] base_reg;
    logic double_reg;
    logic [AW:0] issue_count, write_count;
    logic [2:0] step;
    logic [1:0] root_phase, next_root_phase, ntt_op;
    logic carry_load,carry_read,carry_start,carry_valid,carry_busy,carry_done,carry_error;
    logic [AW-1:0] carry_addr;
    logic signed [95:0] carry_input,carry_output,coefficient;
    logic [2:0] conversion_valid,rom_valid,rom_done,rom_busy;
    logic [2:0] profile_loaded,profile_loading,profile_error;
    logic [4:0] profile_size[0:2];
    logic [15:0] profile_next[0:2],rom_addr[0:2];
    logic [31:0] rom_data[0:2];
    logic [63:0] child_seed_cycles[0:2];
    logic profile_coherent;
    logic [2:0] ntt_valid,ntt_busy,ntt_done,ntt_error;
    logic [31:0] conversion_data[0:2],ntt_data[0:2];
    logic crt_valid,crt_ready;
    logic [63:0] carry_kernel_cycles;
    logic carry_vector_valid,carry_host_error,convert_input_valid,bad_digit;
    logic [IO_WIDTH-1:0] carry_vector_mask,convert_mask;
    logic [IO_WIDTH*96-1:0] carry_vector_output,carry_vector_input;
    logic signed [95:0] carry_words[0:IO_WIDTH-1],coefficient_words[0:IO_WIDTH-1];
    logic [IO_WIDTH-1:0] convert_valid_words[0:2],crt_valid_words,crt_ready_words;
    logic [IO_WIDTH*32-1:0] convert_words[0:2],ntt_words[0:2];
    logic [IO_WIDTH-1:0] ntt_masks[0:2];
    logic [2:0] ntt_host_error,ntt_scalar_valid;
    logic [AW-1:0] carry_vector_addr;
    logic [2:0] reduction_error;
    logic [IO_WIDTH-1:0] reduce_valid_words[0:2],reduce_error_words[0:2];

    // Once setup finishes, the frozen precision carry accepts every ordered row.
    // Its97-clock setup overlaps roots/NTT; short warm transforms wait here.
    assign residue_issue=state==RESIDUES && int'(issue_count)<N && carry_stream_ready;
    assign carry_vector_addr=state==CONVERT ? AW'(issue_count) : AW'(write_count);
    assign convert_input_valid=VECTOR_IO ? carry_vector_valid : carry_valid;
    assign convert_mask=VECTOR_IO ? carry_vector_mask : IO_MASK;
    assign crt_valid=crt_valid_words[0];
    assign crt_ready=&crt_ready_words;
    assign coefficient=coefficient_words[0];
    for(genvar h=0;h<IO_WIDTH;h=h+1)begin: coefficient_lane
        assign carry_words[h]=VECTOR_IO ? $signed(carry_vector_output[h*96+:96]) : carry_output;
        assign carry_vector_input[h*96+:96]=double_reg ? (coefficient_words[h] <<< 1) : coefficient_words[h];
        genefer_crt3_27_pipe crt (
            .clk,.rst_n,.in_valid(state==RESIDUES && (&ntt_valid) && IO_MASK[h]),
            .r1(ntt_words[0][h*32+:32]),.r2(ntt_words[1][h*32+:32]),.r3(ntt_words[2][h*32+:32]),
            .ready(crt_ready_words[h]),.out_valid(crt_valid_words[h]),.coefficient(coefficient_words[h])
        );
    end
    always_comb begin
        bad_digit=0;
        for(int h=0;h<IO_WIDTH;h=h+1)
            if(convert_input_valid && convert_mask[h] && carry_words[h]!=-96'sd1 &&
               (carry_words[h]<0 || carry_words[h]>=$signed({64'd0,base_reg}))) bad_digit=1;
    end

    assign profile_coherent=(&profile_loaded) && !(|profile_loading) &&
        profile_size[0]==5'(AW) && profile_size[1]==5'(AW) && profile_size[2]==5'(AW) &&
        profile_next[0]==16'(PROFILE_WORDS) && profile_next[1]==16'(PROFILE_WORDS) &&
        profile_next[2]==16'(PROFILE_WORDS);
    assign read_valid=state==IDLE && carry_valid;
    assign read_data=carry_output;
    assign root_phase=step==0 ? 2'd0 : step==1 ? 2'd1 : step==3 ? 2'd2 : 2'd3;
    assign next_root_phase=step==0 ? 2'd1 : step==2 ? 2'd2 : 2'd3;
    assign ntt_op=step==0 || step==4 ? 2'd2 : step==2 ? 2'd1 : 2'd0;
    always_comb begin
        carry_load=0; carry_read=0; carry_start=state==CONVERT && (&conversion_valid) && int'(write_count)==N-IO_STEP;
        carry_addr=host_addr; carry_input={{64{write_data[31]}},write_data};
        if(state==IDLE && !start) begin carry_load=load_we; carry_read=read_en; end
        if(state==CONVERT) begin
            carry_addr=AW'(issue_count); carry_read=!VECTOR_IO && int'(issue_count)<N;
        end
        if(state==RESIDUES && crt_valid) begin
            carry_load=!VECTOR_IO; carry_addr=AW'(write_count);
            carry_input=double_reg ? (coefficient <<< 1) : coefficient;
        end
    end
        genefer_carry_prefix_stream_precision #(.AW(AW),.LANES(IO_WIDTH)) carry_unit (
            .clk,.rst_n,.load_we(carry_load),.read_en(carry_read),.start(carry_start),
            .host_addr(carry_addr),.write_data(carry_input),.size_log2(5'(AW)),.base(base_reg),
            .read_valid(carry_valid),.read_data(carry_output),.busy(carry_busy),
            .done(carry_done),.error(carry_error),.cycles(carry_kernel_cycles),.passes(carry_passes),
            .vector_load_we(1'b0),
            .stream_valid(state==RESIDUES && crt_valid),.stream_ready(carry_stream_ready),
            .stream_addr(carry_vector_addr),.stream_mask(IO_MASK),.stream_data(carry_vector_input),
            .vector_read_en(state==CONVERT && int'(issue_count)<N),
            .vector_addr(carry_vector_addr),
            .vector_lane_mask(IO_MASK),.vector_write_data(carry_vector_input),
            .vector_read_valid(carry_vector_valid),.vector_read_mask(carry_vector_mask),
            .vector_read_data(carry_vector_output),.host_error(carry_host_error)
        );
    for(genvar f=0; f<3; f=f+1) begin: field_lane
        logic ntt_load,ntt_read;
        logic [AW-1:0] addr;
        logic [31:0] data;
        assign conversion_valid[f]=convert_valid_words[f][0];
        assign conversion_data[f]=convert_words[f][31:0];
        assign reduction_error[f]=|reduce_error_words[f];
        for(genvar h=0;h<IO_WIDTH;h=h+1)begin: input_lane
            logic [31:0] canonical_digit;
            // Validate the entire signed96 row against the latched base first.
            // The full signed32 word reaches the reducer; never truncate raw
            // digits to27 bits, since legal base digits can exceed every P.
            genefer_digit_reduce27_pipe #(.P(P[f]),.PAYLOAD_W(1)) digit_reduce (
                .clk,.rst_n,.in_valid(state==CONVERT && convert_input_valid && convert_mask[h] && !bad_digit),
                .digit(carry_words[h][31:0]),.payload_in(1'b0),
                .out_valid(reduce_valid_words[f][h]),.out_error(reduce_error_words[f][h]),
                .residue(canonical_digit),.payload_out()
            );
            // Format2 twist consumes ordinary canonical d, not d*R.
            // Preserve the reducer and a registered boundary before NTT RAM.
            // Payload holds on bubbles/reset; reset clears eligibility only.
            always_ff @(posedge clk or negedge rst_n) begin
                if(!rst_n) convert_valid_words[f][h]<=0;
                else convert_valid_words[f][h]<=state==CONVERT &&
                    reduce_valid_words[f][h] && !reduce_error_words[f][h];
            end
            always_ff @(posedge clk) begin
                if(rst_n && state==CONVERT && reduce_valid_words[f][h] && !reduce_error_words[f][h])
                    convert_words[f][h*32+:32]<=canonical_digit;
            end
        end
        genefer_root_profile27_r2_rom #(.AW(AW),.LANES(NTT_LANES),.P(P[f]),.GENERATOR(G[f])) roots (
            .clk,.rst_n,.start(state==PROFILE_ROM_START),
            .busy(rom_busy[f]),.done(rom_done[f]),.word_valid(rom_valid[f]),
            .word_addr(rom_addr[f]),.word_data(rom_data[f])
        );
        assign ntt_load=state==CONVERT && conversion_valid[f];
        assign ntt_read=residue_issue;
        assign addr=state==CONVERT ? AW'(write_count) : AW'(issue_count);
        assign data=conversion_data[f];
        genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rowcompact_engine_resetprobe #(.AW(AW),.LANES(NTT_LANES),.HOST_LANES(IO_WIDTH),.P(P[f]),.Q(Q[f])) engine (
            .clk,.rst_n,.load_we(1'b0),.read_en(1'b0),
            .host_addr(addr),.write_data(data),.read_valid(ntt_scalar_valid[f]),.read_data(ntt_data[f]),
            .vector_load_we(ntt_load),.vector_read_en(ntt_read),
            .vector_addr(state==CONVERT ? AW'(write_count) : AW'(issue_count)),
            .vector_lane_mask(IO_MASK),.vector_write_data(convert_words[f]),
            .vector_read_valid(ntt_valid[f]),.vector_read_mask(ntt_masks[f]),
            .vector_read_data(ntt_words[f]),.host_error(ntt_host_error[f]),
            .profile_begin(state==PROFILE_BEGIN),.profile_we(state==PROFILE_STREAM && rom_valid[f]),
            .profile_commit(state==PROFILE_COMMIT),.profile_size_log2(5'(AW)),
            .profile_modulus(P[f]),.profile_format(8'd2),.profile_addr(rom_addr[f]),.profile_data(rom_data[f]),
            .profile_loaded(profile_loaded[f]),.profile_loading(profile_loading[f]),
            .profile_error(profile_error[f]),.profile_loaded_size(profile_size[f]),
            .profile_next_addr(profile_next[f]),.seed_setup_cycles(child_seed_cycles[f]),
            .start(state==NTT_START),.inverse(1'b0),.dif(step==1),.root_phase,.op(ntt_op),
            .size_log2(5'(AW)),.scale(32'd0),.busy(ntt_busy[f]),.done(ntt_done[f]),.error(ntt_error[f]),
            .cycles(),.butterflies(),.data_reads(),.data_writes(),.root_reads(),.wait_cycles()
        );
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE; busy<=0; done<=0; error<=0; base_reg<=2; double_reg<=0;
            issue_count<=0; write_count<=0; step<=0;
            cycles<=0; conversion_cycles<=0; root_cycles<=0; ntt_cycles<=0; crt_cycles<=0; carry_cycles<=0;
            profile_loads<=0;profile_hits<=0;profile_cache_valid<=0;profile_words_loaded<=0;seed_setup_cycles<=0;
        end else begin
            done<=0;
            if(busy) cycles<=cycles+1;
            case(state)
                IDLE: if(start) begin
                    error<=0; cycles<=0; conversion_cycles<=0; root_cycles<=0;
                    ntt_cycles<=0; crt_cycles<=0; carry_cycles<=0;
                    profile_loads<=0;profile_hits<=0;profile_words_loaded<=0;seed_setup_cycles<=0;
                    if(base<2 || base>1000000000 || AW<1 || AW>16 ||
                       NTT_LANES!=64 || base <= 32'(2*N+4)) begin
                        error<=1; done<=1; state<=FAILED; profile_cache_valid<=0;
                    end else begin
                        base_reg<=base; double_reg<=double_bit; busy<=1;
                        issue_count<=0; write_count<=0; step<=0; state<=CONVERT;
                    end
                end
                CONVERT: begin
                    conversion_cycles<=conversion_cycles+1;
                    if(int'(issue_count)<N) issue_count<=issue_count+(AW+1)'(IO_STEP);
                    if(&conversion_valid) begin
                        write_count<=write_count+(AW+1)'(IO_STEP);
                        if(int'(write_count)==N-IO_STEP) begin
                            if(profile_cache_valid) begin
                                state<=NTT_START;profile_hits<=1;
                            end else state<=PROFILE_BEGIN;
                        end
                    end
                    if(bad_digit) begin
                        error<=1; done<=1; busy<=0; state<=FAILED; profile_cache_valid<=0;
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
                         rom_data[0]>=P[0] || rom_data[1]>=P[1] || rom_data[2]>=P[2] ||
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
                        else if(step==4) begin issue_count<=0; write_count<=0; state<=RESIDUES; end
                        else begin
                            step<=step+1;
                            state<=NTT_START;
                        end
                    end
                end
                RESIDUES: begin
                    crt_cycles<=crt_cycles+1;
                    if(residue_issue) issue_count<=issue_count+(AW+1)'(IO_STEP);
                    if(crt_valid) begin
                        write_count<=write_count+(AW+1)'(IO_STEP);
                        if(int'(write_count)==N-IO_STEP) state<=CARRY_WAIT;
                    end
                end
                CARRY_START: begin carry_cycles<=carry_cycles+1; state<=CARRY_WAIT; end
                CARRY_WAIT: begin
                    carry_cycles<=carry_cycles+1;
                    if(carry_done) begin
                        busy<=0; done<=1; error<=carry_error;
                        state<=carry_error ? FAILED : IDLE;
                        if(carry_error) profile_cache_valid<=0;
                    end
                end
                FAILED: ;
                default: begin state<=FAILED; busy<=0; done<=1; error<=1; profile_cache_valid<=0; end
            endcase
            if(busy && (carry_host_error || (|ntt_host_error) || (|reduction_error) || (|profile_error) ||
               (profile_cache_valid && !profile_coherent) ||
               (conversion_valid!=0 && conversion_valid!=3'b111) ||
               (ntt_valid!=0 && ntt_valid!=3'b111) || (ntt_done!=0 && ntt_done!=3'b111) ||
               ((&ntt_done) && (child_seed_cycles[0]!=child_seed_cycles[1] || child_seed_cycles[0]!=child_seed_cycles[2])) ||
               carry_error || (carry_done && state!=CARRY_WAIT) ||
               (state==RESIDUES && crt_valid && !carry_stream_ready)))begin
                error<=1;done<=1;busy<=0;state<=FAILED;profile_cache_valid<=0;
            end
        end
    end
    // synthesis translate_off
    initial begin
        for(int f=0;f<3;f=f+1)begin
            if(32'(64'(P[f])*64'(Q[f]))!=32'd1)$fatal(1,"core27 profile inverse mismatch");
            if(R2[f]!=32'(((64'h100000000%64'(P[f]))*(64'h100000000%64'(P[f])))%64'(P[f])))
                $fatal(1,"core27 radix32 R2 mismatch");
        end
        // Centered CRT must cover doubled worst-case coefficients at full N.
        if(96'd487945222748036195811329 <= 96'd262143999475712000262144)
            $fatal(1,"core27 centered range mismatch");
    end
    always @(posedge clk) if(rst_n && busy) begin
        if(conversion_valid!=0 && conversion_valid!=3'b111) $fatal(1,"conversion lane skew");
        if(ntt_valid!=0 && ntt_valid!=3'b111) $fatal(1,"residue lane skew");
        if(ntt_done!=0 && ntt_done!=3'b111) $fatal(1,"NTT lane skew");
        if(rom_done!=0 && rom_done!=3'b111 && state==PROFILE_STREAM) $fatal(1,"profile ROM lane skew");
        for(int f=0;f<3;f=f+1)begin
            if(reduce_valid_words[f]!=0 && reduce_valid_words[f]!=IO_MASK) $fatal(1,"reduction word skew");
            if(convert_valid_words[f]!=0 && convert_valid_words[f]!=IO_MASK) $fatal(1,"conversion word skew");
            if(ntt_valid[f] && ntt_masks[f]!=IO_MASK) $fatal(1,"residue mask skew");
        end
        if(crt_valid_words!=0 && crt_valid_words!=IO_MASK) $fatal(1,"CRT word skew");
    end
    // synthesis translate_on
endmodule

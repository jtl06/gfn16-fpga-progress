// Simulation-only fault bridge. Never a physical top.
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
// SOURCE-ONLY T5b: source row FF + two field-local launch FFs.
// Invalidated images are quarantined until reset/reload; already-admitted
// rows may write on a fault-detection edge, never after the flush edge.
// No clock claim; source registers are not a demonstrated M20K packing result.
module core27_prefill_pipe_fault_bridge_v1 #(
    parameter int AW=16,
    parameter int NTT_LANES=64
) (
    input logic clk, rst_n, load_we, read_en, start,
    input logic [2:0] sim_host_error,
    input logic sim_carry_error,
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
        PROFILE_COMMIT,PROFILE_CHECK,NTT_START,NTT_WAIT,RESIDUES,CARRY_START,CARRY_WAIT,FAILED,PREFILL_CHECK} state_t;
    state_t state;
    logic carry_stream_ready,residue_issue;
    logic [31:0] base_reg;
    logic double_reg;
    logic [AW:0] issue_count, write_count;
    logic [2:0] step;
    logic [1:0] root_phase, next_root_phase, ntt_op;
    logic carry_load,carry_read,carry_start,carry_valid,carry_busy,carry_done,carry_error;
    logic native_carry_error;
    assign carry_error=native_carry_error | sim_carry_error;
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
    logic [2:0] native_ntt_host_error;
    assign ntt_host_error=native_ntt_host_error | sim_host_error;
    logic [AW-1:0] carry_vector_addr;
    logic [2:0] reduction_error;
    logic [IO_WIDTH-1:0] reduce_valid_words[0:2],reduce_error_words[0:2];

    assign core_fault=carry_host_error || (|ntt_host_error) || (|reduction_error) || (|profile_error) ||
               (profile_cache_valid && !profile_coherent) ||
               (conversion_valid!=0 && conversion_valid!=3'b111) ||
               (ntt_valid!=0 && ntt_valid!=3'b111) || (ntt_done!=0 && ntt_done!=3'b111) ||
               ((&ntt_done) && (child_seed_cycles[0]!=child_seed_cycles[1] || child_seed_cycles[0]!=child_seed_cycles[2])) ||
               carry_error || (carry_done && state!=CARRY_WAIT) ||
               (state==RESIDUES && crt_valid && !carry_stream_ready);
    // Source capture E0 -> reducer E1..E4 -> boundary E5 -> field launch
    // E6/E7 -> RAM E8 -> registered host-error check E9. II remains one.
    // All launch payload and descriptors travel through the SAME registers.
    logic emit_commit_valid;
    logic [AW-1:0] emit_commit_addr;
    logic [IO_WIDTH-1:0] emit_commit_mask;
    logic [IO_WIDTH*96-1:0] emit_commit_data;
    logic ntt_prefilled,fast_start_pending,carry_success;
    logic [31:0] prefill_base;
    logic [AW:0] prefill_issued,prefill_written;
    logic [3:0] prefill_pipe_valid;
    logic [AW-1:0] prefill_pipe_addr[0:3],prefill_boundary_addr;
    logic [IO_WIDTH-1:0] prefill_pipe_mask[0:3],prefill_boundary_mask;
    logic prefill_boundary_valid,prefill_accept,prefill_commit,prefill_fault,core_fault;
    logic prefill_window,fast_eligible,prefill_complete;
    logic source_valid,source_prefill,source_capture;
    logic [AW-1:0] source_addr;
    logic [IO_WIDTH-1:0] source_mask;
    logic [IO_WIDTH*96-1:0] source_words;
    logic [AW:0] conversion_sent,prefill_launched;
    logic boundary_admit;
    (* preserve, dont_merge *) logic [1:0] field_launch_valid[0:2];
    (* preserve, dont_merge *) logic [AW-1:0] field_launch_addr[0:2][0:1];
    (* preserve, dont_merge *) logic [IO_WIDTH-1:0] field_launch_mask[0:2][0:1];
    (* preserve, dont_merge *) logic [IO_WIDTH*32-1:0] field_launch_words[0:2][0:1];
    logic [2:0] field_write_valid;
    logic launch_empty;
    assign launch_empty=(field_launch_valid[0]==0 && field_launch_valid[1]==0 && field_launch_valid[2]==0);
    assign source_capture=(state==CONVERT && (VECTOR_IO ? carry_vector_valid : carry_valid)) ||
        (prefill_window && emit_commit_valid && !prefill_fault && !core_fault);
    // A RAM-output/source register cuts the previous RAM -> bad_digit -> ena cone.
    // Payload is deliberately not reset. A fault flush wins over capture.
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin source_valid<=0;source_prefill<=0;end
        else begin
            source_valid<=source_capture;source_prefill<=prefill_window;
            if(state==FAILED || error || (busy && (core_fault || prefill_fault)) ||
               (state==IDLE && start))source_valid<=0;
        end
    end
    always_ff @(posedge clk)if(rst_n && source_capture)begin
        source_addr<=emit_commit_addr;
        source_mask<=prefill_window ? emit_commit_mask : (VECTOR_IO ? carry_vector_mask : IO_MASK);
        for(int h=0;h<IO_WIDTH;h=h+1)
            source_words[h*96+:96]<=prefill_window ? emit_commit_data[h*96+:96] :
                (VECTOR_IO ? carry_vector_output[h*96+:96] : carry_output);
    end
    assign prefill_window=state==CARRY_WAIT;
    assign fast_eligible=ntt_prefilled && base==prefill_base &&
        profile_cache_valid && profile_coherent;
    assign prefill_complete=carry_success && int'(prefill_issued)==N &&
        int'(prefill_written)==N && prefill_pipe_valid==0 &&
        !source_valid && !prefill_boundary_valid && conversion_valid==0 && launch_empty &&
        !carry_busy && !(|ntt_busy) && profile_cache_valid && profile_coherent;
    always_comb begin
        prefill_fault=0;
        if(prefill_window)begin
            if(source_valid && source_prefill && bad_digit)prefill_fault=1;
            if(emit_commit_valid && (emit_commit_mask!=IO_MASK ||
               emit_commit_addr!=AW'(prefill_issued) || int'(prefill_issued)>=N))
                prefill_fault=1;
            if((emit_commit_valid || prefill_boundary_valid) &&
               ((|ntt_busy) || (|ntt_valid) || (|profile_loading)))prefill_fault=1;
            for(int f=0;f<3;f=f+1)begin
                if(reduce_valid_words[f]!=(prefill_pipe_valid[3] ? IO_MASK : '0))
                    prefill_fault=1;
                if(convert_valid_words[f]!=(prefill_boundary_valid ? IO_MASK : '0))
                    prefill_fault=1;
            end
            if(prefill_boundary_valid && (prefill_boundary_mask!=IO_MASK ||
               prefill_boundary_addr!=AW'(prefill_launched) ||
               int'(prefill_launched)>=N))prefill_fault=1;
            if(carry_done && (carry_error || int'(prefill_issued)!=N))prefill_fault=1;
            if(carry_success && !source_valid && prefill_pipe_valid==0 && !prefill_boundary_valid &&
               conversion_valid==0 && launch_empty && int'(prefill_written)!=N)prefill_fault=1;
        end
        if(emit_commit_valid && !prefill_window)prefill_fault=1;
    end
    assign prefill_accept=prefill_window && source_valid && source_prefill && !prefill_fault && !core_fault;
    assign boundary_admit=((state==CONVERT && (&conversion_valid) && !bad_digit) ||
        (prefill_window && prefill_boundary_valid && (&conversion_valid))) && !prefill_fault && !core_fault;
    // Do not reconnect combinational global fault to the physical RAM write enable.
    assign prefill_commit=prefill_window && (&field_write_valid);
    // Eligibility belongs to a complete data image, not merely cached roots.
    // Host reads preserve it; an accepted host load or any accepted start clears it.
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            ntt_prefilled<=0;prefill_base<=0;fast_start_pending<=0;carry_success<=0;
            prefill_issued<=0;prefill_written<=0;prefill_pipe_valid<=0;prefill_boundary_valid<=0;
            conversion_sent<=0;prefill_launched<=0;
        end else begin
            prefill_pipe_valid<={prefill_pipe_valid[2:0],prefill_accept};
            prefill_boundary_valid<=prefill_window && prefill_pipe_valid[3];
            if(prefill_accept)begin
                prefill_pipe_addr[0]<=source_addr;
                prefill_pipe_mask[0]<=source_mask;
            end
            for(int d=1;d<4;d=d+1)if(prefill_pipe_valid[d-1])begin
                prefill_pipe_addr[d]<=prefill_pipe_addr[d-1];
                prefill_pipe_mask[d]<=prefill_pipe_mask[d-1];
            end
            if(prefill_pipe_valid[3])begin
                prefill_boundary_addr<=prefill_pipe_addr[3];
                prefill_boundary_mask<=prefill_pipe_mask[3];
            end
            if(prefill_window && source_capture)prefill_issued<=prefill_issued+(AW+1)'(IO_STEP);
            if(boundary_admit && prefill_window)prefill_launched<=prefill_launched+(AW+1)'(IO_STEP);
            if(boundary_admit && state==CONVERT)conversion_sent<=conversion_sent+(AW+1)'(IO_STEP);
            if(prefill_commit)prefill_written<=prefill_written+(AW+1)'(IO_STEP);
            if(prefill_window && carry_done && !carry_error)carry_success<=1;
            if(state==NTT_START)fast_start_pending<=0;
            if(state==PREFILL_CHECK && prefill_complete && !core_fault && !prefill_fault)begin
                ntt_prefilled<=1;prefill_base<=base_reg;
            end
            if(state==IDLE && !start && load_we)ntt_prefilled<=0;
            if(state==IDLE && start)begin
                ntt_prefilled<=0;fast_start_pending<=fast_eligible;
                prefill_issued<=0;prefill_written<=0;carry_success<=0;
                conversion_sent<=0;prefill_launched<=0;
                prefill_pipe_valid<=0;prefill_boundary_valid<=0;
            end
            if(state==FAILED || error || (busy && (core_fault || prefill_fault)))begin
                ntt_prefilled<=0;fast_start_pending<=0;prefill_pipe_valid<=0;
                prefill_boundary_valid<=0;
            end
        end
    end

    // Once setup finishes, the frozen precision carry accepts every ordered row.
    // Its97-clock setup overlaps roots/NTT; short warm transforms wait here.
    assign residue_issue=state==RESIDUES && int'(issue_count)<N && carry_stream_ready;
    assign carry_vector_addr=state==CONVERT ? AW'(issue_count) : AW'(write_count);
    assign convert_input_valid=source_valid;
    assign convert_mask=source_mask;
    assign crt_valid=crt_valid_words[0];
    assign crt_ready=&crt_ready_words;
    assign coefficient=coefficient_words[0];
    for(genvar h=0;h<IO_WIDTH;h=h+1)begin: coefficient_lane
        assign carry_words[h]=$signed(source_words[h*96+:96]);
        assign carry_vector_input[h*96+:96]=double_reg ? (coefficient_words[h] <<< 1) : coefficient_words[h];
        genefer_crt3_27_mont_pipe crt (
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
        carry_load=0; carry_read=0; carry_start=(state==CONVERT && (&field_write_valid) && int'(write_count)==N-IO_STEP) ||
            (state==NTT_START && step==0 && fast_start_pending);
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
        genefer_carry_prefix_stream_precision_emit #(.AW(AW),.LANES(IO_WIDTH)) carry_unit (
            .clk,.rst_n,.load_we(carry_load),.read_en(carry_read),.start(carry_start),
            .host_addr(carry_addr),.write_data(carry_input),.size_log2(5'(AW)),.base(base_reg),
            .read_valid(carry_valid),.read_data(carry_output),.busy(carry_busy),
            .done(carry_done),.error(native_carry_error),.cycles(carry_kernel_cycles),.passes(carry_passes),
            .vector_load_we(1'b0),
            .stream_valid(state==RESIDUES && crt_valid),.stream_ready(carry_stream_ready),
            .stream_addr(carry_vector_addr),.stream_mask(IO_MASK),.stream_data(carry_vector_input),
            .vector_read_en(state==CONVERT && int'(issue_count)<N),
            .vector_addr(carry_vector_addr),
            .vector_lane_mask(IO_MASK),.vector_write_data(carry_vector_input),
            .vector_read_valid(carry_vector_valid),.vector_read_mask(carry_vector_mask),
            .vector_read_data(carry_vector_output),.host_error(carry_host_error),
            .emit_commit_valid,.emit_commit_addr,.emit_commit_mask,.emit_commit_data
        );
    for(genvar f=0; f<3; f=f+1) begin: field_lane
        logic ntt_load,ntt_read;
        logic [AW-1:0] addr;
        logic [31:0] data;
        assign conversion_valid[f]=convert_valid_words[f][0];
        assign field_write_valid[f]=field_launch_valid[f][1];
        // Field-local admission and physical launch registers: control and data
        // share both edges. Clearing valid never fabricates replacement payload.
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)field_launch_valid[f]<=0;
            else begin
                field_launch_valid[f]<={field_launch_valid[f][0],boundary_admit};
                if(state==FAILED || error || (busy && (core_fault || prefill_fault)) ||
                   (state==CONVERT && bad_digit) || (state==IDLE && start))
                    field_launch_valid[f]<=0;
            end
        end
        always_ff @(posedge clk)if(rst_n)begin
            if(boundary_admit)begin
                field_launch_addr[f][0]<=prefill_window ? prefill_boundary_addr : AW'(conversion_sent);
                field_launch_mask[f][0]<=prefill_window ? prefill_boundary_mask : IO_MASK;
                field_launch_words[f][0]<=convert_words[f];
            end
            if(field_launch_valid[f][0])begin
                field_launch_addr[f][1]<=field_launch_addr[f][0];
                field_launch_mask[f][1]<=field_launch_mask[f][0];
                field_launch_words[f][1]<=field_launch_words[f][0];
            end
        end
        assign conversion_data[f]=convert_words[f][31:0];
        assign reduction_error[f]=|reduce_error_words[f];
        for(genvar h=0;h<IO_WIDTH;h=h+1)begin: input_lane
            logic [31:0] canonical_digit;
            // Validate the entire signed96 row against the latched base first.
            // The full signed32 word reaches the reducer; never truncate raw
            // digits to27 bits, since legal base digits can exceed every P.
            genefer_digit_reduce27_pipe #(.P(P[f]),.PAYLOAD_W(1)) digit_reduce (
                .clk,.rst_n,.in_valid(((state==CONVERT && convert_input_valid) || prefill_accept) && convert_mask[h] && !bad_digit),
                .digit(carry_words[h][31:0]),.payload_in(1'b0),
                .out_valid(reduce_valid_words[f][h]),.out_error(reduce_error_words[f][h]),
                .residue(canonical_digit),.payload_out()
            );
            // Format2 twist consumes ordinary canonical d, not d*R.
            // Preserve the reducer and a registered boundary before NTT RAM.
            // Payload holds on bubbles/reset; reset clears eligibility only.
            always_ff @(posedge clk or negedge rst_n) begin
                if(!rst_n) convert_valid_words[f][h]<=0;
                else convert_valid_words[f][h]<=(state==CONVERT || prefill_window) &&
                    reduce_valid_words[f][h] && !reduce_error_words[f][h];
            end
            always_ff @(posedge clk) begin
                if(rst_n && (state==CONVERT || prefill_window) && reduce_valid_words[f][h] && !reduce_error_words[f][h])
                    convert_words[f][h*32+:32]<=canonical_digit;
            end
        end
        genefer_root_profile27_r2_rom #(.AW(AW),.LANES(NTT_LANES),.P(P[f]),.GENERATOR(G[f])) roots (
            .clk,.rst_n,.start(state==PROFILE_ROM_START),
            .busy(rom_busy[f]),.done(rom_done[f]),.word_valid(rom_valid[f]),
            .word_addr(rom_addr[f]),.word_data(rom_data[f])
        );
        assign ntt_load=(state==CONVERT || prefill_window) && field_write_valid[f];
        assign ntt_read=residue_issue;
        assign addr=(prefill_window || state==CONVERT) ? field_launch_addr[f][1] : AW'(issue_count);
        assign data=field_launch_words[f][1][31:0];
        genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_engine #(.AW(AW),.LANES(NTT_LANES),.HOST_LANES(IO_WIDTH),.P(P[f]),.Q(Q[f])) engine (
            .clk,.rst_n,.load_we(1'b0),.read_en(1'b0),
            .host_addr(addr),.write_data(data),.read_valid(ntt_scalar_valid[f]),.read_data(ntt_data[f]),
            .vector_load_we(ntt_load),.vector_read_en(ntt_read),
            .vector_addr(addr),
            .vector_lane_mask((prefill_window || state==CONVERT) ? field_launch_mask[f][1] : IO_MASK),.vector_write_data(field_launch_words[f][1]),
            .vector_read_valid(ntt_valid[f]),.vector_read_mask(ntt_masks[f]),
            .vector_read_data(ntt_words[f]),.host_error(native_ntt_host_error[f]),
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
                        issue_count<=0; write_count<=0; step<=0;
                        if(fast_eligible)begin state<=NTT_START;profile_hits<=1;end
                        else state<=CONVERT;
                    end
                end
                CONVERT: begin
                    conversion_cycles<=conversion_cycles+1;
                    if(int'(issue_count)<N) issue_count<=issue_count+(AW+1)'(IO_STEP);
                    if(&field_write_valid) begin
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
                    if(prefill_commit && int'(prefill_written)==N-IO_STEP)state<=PREFILL_CHECK;
                end
                PREFILL_CHECK: begin
                    // Last RAM write happened one edge ago: include its registered
                    // host error before publishing the image or pulsing done.
                    carry_cycles<=carry_cycles+1;
                    busy<=0;done<=1;
                    if(prefill_complete && !core_fault && !prefill_fault)begin
                        error<=0;state<=IDLE;
                    end else begin error<=1;state<=FAILED;profile_cache_valid<=0;end
                end
                FAILED: ;
                default: begin state<=FAILED; busy<=0; done<=1; error<=1; profile_cache_valid<=0; end
            endcase
            if(busy && (core_fault || prefill_fault))begin
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

// Autonomous fixed-size squareDup in Z/(base^(2^AW)+1), AW in [1,16].
// Host loads canonical signed32 digits while idle; -1 is the special residue.
// Result remains in carry RAM and can feed the next start without host traffic.
// Reset aborts all work; reload every digit after reset or any reported error.
module genefer_square_core #(
    parameter int AW=16,
    parameter bit DIFDIT=1'b0,
    parameter int NTT_LANES=1,
    parameter bit PREFIX_CARRY=1'b0,
    parameter bit ROOT_CACHE=1'b0,
    parameter bit BANKED_NTT=1'b0,
    parameter int CARRY_LANES=1,
    parameter bit VECTOR_IO=1'b0,
    parameter bit FAST_ARITH=1'b0,
    parameter bit FUSE_INPUT_MONT=1'b0,
    parameter bit STREAM_CARRY=1'b0
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
    output logic [3:0] root_cache_valid,
    output logic [2:0] root_phases_loaded, root_cache_hits
);
    localparam int N=1<<AW;
    localparam int IO_WIDTH=VECTOR_IO ? CARRY_LANES : 1;
    localparam bit USE_HOST_ADAPTER=FAST_ARITH && VECTOR_IO && NTT_LANES==64 && CARRY_LANES==16;
    localparam int IO_STEP=N<IO_WIDTH ? N : IO_WIDTH;
    localparam logic [IO_WIDTH-1:0] IO_MASK={IO_WIDTH{1'b1}} >> (IO_WIDTH-IO_STEP);
    localparam logic [31:0] P[0:2]='{32'd2130706433,32'd2113929217,32'd2013265921};
    localparam logic [31:0] Q[0:2]='{32'd2164260865,32'd2181038081,32'd2281701377};
    localparam logic [31:0] R2[0:2]='{32'd402124772,32'd2111798781,32'd1172168163};
    localparam logic [31:0] G[0:2]='{32'd3,32'd5,32'd31};
    typedef enum logic [3:0] {IDLE, CONVERT, ROOT_START, ROOT_WAIT,
        NTT_START, NTT_WAIT, RESIDUES, CARRY_START, CARRY_WAIT, FAILED} state_t;
    state_t state;
    logic [31:0] base_reg;
    logic double_reg;
    logic [AW:0] issue_count, write_count;
    logic [2:0] step;
    logic [1:0] root_phase, next_root_phase, ntt_op;
    logic carry_load,carry_read,carry_start,carry_valid,carry_busy,carry_done,carry_error;
    logic [AW-1:0] carry_addr;
    logic signed [95:0] carry_input,carry_output,coefficient;
    logic [2:0] conversion_valid,root_valid,root_done,root_error,root_busy;
    logic [2:0] ntt_valid,ntt_busy,ntt_done,ntt_error;
    logic [31:0] conversion_data[0:2],root_data[0:2],ntt_data[0:2];
    logic [AW-1:0] root_addr[0:2];
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
    logic carry_stream_ready,residue_issue;

    assign carry_vector_addr=state==CONVERT ? AW'(issue_count) : AW'(write_count);
    assign convert_input_valid=VECTOR_IO ? carry_vector_valid : carry_valid;
    assign convert_mask=VECTOR_IO ? carry_vector_mask : IO_MASK;
    assign crt_valid=crt_valid_words[0];
    assign crt_ready=&crt_ready_words;
    assign coefficient=coefficient_words[0];
    // Once the streaming carry is ready it cannot stall a legal complete row.
    // Waiting here drains setup before any non-backpressurable CRT input issue.
    assign residue_issue=state==RESIDUES && int'(issue_count)<N && (!STREAM_CARRY || carry_stream_ready);
    for(genvar h=0;h<IO_WIDTH;h=h+1)begin: coefficient_lane
        assign carry_words[h]=VECTOR_IO ? $signed(carry_vector_output[h*96+:96]) : carry_output;
        assign carry_vector_input[h*96+:96]=double_reg ? (coefficient_words[h] <<< 1) : coefficient_words[h];
        genefer_crt3_pipe crt (
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

    assign read_valid=state==IDLE && carry_valid;
    assign read_data=carry_output;
    assign root_phase=step==0 ? 2'd0 : step==1 ? 2'd1 : step==3 ? 2'd2 : 2'd3;
    assign next_root_phase=step==0 ? 2'd1 : step==2 ? 2'd2 : 2'd3;
    assign ntt_op=step==0 || step==4 ? 2'd2 : step==2 ? 2'd1 : 2'd0;
    always_comb begin
        carry_load=0; carry_read=0;
        carry_start=STREAM_CARRY ?
            (state==CONVERT && (&conversion_valid) && int'(write_count)==N-IO_STEP) : state==CARRY_START;
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
    if(VECTOR_IO) begin: use_vector_prefix_carry
      if(STREAM_CARRY)begin: streaming_carry
        genefer_carry_prefix_stream #(.AW(AW),.LANES(IO_WIDTH)) carry_unit (
            .clk,.rst_n,.load_we(carry_load),.read_en(carry_read),.start(carry_start),
            .host_addr(carry_addr),.write_data(carry_input),.size_log2(5'(AW)),.base(base_reg),
            .read_valid(carry_valid),.read_data(carry_output),.busy(carry_busy),
            .done(carry_done),.error(carry_error),.cycles(carry_kernel_cycles),.passes(carry_passes),
            .vector_load_we(1'b0),
            .vector_read_en(state==CONVERT && int'(issue_count)<N),
            .vector_addr(carry_vector_addr),
            .vector_lane_mask(IO_MASK),.vector_write_data(carry_vector_input),
            .vector_read_valid(carry_vector_valid),.vector_read_mask(carry_vector_mask),
            .vector_read_data(carry_vector_output),.host_error(carry_host_error),
            .stream_valid(state==RESIDUES && crt_valid),.stream_ready(carry_stream_ready),
            .stream_addr(carry_vector_addr),.stream_mask(IO_MASK),.stream_data(carry_vector_input)
        );
      end else if(FAST_ARITH)begin: fast_carry
        genefer_carry_prefix_vector_pipe_v2 #(.AW(AW),.LANES(IO_WIDTH)) carry_unit (
            .clk,.rst_n,.load_we(carry_load),.read_en(carry_read),.start(carry_start),
            .host_addr(carry_addr),.write_data(carry_input),.size_log2(5'(AW)),.base(base_reg),
            .read_valid(carry_valid),.read_data(carry_output),.busy(carry_busy),
            .done(carry_done),.error(carry_error),.cycles(carry_kernel_cycles),.passes(carry_passes),
            .vector_load_we(state==RESIDUES && crt_valid),
            .vector_read_en(state==CONVERT && int'(issue_count)<N),
            .vector_addr(carry_vector_addr),
            .vector_lane_mask(IO_MASK),.vector_write_data(carry_vector_input),
            .vector_read_valid(carry_vector_valid),.vector_read_mask(carry_vector_mask),
            .vector_read_data(carry_vector_output),.host_error(carry_host_error)
        );
      end else begin: baseline_carry
        genefer_carry_prefix_vector_ram #(.AW(AW),.LANES(IO_WIDTH)) carry_unit (
            .clk,.rst_n,.load_we(carry_load),.read_en(carry_read),.start(carry_start),
            .host_addr(carry_addr),.write_data(carry_input),.size_log2(5'(AW)),.base(base_reg),
            .read_valid(carry_valid),.read_data(carry_output),.busy(carry_busy),
            .done(carry_done),.error(carry_error),.cycles(carry_kernel_cycles),.passes(carry_passes),
            .vector_load_we(state==RESIDUES && crt_valid),
            .vector_read_en(state==CONVERT && int'(issue_count)<N),
            .vector_addr(carry_vector_addr),
            .vector_lane_mask(IO_MASK),.vector_write_data(carry_vector_input),
            .vector_read_valid(carry_vector_valid),.vector_read_mask(carry_vector_mask),
            .vector_read_data(carry_vector_output),.host_error(carry_host_error)
        );
      end
    end else if(PREFIX_CARRY && CARRY_LANES>1) begin: use_wide_prefix_carry
        genefer_carry_prefix_wide_ram #(.AW(AW),.LANES(CARRY_LANES)) carry_unit (
            .clk,.rst_n,.load_we(carry_load),.read_en(carry_read),.start(carry_start),
            .host_addr(carry_addr),.write_data(carry_input),.size_log2(5'(AW)),.base(base_reg),
            .read_valid(carry_valid),.read_data(carry_output),.busy(carry_busy),
            .done(carry_done),.error(carry_error),.cycles(carry_kernel_cycles),.passes(carry_passes)
        );
    end else if(PREFIX_CARRY) begin: use_prefix_carry
        genefer_carry_prefix #(.AW(AW)) carry_unit (
            .clk,.rst_n,.load_we(carry_load),.read_en(carry_read),.start(carry_start),
            .host_addr(carry_addr),.write_data(carry_input),.size_log2(5'(AW)),.base(base_reg),
            .read_valid(carry_valid),.read_data(carry_output),.busy(carry_busy),
            .done(carry_done),.error(carry_error),.cycles(carry_kernel_cycles),.passes(carry_passes)
        );
    end else begin: use_general_carry
        genefer_carry_fast #(.AW(AW)) carry_unit (
            .clk,.rst_n,.load_we(carry_load),.read_en(carry_read),.start(carry_start),
            .host_addr(carry_addr),.write_data(carry_input),.size_log2(5'(AW)),.base(base_reg),
            .read_valid(carry_valid),.read_data(carry_output),.busy(carry_busy),
            .done(carry_done),.error(carry_error),.cycles(carry_kernel_cycles),.passes(carry_passes)
        );
    end
    if(!VECTOR_IO)begin: no_vector_carry
        assign carry_vector_valid=0;
        assign carry_vector_mask='0;
        assign carry_vector_output='0;
        assign carry_host_error=0;
    end
    if(!STREAM_CARRY || !VECTOR_IO)begin: no_carry_stream
        assign carry_stream_ready=1'b0;
    end
    for(genvar f=0; f<3; f=f+1) begin: field_lane
        logic ntt_load,ntt_root,ntt_read;
        logic [AW-1:0] addr;
        logic [31:0] data;
        assign conversion_valid[f]=convert_valid_words[f][0];
        assign conversion_data[f]=convert_words[f][31:0];
        for(genvar h=0;h<IO_WIDTH;h=h+1)begin: input_lane
            logic [31:0] ordinary;
            assign ordinary=carry_words[h]==-96'sd1 ? P[f]-1 : carry_words[h][31:0];
            if(FUSE_INPUT_MONT)begin: ordinary_register
                // The R^2 phase-zero twist converts this ordinary residue.
                // Keep a register boundary; traffic remains one word/lane/clock.
                always_ff @(posedge clk or negedge rst_n) begin
                    if(!rst_n)begin
                        convert_valid_words[f][h]<=0;
                        convert_words[f][h*32+:32]<=0;
                    end else begin
                        convert_valid_words[f][h]<=state==CONVERT && convert_input_valid && convert_mask[h];
                        if(state==CONVERT && convert_input_valid && convert_mask[h])
                            convert_words[f][h*32+:32]<=ordinary;
                    end
                end
            end else begin: montgomery_registers
              genefer_montgomery_mul32_pipe #(.P(P[f]),.Q(Q[f])) convert (
                .clk,.rst_n,.in_valid(state==CONVERT && convert_input_valid && convert_mask[h]),.lhs(ordinary),.rhs(R2[f]),
                .out_valid(convert_valid_words[f][h]),.result(convert_words[f][h*32+:32])
              );
            end
        end
        if(FUSE_INPUT_MONT)begin: fused_root_profile
          genefer_root_stream32_r2 #(.AW(AW),.P(P[f]),.Q(Q[f]),.GENERATOR(G[f])) roots (
            .clk,.rst_n,.start(state==ROOT_START),.phase(root_phase),
            .busy(root_busy[f]),.done(root_done[f]),.error(root_error[f]),
            .root_valid(root_valid[f]),.root_addr(root_addr[f]),.root_data(root_data[f])
          );
        end else begin: original_root_profile
          genefer_root_stream32 #(.AW(AW),.P(P[f]),.Q(Q[f]),.GENERATOR(G[f])) roots (
            .clk,.rst_n,.start(state==ROOT_START),.phase(root_phase),
            .busy(root_busy[f]),.done(root_done[f]),.error(root_error[f]),
            .root_valid(root_valid[f]),.root_addr(root_addr[f]),.root_data(root_data[f])
          );
        end
        assign ntt_load=state==CONVERT && conversion_valid[f];
        assign ntt_root=state==ROOT_WAIT && root_valid[f];
        assign ntt_read=residue_issue;
        assign addr=state==CONVERT ? AW'(write_count) : state==ROOT_WAIT ? root_addr[f] : AW'(issue_count);
        assign data=state==CONVERT ? conversion_data[f] : root_data[f];
        if(VECTOR_IO)begin: use_vector_ntt
          if(USE_HOST_ADAPTER)begin: adapted_ntt
            genefer_ntt_banked_host_engine #(.AW(AW),.LANES(NTT_LANES),.HOST_LANES(IO_WIDTH),.P(P[f]),.Q(Q[f])) engine (
                .clk,.rst_n,.load_we(1'b0),.root_we(ntt_root),.read_en(1'b0),
                .host_addr(addr),.write_data(data),.read_valid(ntt_scalar_valid[f]),.read_data(ntt_data[f]),
                .vector_load_we(ntt_load),.vector_read_en(ntt_read),
                .vector_addr(state==CONVERT ? AW'(write_count) : AW'(issue_count)),
                .vector_lane_mask(IO_MASK),.vector_write_data(convert_words[f]),
                .vector_read_valid(ntt_valid[f]),.vector_read_mask(ntt_masks[f]),
                .vector_read_data(ntt_words[f]),.host_error(ntt_host_error[f]),
                .start(state==NTT_START),.inverse(1'b0),.dif(step==1),.root_phase,.op(ntt_op),
                .size_log2(5'(AW)),.scale(32'd0),
                .busy(ntt_busy[f]),.done(ntt_done[f]),.error(ntt_error[f]),
                .cycles(),.butterflies(),.data_reads(),.data_writes(),.root_reads(),.wait_cycles()
            );
          end else if(FAST_ARITH)begin: fast_ntt
            genefer_ntt_banked_shared_engine #(.AW(AW),.LANES(IO_WIDTH),.P(P[f]),.Q(Q[f])) engine (
                .clk,.rst_n,.load_we(1'b0),.root_we(ntt_root),.read_en(1'b0),
                .host_addr(addr),.write_data(data),.read_valid(ntt_scalar_valid[f]),.read_data(ntt_data[f]),
                .vector_load_we(ntt_load),.vector_read_en(ntt_read),
                .vector_addr(state==CONVERT ? AW'(write_count) : AW'(issue_count)),
                .vector_lane_mask(IO_MASK),.vector_write_data(convert_words[f]),
                .vector_read_valid(ntt_valid[f]),.vector_read_mask(ntt_masks[f]),
                .vector_read_data(ntt_words[f]),.host_error(ntt_host_error[f]),
                .start(state==NTT_START),.inverse(1'b0),.dif(step==1),.root_phase,.op(ntt_op),
                .size_log2(5'(AW)),.scale(32'd0),
                .busy(ntt_busy[f]),.done(ntt_done[f]),.error(ntt_error[f]),
                .cycles(),.butterflies(),.data_reads(),.data_writes(),.root_reads(),.wait_cycles()
            );
          end else begin: baseline_ntt
            genefer_ntt_banked_vector_engine #(.AW(AW),.LANES(IO_WIDTH),.P(P[f]),.Q(Q[f])) engine (
                .clk,.rst_n,.load_we(1'b0),.root_we(ntt_root),.read_en(1'b0),
                .host_addr(addr),.write_data(data),.read_valid(ntt_scalar_valid[f]),.read_data(ntt_data[f]),
                .vector_load_we(ntt_load),.vector_read_en(ntt_read),
                .vector_addr(state==CONVERT ? AW'(write_count) : AW'(issue_count)),
                .vector_lane_mask(IO_MASK),.vector_write_data(convert_words[f]),
                .vector_read_valid(ntt_valid[f]),.vector_read_mask(ntt_masks[f]),
                .vector_read_data(ntt_words[f]),.host_error(ntt_host_error[f]),
                .start(state==NTT_START),.inverse(1'b0),.dif(step==1),.root_phase,.op(ntt_op),
                .size_log2(5'(AW)),.scale(32'd0),
                .busy(ntt_busy[f]),.done(ntt_done[f]),.error(ntt_error[f]),
                .cycles(),.butterflies(),.data_reads(),.data_writes(),.root_reads(),.wait_cycles()
            );
          end
        end else if(BANKED_NTT && ROOT_CACHE && DIFDIT) begin: use_banked_ntt
            genefer_ntt_banked_modulemem_engine #(.AW(AW),.LANES(NTT_LANES),.P(P[f]),.Q(Q[f])) engine (
                .clk,.rst_n,.load_we(ntt_load),.root_we(ntt_root),.read_en(ntt_read),
                .host_addr(addr),.write_data(data),.read_valid(ntt_valid[f]),.read_data(ntt_data[f]),
                .start(state==NTT_START),.inverse(1'b0),.dif(step==1),.root_phase,.op(ntt_op),
                .size_log2(5'(AW)),.scale(32'd0),
                .busy(ntt_busy[f]),.done(ntt_done[f]),.error(ntt_error[f]),
                .cycles(),.butterflies(),.data_reads(),.data_writes(),.root_reads(),.wait_cycles()
            );
        end else if(ROOT_CACHE && DIFDIT) begin: use_cached_parallel
            genefer_ntt_parallel_cached_engine #(.AW(AW),.LANES(NTT_LANES),.P(P[f]),.Q(Q[f])) engine (
                .clk,.rst_n,.load_we(ntt_load),.root_we(ntt_root),.read_en(ntt_read),
                .host_addr(addr),.write_data(data),.read_valid(ntt_valid[f]),.read_data(ntt_data[f]),
                .start(state==NTT_START),.inverse(1'b0),.dif(step==1),.root_phase,.op(ntt_op),
                .size_log2(5'(AW)),.scale(32'd0),
                .busy(ntt_busy[f]),.done(ntt_done[f]),.error(ntt_error[f]),
                .cycles(),.butterflies(),.data_reads(),.data_writes(),.root_reads(),.wait_cycles()
            );
        end else if(DIFDIT && NTT_LANES>1) begin: use_parallel
            genefer_ntt_parallel_engine #(.AW(AW),.LANES(NTT_LANES),.P(P[f]),.Q(Q[f])) engine (
                .clk,.rst_n,.load_we(ntt_load),.root_we(ntt_root),.read_en(ntt_read),
                .host_addr(addr),.write_data(data),.read_valid(ntt_valid[f]),.read_data(ntt_data[f]),
                .start(state==NTT_START),.inverse(1'b0),.dif(step==1),.op(ntt_op),
                .size_log2(5'(AW)),.scale(32'd0),
                .busy(ntt_busy[f]),.done(ntt_done[f]),.error(ntt_error[f]),
                .cycles(),.butterflies(),.data_reads(),.data_writes(),.root_reads(),.wait_cycles()
            );
        end else if(DIFDIT) begin: use_difdit
            // Natural digits -> DIF bit-reversed spectrum -> pointwise square
            // -> DIT natural digits. No permutation is needed between phases.
            genefer_ntt_difdit_engine #(.AW(AW),.P(P[f]),.Q(Q[f])) engine (
                .clk,.rst_n,.load_we(ntt_load),.root_we(ntt_root),.read_en(ntt_read),
                .host_addr(addr),.write_data(data),.read_valid(ntt_valid[f]),.read_data(ntt_data[f]),
                .start(state==NTT_START),.inverse(1'b0),.dif(step==1),.op(ntt_op),
                .size_log2(5'(AW)),.scale(32'd0),
                .busy(ntt_busy[f]),.done(ntt_done[f]),.error(ntt_error[f]),
                .cycles(),.butterflies(),.data_reads(),.data_writes(),.root_reads(),.wait_cycles()
            );
        end else begin: use_stream
            genefer_ntt_stream_engine #(.AW(AW),.P(P[f]),.Q(Q[f])) engine (
                .clk,.rst_n,.load_we(ntt_load),.root_we(ntt_root),.read_en(ntt_read),
                .host_addr(addr),.write_data(data),.read_valid(ntt_valid[f]),.read_data(ntt_data[f]),
                .start(state==NTT_START),.inverse(1'b0),.op(ntt_op),.size_log2(5'(AW)),.scale(32'd0),
                .busy(ntt_busy[f]),.done(ntt_done[f]),.error(ntt_error[f]),
                .cycles(),.butterflies(),.data_reads(),.data_writes(),.root_reads(),.wait_cycles()
            );
        end
        if(!VECTOR_IO)begin: scalar_boundary
            assign ntt_words[f]=ntt_data[f];
            assign ntt_masks[f]=ntt_valid[f] ? IO_MASK : '0;
            assign ntt_host_error[f]=0;
            assign ntt_scalar_valid[f]=0;
        end
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE; busy<=0; done<=0; error<=0; base_reg<=2; double_reg<=0;
            issue_count<=0; write_count<=0; step<=0;
            cycles<=0; conversion_cycles<=0; root_cycles<=0; ntt_cycles<=0; crt_cycles<=0; carry_cycles<=0;
            root_phases_loaded<=0; root_cache_hits<=0; root_cache_valid<=0;
        end else begin
            done<=0;
            if(busy) cycles<=cycles+1;
            case(state)
                IDLE: if(start) begin
                    error<=0; cycles<=0; conversion_cycles<=0; root_cycles<=0;
                    ntt_cycles<=0; crt_cycles<=0; carry_cycles<=0;
                    root_phases_loaded<=0; root_cache_hits<=0;
                    if(base<2 || base>1000000000 || AW<1 || AW>16 ||
                       (ROOT_CACHE && !DIFDIT) ||
                       (BANKED_NTT && (!ROOT_CACHE || !DIFDIT)) ||
                       (NTT_LANES!=1 && !DIFDIT) ||
                       (CARRY_LANES!=1 && !PREFIX_CARRY) ||
                       (FAST_ARITH && !VECTOR_IO) ||
                       (FUSE_INPUT_MONT && !(FAST_ARITH && VECTOR_IO)) ||
                       (STREAM_CARRY && !(FAST_ARITH && VECTOR_IO && (CARRY_LANES==4 || CARRY_LANES==16))) ||
                       (VECTOR_IO && (!BANKED_NTT || !PREFIX_CARRY || !ROOT_CACHE || !DIFDIT ||
                                      ((NTT_LANES!=CARRY_LANES) && !USE_HOST_ADAPTER) || CARRY_LANES<2)) ||
                       CARRY_LANES<1 || CARRY_LANES>16 || (CARRY_LANES&(CARRY_LANES-1))!=0 ||
                       NTT_LANES<1 || (NTT_LANES>16 && !USE_HOST_ADAPTER) || (NTT_LANES&(NTT_LANES-1))!=0 ||
                       (NTT_LANES>8 && !BANKED_NTT) ||
                       (PREFIX_CARRY && base <= 32'(2*N+4))) begin
                        error<=1; done<=1; state<=FAILED; root_cache_valid<=0;
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
                            if(ROOT_CACHE && root_cache_valid[0]) begin
                                state<=NTT_START; root_cache_hits<=root_cache_hits+1;
                            end else state<=ROOT_START;
                        end
                    end
                    if(bad_digit) begin
                        error<=1; done<=1; busy<=0; state<=FAILED; root_cache_valid<=0;
                    end
                end
                ROOT_START: begin root_cycles<=root_cycles+1; state<=ROOT_WAIT; end
                ROOT_WAIT: begin
                    root_cycles<=root_cycles+1;
                    if(&root_done) begin
                        if(|root_error) begin error<=1; done<=1; busy<=0; state<=FAILED; root_cache_valid<=0; end
                        else begin
                            // The stream has drained, including any unused
                            // upper-half words in compact cached phases.
                            // NTT_START does not assert until the next edge.
                            if(ROOT_CACHE) root_cache_valid[root_phase]<=1'b1;
                            root_phases_loaded<=root_phases_loaded+1;
                            state<=NTT_START;
                        end
                    end
                end
                NTT_START: begin ntt_cycles<=ntt_cycles+1; state<=NTT_WAIT; end
                NTT_WAIT: begin
                    ntt_cycles<=ntt_cycles+1;
                    if(&ntt_done) begin
                        if(|ntt_error) begin error<=1; done<=1; busy<=0; state<=FAILED; root_cache_valid<=0; end
                        else if(step==4) begin issue_count<=0; write_count<=0; state<=RESIDUES; end
                        else begin
                            step<=step+1;
                            if(step==1) state<=NTT_START;
                            else if(ROOT_CACHE && root_cache_valid[next_root_phase]) begin
                                state<=NTT_START; root_cache_hits<=root_cache_hits+1;
                            end else state<=ROOT_START;
                        end
                    end
                end
                RESIDUES: begin
                    crt_cycles<=crt_cycles+1;
                    if(residue_issue) issue_count<=issue_count+(AW+1)'(IO_STEP);
                    if(crt_valid) begin
                        write_count<=write_count+(AW+1)'(IO_STEP);
                        if(int'(write_count)==N-IO_STEP) state<=STREAM_CARRY ? CARRY_WAIT : CARRY_START;
                    end
                end
                CARRY_START: begin carry_cycles<=carry_cycles+1; state<=CARRY_WAIT; end
                CARRY_WAIT: begin
                    carry_cycles<=carry_cycles+1;
                    if(carry_done) begin
                        busy<=0; done<=1; error<=carry_error;
                        state<=carry_error ? FAILED : IDLE;
                        if(carry_error) root_cache_valid<=0;
                    end
                end
                FAILED: ;
                default: begin state<=FAILED; busy<=0; done<=1; error<=1; root_cache_valid<=0; end
            endcase
            if(busy && (carry_host_error || (|ntt_host_error) ||
               (STREAM_CARRY && (carry_error || (carry_done && state!=CARRY_WAIT) ||
                                (state==RESIDUES && crt_valid && !carry_stream_ready)))))begin
                error<=1;done<=1;busy<=0;state<=FAILED;root_cache_valid<=0;
            end
        end
    end
    // synthesis translate_off
    always @(posedge clk) if(rst_n && busy) begin
        if(conversion_valid!=0 && conversion_valid!=3'b111) $fatal(1,"conversion lane skew");
        if(ntt_valid!=0 && ntt_valid!=3'b111) $fatal(1,"residue lane skew");
        if(ntt_done!=0 && ntt_done!=3'b111) $fatal(1,"NTT lane skew");
        if(root_done!=0 && root_done!=3'b111) $fatal(1,"root lane skew");
        for(int f=0;f<3;f=f+1)begin
            if(convert_valid_words[f]!=0 && convert_valid_words[f]!=IO_MASK) $fatal(1,"conversion word skew");
            if(ntt_valid[f] && ntt_masks[f]!=IO_MASK) $fatal(1,"residue mask skew");
        end
        if(crt_valid_words!=0 && crt_valid_words!=IO_MASK) $fatal(1,"CRT word skew");
    end
    // synthesis translate_on
endmodule

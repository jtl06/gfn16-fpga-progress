// Isolated root-pipeline integration from frozen precision-stream core75eb.
// Only the NTT backend/adapter and default lane parameter change.
// Conversion, cached root generation, CRT, carry and outer FSM are unchanged.
// Precision carry keeps canonical digits in signed32 RAM, streams guarded96-bit
// coefficients directly, and retains the external sign-extended96 read contract.
// Autonomous fixed-size squareDup in Z/(base^(2^AW)+1), AW in [1,16].
// Host loads canonical signed32 digits while idle; -1 is the special residue.
// Result remains in carry RAM and can feed the next start without host traffic.
// Reset aborts all work; reload every digit after reset or any reported error.
module genefer_square_core27_stream_rootpipe #(
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
    output logic [3:0] root_cache_valid,
    output logic [2:0] root_phases_loaded, root_cache_hits
);
    // Explicit atomic profile: three27-bit fields, radix2^32, cached DIF/DIT,
    // sixteen-wide conversion/CRT/carry, sixteen or64 arithmetic lanes only.
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
    typedef enum logic [3:0] {IDLE, CONVERT, ROOT_START, ROOT_WAIT,
        NTT_START, NTT_WAIT, RESIDUES, CARRY_START, CARRY_WAIT, FAILED} state_t;
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
        logic ntt_load,ntt_root,ntt_read;
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
            genefer_montgomery_mul27_sparse_pipe #(.P(P[f]),.Q(Q[f])) convert (
                .clk,.rst_n,.in_valid(state==CONVERT && reduce_valid_words[f][h] && !reduce_error_words[f][h]),
                .lhs(canonical_digit),.rhs(R2[f]),
                .out_valid(convert_valid_words[f][h]),.result(convert_words[f][h*32+:32])
            );
        end
        genefer_root_stream27_stream_cached #(.AW(AW),.P(P[f]),.Q(Q[f]),.GENERATOR(G[f])) roots (
            .clk,.rst_n,.start(state==ROOT_START),.phase(root_phase),
            .busy(root_busy[f]),.done(root_done[f]),.error(root_error[f]),
            .root_valid(root_valid[f]),.root_addr(root_addr[f]),.root_data(root_data[f])
        );
        assign ntt_load=state==CONVERT && conversion_valid[f];
        assign ntt_root=state==ROOT_WAIT && root_valid[f];
        assign ntt_read=residue_issue;
        assign addr=state==CONVERT ? AW'(write_count) : state==ROOT_WAIT ? root_addr[f] : AW'(issue_count);
        assign data=state==CONVERT ? conversion_data[f] : root_data[f];
            genefer_ntt_banked27_host_rootpipe_engine #(.AW(AW),.LANES(NTT_LANES),.HOST_LANES(IO_WIDTH),.P(P[f]),.Q(Q[f])) engine (
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
                       (NTT_LANES!=16 && NTT_LANES!=64) || base <= 32'(2*N+4)) begin
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
                        if(int'(write_count)==N-IO_STEP) state<=CARRY_WAIT;
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
            if(busy && (carry_host_error || (|ntt_host_error) || (|reduction_error) ||
               carry_error || (carry_done && state!=CARRY_WAIT) ||
               (state==RESIDUES && crt_valid && !carry_stream_ready)))begin
                error<=1;done<=1;busy<=0;state<=FAILED;root_cache_valid<=0;
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
        if(root_done!=0 && root_done!=3'b111) $fatal(1,"root lane skew");
        for(int f=0;f<3;f=f+1)begin
            if(reduce_valid_words[f]!=0 && reduce_valid_words[f]!=IO_MASK) $fatal(1,"reduction word skew");
            if(convert_valid_words[f]!=0 && convert_valid_words[f]!=IO_MASK) $fatal(1,"conversion word skew");
            if(ntt_valid[f] && ntt_masks[f]!=IO_MASK) $fatal(1,"residue mask skew");
        end
        if(crt_valid_words!=0 && crt_valid_words!=IO_MASK) $fatal(1,"CRT word skew");
    end
    // synthesis translate_on
endmodule
// Fixed-size N=2^AW root-table generator, one output per cycle after start.
// Four interleaved power sequences hide the four-cycle multiplier feedback.
// phase 0: psi^i*R; 1: omega^i*R; 2: omega^-i*R;
// phase 3: psi^-i/N (ordinary residues for fused inverse/postconversion).
// All powers below are elaboration-time constants, not hardware dividers.
module genefer_root_stream27_stream_cached #(
    parameter int AW=16,
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] Q=32'd4190109697,
    parameter logic [31:0] GENERATOR=32'd3
) (
    input logic clk, rst_n, start,
    input logic [1:0] phase,
    output logic busy, done, error, root_valid,
    output logic [AW-1:0] root_addr,
    output logic [31:0] root_data
);
    function automatic logic [31:0] cmul(input logic [31:0] x, y);
        logic [63:0] wide;
        begin wide=64'(x)*64'(y); cmul=32'(wide%64'(P)); end
    endfunction
    function automatic logic [31:0] cpow(input logic [31:0] x, exponent);
        logic [31:0] result, power;
        begin
            result=1; power=x;
            for(int k=0;k<32;k=k+1) begin
                if(exponent[k]) result=cmul(result,power);
                power=cmul(power,power);
            end
            cpow=result;
        end
    endfunction
    localparam int N=1<<AW;
    localparam logic [31:0] R=32'(64'h100000000%64'(P));
    localparam logic [31:0] PSI=cpow(GENERATOR,(P-1)/32'(2*N));
    localparam logic [31:0] OMEGA=cmul(PSI,PSI);
    localparam logic [31:0] IPSI=cpow(PSI,P-2);
    localparam logic [31:0] IOMEGA=cpow(OMEGA,P-2);
    localparam logic [31:0] IN=cpow(32'(N),P-2);
    localparam logic [31:0] S0[0:3]='{R,cmul(R,PSI),cmul(R,cpow(PSI,2)),cmul(R,cpow(PSI,3))};
    localparam logic [31:0] S1[0:3]='{R,cmul(R,OMEGA),cmul(R,cpow(OMEGA,2)),cmul(R,cpow(OMEGA,3))};
    localparam logic [31:0] S2[0:3]='{R,cmul(R,IOMEGA),cmul(R,cpow(IOMEGA,2)),cmul(R,cpow(IOMEGA,3))};
    localparam logic [31:0] S3[0:3]='{IN,cmul(IN,IPSI),cmul(IN,cpow(IPSI,2)),cmul(IN,cpow(IPSI,3))};
    localparam logic [31:0] STEP[0:3]='{cmul(R,cpow(PSI,4)),cmul(R,cpow(OMEGA,4)),
                                                      cmul(R,cpow(IOMEGA,4)),cmul(R,cpow(IPSI,4))};
    logic [AW:0] index;
    logic [1:0] phase_reg;
    logic [31:0] seed, word_value, feedback;
    logic feedback_valid, multiply;
    always_comb begin
        case(phase_reg)
            0: seed=S0[index[1:0]];
            1: seed=S1[index[1:0]];
            2: seed=S2[index[1:0]];
            default: seed=S3[index[1:0]];
        endcase
    end
    assign word_value=int'(index)<4 ? seed : feedback;
    // Last four outputs need no successor; the pipeline is empty when done.
    assign multiply=busy && (int'(index)+4<N);
    genefer_montgomery_mul32_pipe #(.P(P),.Q(Q)) powers (
        .clk,.rst_n,.in_valid(multiply),.lhs(word_value),.rhs(STEP[phase_reg]),
        .out_valid(feedback_valid),.result(feedback)
    );
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            busy<=0; done<=0; error<=0; root_valid<=0;
            root_addr<=0; root_data<=0; phase_reg<=0; index<=0;
        end else begin
            done<=0; root_valid<=0;
            if(!busy) begin
                if(start) begin busy<=1; error<=0; index<=0; phase_reg<=phase; end
            end else begin
                root_valid<=1; root_addr<=AW'(index); root_data<=word_value;
                if(int'(index)>=4 && !feedback_valid) error<=1;
                if(int'(index)==N-1) begin busy<=0; done<=1; end
                else index<=index+1;
            end
        end
    end
endmodule

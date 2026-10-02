// Isolated W-bit-precision reciprocal-divider experiment. Frozen scan/feedback protocol retained.
// Reuses genefer_carry_stream_scan_pipe from frozen stream_pipe source.
// Ordered coefficient stream remains II1 after 97 setup clocks, without staging RAM.
// No-bubble clocks: 2*ceil(N/LANES)+135+3*log2(LANES).
module genefer_carry_prefix_stream_precision_emit #(parameter int AW=16, LANES=4) (
    input logic clk, rst_n, load_we, read_en, start,
    input logic [AW-1:0] host_addr,
    input logic signed [95:0] write_data,
    input logic [4:0] size_log2,
    input logic [31:0] base,
    input logic vector_load_we, vector_read_en,
    input logic [AW-1:0] vector_addr,
    input logic [LANES-1:0] vector_lane_mask,
    input logic [LANES*96-1:0] vector_write_data,
    input logic stream_valid,
    output logic stream_ready,
    input logic [AW-1:0] stream_addr,
    input logic [LANES-1:0] stream_mask,
    input logic [LANES*96-1:0] stream_data,
    output logic vector_read_valid, host_error,
    output logic [LANES-1:0] vector_read_mask,
    output logic [LANES*96-1:0] vector_read_data,
    output logic read_valid,
    output logic signed [95:0] read_data,
    output logic busy, done, error,
    output logic [63:0] cycles,
    output logic [6:0] passes,
    // Passive descriptor for the actual canonical digit-RAM commit edge.
    output logic emit_commit_valid,
    output logic [AW-1:0] emit_commit_addr,
    output logic [LANES-1:0] emit_commit_mask,
    output logic [LANES*96-1:0] emit_commit_data
);
    localparam int LGW=$clog2(LANES);
    localparam int RW=AW>LGW ? AW-LGW : 1;
    localparam int DEPTH=AW>LGW ? (1<<(AW-LGW)) : 1;
    localparam logic [14:0] IDENTITY={3'd4,3'd3,3'd2,3'd1,3'd0};
    typedef enum logic [3:0] {IDLE,BOUND,RECIP,SPLIT,WRAP,WRAP_WAIT,SOLVE,EMIT} state_t;
    state_t state;
    logic [AW:0] n,groups,issue,received,written;
    logic [4:0] lg;
    logic [31:0] base_reg;
    logic [31:0] bound_base_minus1,bound_lo_sq,bound_hi_sq,bound_cross;
    logic [63:0] bound_square;
    logic bound_valid;
    logic [95:0] bound,reciprocal;
    logic [31:0] reciprocal_rem;
    logic [32:0] reciprocal_shift;
    logic [6:0] reciprocal_round;
    logic small_d,special;
    logic [LGW-1:0] host_bank_d;
    logic [LANES-1:0] first_valid,split_valid;
    logic signed [95:0] coeff_q[0:LANES-1],first_q[0:LANES-1],split_q[0:LANES-1];
    logic signed [32:0] small_q[0:LANES-1],stream_s[0:LANES-1],s0,s1,previous_q,previous_previous_q;
    logic [31:0] first_r[0:LANES-1],split_r0[0:LANES-1],split_r1[0:LANES-1];
    logic [31:0] first_r00,first_r01,first_r10,previous_r1;
    logic [14:0] suffix,transfer_all;
    logic [14:0] b_prefix[0:LANES-1];
    logic [2:0] current_carry,initial_carry,solved_carry,next_group;
    logic found_carry,multiple_carries;
    logic [2:0] lane_in[0:LANES-1],lane_out[0:LANES-1];
    logic signed [33:0] emit_base,lane_total[0:LANES-1],lane_digit[0:LANES-1];
    logic [LANES-1:0] mem_en,mem_we,small_en,small_we;
    logic [RW-1:0] mem_addr[0:LANES-1],small_addr[0:LANES-1];
    logic emit_valid;
    logic [RW-1:0] emit_row;
    logic signed [95:0] emit_data[0:LANES-1];
    logic signed [95:0] mem_data[0:LANES-1];
    logic signed [32:0] small_data[0:LANES-1];
    logic leaf_valid,digit_valid;
    logic [RW-1:0] leaf_row,digit_row;
    logic signed [32:0] leaf_small[0:LANES-1],digit_small[0:LANES-1];
    logic [679:0] thresholds;
    logic summary_input_valid,summary_output_valid,summary_wrap;
    logic [AW:0] summary_row;
    logic [AW+1:0] summary_payload;
    logic [LANES*33-1:0] summary_values,emit_values;
    logic [LANES-1:0] summary_mask;
    logic [RW+LANES*33-1:0] emit_payload;
    logic prefix_valid;
    logic [LANES*15-1:0] summary_prefix,emit_prefix;
    logic signed [32:0] summary_s[0:LANES-1];
    logic [2:0] digit_in[0:LANES-1],digit_out[0:LANES-1];
    integer last_active;
    logic vector_request,vector_ok,host_write_ok,stream_fire,stream_ok;
    logic [LANES-1:0] active_mask;
    logic signed [95:0] stream_word[0:LANES-1];
    logic signed [31:0] digit_q[0:LANES-1];
    assign stream_ready=rst_n && state==SPLIT && issue<groups;
    assign stream_fire=stream_valid && stream_ready;
    always_comb begin
        stream_ok=stream_addr==AW'(issue<<LGW) && stream_mask==active_mask;
        host_write_ok=vector_request ? 1'b1 : write_data=={{64{write_data[31]}},write_data[31:0]};
        for(int g=0;g<LANES;g=g+1)begin
            if(active_mask[g] && (stream_word[g]<-$signed(bound) || stream_word[g]>$signed(bound)))
                stream_ok=0;
            if(vector_request && effective_mask[g] &&
               $signed(vector_write_data[g*96+:96]) != $signed({{64{vector_write_data[g*96+31]}},vector_write_data[g*96+:32]}))
                host_write_ok=0;
        end
    end
    logic [31:0] host_n;
    logic [LANES-1:0] effective_mask;
    assign vector_request=vector_load_we || vector_read_en;
    assign host_n=(size_log2>=1 && int'(size_log2)<=AW) ? (32'd1<<size_log2) : 32'd0;
    assign vector_ok=host_n!=0 && (32'(vector_addr)&32'(LANES-1))==0 && 32'(vector_addr)<host_n;
    for(genvar h=0;h<LANES;h=h+1)begin: host_lane
        assign effective_mask[h]=vector_lane_mask[h] && (32'(vector_addr)+32'(h))<host_n;
        assign vector_read_data[h*96+:96]=coeff_q[h];
        assign coeff_q[h]={{64{digit_q[h][31]}},digit_q[h]};
        assign stream_word[h]=$signed(stream_data[h*96+:96]);
        assign active_mask[h]=h<int'(n);
    end

    function automatic logic [14:0] compose(input logic [14:0] first,second);
        for(int k=0;k<5;k=k+1)compose[k*3+:3]=second[first[k*3+:3]*3+:3];
    endfunction
    assign read_data=coeff_q[host_bank_d];
    // Bound setup uses spare reciprocal clocks, with no extra busy cycles.
    // These arithmetic registers deliberately have no reset; bound_valid
    // controls whether the result may be consumed.
    always_ff @(posedge clk)begin
        if(rst_n && state==IDLE && start)bound_base_minus1<=base-32'd1;
        if(rst_n && state==BOUND)begin
            bound_lo_sq<=bound_base_minus1[15:0]*bound_base_minus1[15:0];
            bound_hi_sq<=bound_base_minus1[31:16]*bound_base_minus1[31:16];
            bound_cross<=bound_base_minus1[15:0]*bound_base_minus1[31:16];
        end
        if(rst_n && state==RECIP && reciprocal_round==0)
            bound_square<={32'b0,bound_lo_sq}+{15'b0,bound_cross,17'b0}+{bound_hi_sq,32'b0};
    end
    assign reciprocal_shift={reciprocal_rem,1'b0};
    assign last_active=(int'(n)>=2 && int'(n)<LANES) ? int'(n)-1 : LANES-1;

    assign emit_base=$signed({2'b0,base_reg});
    assign next_group=b_prefix[LANES-1][current_carry*3+:3];
    // Thresholds implement s+k-2 < {-b,0,b,2b} as s < threshold.
    // They are stable before the first streamed row reaches the scan pipes.
    always_ff @(posedge clk)if(rst_n && state==BOUND)begin
        for(int k=0;k<5;k=k+1)begin
            thresholds[(k*4+0)*34+:34]<=-$signed({2'b0,base_reg})-34'(k)+34'sd2;
            thresholds[(k*4+1)*34+:34]<=-34'(k)+34'sd2;
            thresholds[(k*4+2)*34+:34]<=$signed({2'b0,base_reg})-34'(k)+34'sd2;
            thresholds[(k*4+3)*34+:34]<=($signed({2'b0,base_reg})<<<1)-34'(k)+34'sd2;
        end
    end
    genefer_carry_stream_scan_pipe #(.LANES(LANES),.PAYLOAD_W(AW+2)) summary_scan (
        .clk,.rst_n,.in_valid(summary_input_valid),.values(summary_values),.mask(summary_mask),
        .thresholds,.payload_in({summary_wrap,summary_row}),.out_valid(summary_output_valid),
        .prefix(summary_prefix),.payload_out(summary_payload)
    );
    genefer_carry_stream_scan_pipe #(.LANES(LANES),.PAYLOAD_W(RW+LANES*33)) emit_scan (
        .clk,.rst_n,.in_valid(leaf_valid),.values(emit_values),.mask(active_mask),
        .thresholds,.payload_in({leaf_row,emit_values}),.out_valid(prefix_valid),
        .prefix(emit_prefix),.payload_out(emit_payload)
    );
    always_comb begin
        found_carry=0;multiple_carries=0;solved_carry=2;
        for(int k=0;k<5;k=k+1)if(k+int'(transfer_all[k*3+:3])==4)begin
            if(found_carry)multiple_carries=1;
            found_carry=1;solved_carry=3'(k);
        end
    end
    for(genvar g=0;g<LANES;g=g+1)begin: lane
        genefer_sp_ram #(.WIDTH(32),.AW(RW),.DEPTH(DEPTH)) digit_ram (
            .clk,.rst_n,.en(mem_en[g]),.write_en(mem_we[g]),.addr(mem_addr[g]),
            .write_data(mem_data[g][31:0]),.read_data(digit_q[g])
        );
        genefer_sp_ram #(.WIDTH(33),.AW(RW),.DEPTH(DEPTH)) intermediate_ram (
            .clk,.rst_n,.en(small_en[g]),.write_en(small_we[g]),.addr(small_addr[g]),
            .write_data(small_data[g]),.read_data(small_q[g])
        );
        logic signed [32:0] predecessor_r1,predecessor_q;
        logic signed [77:0] first_q_narrow;
        logic signed [47:0] split_q_narrow;
        assign first_q[g]={{18{first_q_narrow[77]}},first_q_narrow};
        assign split_q[g]={{48{split_q_narrow[47]}},split_q_narrow};
        if(g==0)assign predecessor_r1=$signed({1'b0,previous_r1});
        else assign predecessor_r1=$signed({1'b0,split_r1[g-1]});
        if(g==0)assign predecessor_q=previous_previous_q;
        else if(g==1)assign predecessor_q=previous_q;
        else assign predecessor_q=33'(split_q[g-2]);
        assign stream_s[g]=$signed({1'b0,split_r0[g]})+predecessor_r1+predecessor_q;
        assign summary_values[g*33+:33]=summary_s[g];
        assign emit_values[g*33+:33]=leaf_small[g];
        assign b_prefix[g]=emit_prefix[g*15+:15];
        if(g==0)assign lane_in[g]=current_carry;
        else assign lane_in[g]=b_prefix[g-1][current_carry*3+:3];
        assign lane_out[g]=b_prefix[g][current_carry*3+:3];
        assign lane_total[g]=34'(digit_small[g])+$signed({31'b0,digit_in[g]})-34'sd2;
        always_comb begin
            case(digit_out[g])
                0:lane_digit[g]=lane_total[g]+(emit_base<<<1);
                1:lane_digit[g]=lane_total[g]+emit_base;
                2:lane_digit[g]=lane_total[g];
                3:lane_digit[g]=lane_total[g]-emit_base;
                default:lane_digit[g]=lane_total[g]-(emit_base<<<1);
            endcase
        end
        genefer_div_recip_precision #(.MAG_W(77),.PAYLOAD_W(1)) first_div (
            .clk,.rst_n,.in_valid(stream_fire && stream_ok && active_mask[g]),.value(stream_word[g][77:0]),
            .base(base_reg),.reciprocal,.payload_in(1'b0),.out_valid(first_valid[g]),
            .quotient(first_q_narrow),.remainder(first_r[g]),.payload_out()
        );
        genefer_div_recip_precision #(.MAG_W(47),.PAYLOAD_W(32)) second_div (
            .clk,.rst_n,.in_valid(state==SPLIT && first_valid[g]),.value(first_q[g][47:0]),
            .base(base_reg),.reciprocal,.payload_in(first_r[g]),.out_valid(split_valid[g]),
            .quotient(split_q_narrow),.remainder(split_r1[g]),.payload_out(split_r0[g])
        );
        always_comb begin
            mem_en[g]=0;mem_we[g]=0;mem_addr[g]=RW'(host_addr>>LGW);mem_data[g]=write_data;
            small_en[g]=0;small_we[g]=0;small_addr[g]=0;small_data[g]=0;
            case(state)
                IDLE:if(!start)begin
                    // Any vector request wins arbitration, including invalid ones.
                    // Zero effective mask is accepted (read-valid with mask0).
                    if(vector_request)begin
                        if(vector_ok && (!vector_load_we || host_write_ok))begin
                            mem_en[g]=effective_mask[g];mem_we[g]=vector_load_we;
                            mem_addr[g]=RW'(vector_addr>>LGW);
                            mem_data[g]=$signed(vector_write_data[g*96+:96]);
                        end
                    end else if((int'(host_addr)&(LANES-1))==g)begin
                        mem_en[g]=(load_we ? host_write_ok : read_en);mem_we[g]=load_we;
                    end
                end
                SPLIT:begin
                    if(split_valid[0] && g<int'(n) && ((int'(received)<<LGW)+g)>=2)begin
                        small_en[g]=1;small_we[g]=1;small_addr[g]=RW'(received);small_data[g]=stream_s[g];
                    end
                end
                WRAP:if(g<2)begin
                    small_en[g]=1;small_we[g]=1;small_addr[g]=0;small_data[g]=g==0 ? s0 : s1;
                end
                EMIT:begin
                    small_en[g]=issue<groups && g<int'(n);small_addr[g]=RW'(issue);
                    if(emit_valid && g<int'(n))begin
                        mem_en[g]=1;mem_we[g]=1;mem_addr[g]=emit_row;
                        mem_data[g]=emit_data[g];
                    end
                end
                default:;
            endcase
        end
        always_ff @(posedge clk)begin
            // RAM capture, registered half-comparisons, pipelined prefix scan,
            // carry selection and digit arithmetic are separate II1 stages.
            if(rst_n && state==EMIT && small_d)begin
                leaf_small[g]<=small_q[g];
            end
            if(rst_n && state==EMIT && prefix_valid)begin
                digit_small[g]<=emit_payload[g*33+:33];digit_in[g]<=lane_in[g];digit_out[g]<=lane_out[g];
            end
            if(rst_n && ((state==SPLIT && split_valid[0]) || state==WRAP))begin
                summary_s[g]<=state==WRAP ? (g==0 ? s0 : s1) : stream_s[g];
                summary_mask[g]<=state==WRAP ? g<2 : (g<int'(n) && ((int'(received)<<LGW)+g)>=2);
            end
            if(rst_n && state==EMIT && digit_valid)
                emit_data[g]<=special ? (digit_row==0 && g==0 ? -96'sd1 : 96'sd0) : $signed({62'b0,lane_digit[g]});
        end
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;busy<=0;done<=0;error<=0;read_valid<=0;cycles<=0;passes<=0;
            n<=0;groups<=0;issue<=0;received<=0;written<=0;lg<=0;base_reg<=2;bound<=0;bound_valid<=0;
            reciprocal<=0;reciprocal_rem<=0;reciprocal_round<=0;small_d<=0;host_bank_d<=0;
            emit_valid<=0;emit_row<=0;leaf_valid<=0;digit_valid<=0;leaf_row<=0;digit_row<=0;
            vector_read_valid<=0;vector_read_mask<=0;host_error<=0;
            first_r00<=0;first_r01<=0;first_r10<=0;previous_r1<=0;previous_q<=0;previous_previous_q<=0;
            summary_input_valid<=0;summary_wrap<=0;summary_row<=0;transfer_all<=IDENTITY;
            s0<=0;s1<=0;suffix<=IDENTITY;current_carry<=2;initial_carry<=2;special<=0;
        end else begin
            summary_input_valid<=(state==SPLIT && split_valid[0]) || state==WRAP;
            if((state==SPLIT && split_valid[0]) || state==WRAP)begin
                summary_wrap<=state==WRAP;summary_row<=received;
            end
            if(summary_output_valid && (state==SPLIT || state==WRAP_WAIT))begin
                if(summary_payload[AW+1])begin
                    transfer_all<=compose(summary_prefix[(LANES-1)*15+:15],suffix);
                    state<=SOLVE;
                end else begin
                    suffix<=compose(suffix,summary_prefix[(LANES-1)*15+:15]);
                    if(summary_payload[AW:0]==groups-1)state<=WRAP;
                end
            end
            done<=0;read_valid<=state==IDLE && !start && !vector_request && read_en && !load_we;
            vector_read_valid<=state==IDLE && !start && vector_read_en && !vector_load_we && vector_ok;
            vector_read_mask<=state==IDLE && !start && vector_read_en && !vector_load_we && vector_ok ? effective_mask : '0;
            host_error<=state==IDLE && !start && ((vector_request && (!vector_ok || (vector_load_we && !host_write_ok))) || (!vector_request && load_we && !host_write_ok));
            if(state==IDLE)host_bank_d<=LGW'(host_addr);
            small_d<=state==EMIT && issue<groups;
            leaf_valid<=state==EMIT && small_d;
            digit_valid<=state==EMIT && prefix_valid;
            emit_valid<=state==EMIT && digit_valid;
            if(state==EMIT && small_d)leaf_row<=RW'(written);
            if(state==EMIT && prefix_valid)digit_row<=emit_payload[LANES*33+:RW];
            if(state==EMIT && digit_valid)emit_row<=digit_row;
            if(busy)cycles<=cycles+1;
            case(state)
                IDLE:if(start)begin
                    cycles<=0;error<=0;passes<=0;bound_valid<=0;
                    if(size_log2<1 || size_log2>16 || int'(size_log2)>AW || base>1000000000 || base<=(32'd2<<size_log2)+32'd4 ||
                       LANES<2 || LANES>16 || (LANES&(LANES-1))!=0)begin done<=1;error<=1;end
                    else begin
                        n<=(AW+1)'(1)<<size_log2;groups<=(AW+1)'(((32'd1<<size_log2)+32'(LANES)-1)>>LGW);
                        lg<=size_log2;base_reg<=base;busy<=1;state<=BOUND;issue<=0;received<=0;written<=0;
                        suffix<=IDENTITY;reciprocal<=0;reciprocal_rem<=1;reciprocal_round<=0;
                        previous_r1<=0;previous_q<=0;previous_previous_q<=0;passes<=1;special<=0;
                    end
                end
                BOUND:state<=RECIP;
                RECIP:begin
                    reciprocal_round<=reciprocal_round+1;
                    if(reciprocal_round==1)begin
                        bound<=96'(bound_square)<<(int'(lg)+1);bound_valid<=1;
                    end
                    if(reciprocal_shift>={1'b0,base_reg})begin
                        reciprocal_rem<=32'(reciprocal_shift-{1'b0,base_reg});reciprocal<={reciprocal[94:0],1'b1};
                    end else begin reciprocal_rem<=reciprocal_shift[31:0];reciprocal<={reciprocal[94:0],1'b0};end
                    if(reciprocal_round==95)begin
                        if(bound_valid)state<=SPLIT;
                        else begin error<=1;done<=1;busy<=0;state<=IDLE;end
                    end
                end
                SPLIT:begin
                    if(stream_fire && stream_ok)issue<=issue+1;
                    if(split_valid[0])begin
                        received<=received+1;
                        previous_previous_q<=33'(split_q[last_active-1]);previous_q<=33'(split_q[last_active]);previous_r1<=split_r1[last_active];
                        if(received==0)begin first_r00<=split_r0[0];first_r01<=split_r0[1];first_r10<=split_r1[0];end
                        if(received==groups-1)begin
                            s0<=$signed({1'b0,(received==0 ? split_r0[0] : first_r00)})-$signed({1'b0,split_r1[last_active]})-33'(split_q[last_active-1]);
                            s1<=$signed({1'b0,(received==0 ? split_r0[1] : first_r01)})+$signed({1'b0,(received==0 ? split_r1[0] : first_r10)})-33'(split_q[last_active]);

                        end
                    end
                    if(stream_fire && !stream_ok)begin
                        error<=1;done<=1;busy<=0;state<=IDLE;
                    end
                end
                WRAP:state<=WRAP_WAIT;
                WRAP_WAIT:;
                SOLVE:begin
                    initial_carry<=solved_carry;current_carry<=solved_carry;special<=!found_carry;
                    issue<=0;written<=0;passes<=2;state<=EMIT;
                    if(multiple_carries)begin error<=1;done<=1;busy<=0;state<=IDLE;end
                end
                EMIT:begin
                    if(issue<groups)issue<=issue+1;
                    if(small_d)written<=written+1;
                    if(prefix_valid)current_carry<=next_group;
                    // done follows the last actual RAM commit, never just
                    // the last computed digit. Its carry is already registered.
                    if(emit_valid && emit_row==RW'(groups-1))begin
                        busy<=0;done<=1;state<=IDLE;
                        if(!special && int'(current_carry)+int'(initial_carry)!=4)error<=1;
                    end
                end
                default:begin busy<=0;done<=1;error<=1;state<=IDLE;end
            endcase
        end
    end
    // No new state or backpressure: these are the same words/edge as digit_ram.
    // Consumers must retain final carry-error ownership until their own drain.
    assign emit_commit_valid=rst_n && state==EMIT && emit_valid;
    assign emit_commit_addr=AW'(emit_row)<<LGW;
    assign emit_commit_mask=emit_commit_valid ? active_mask : '0;
    for(genvar e=0;e<LANES;e=e+1)begin: commit_descriptor
        assign emit_commit_data[e*96+:96]={{64{emit_data[e][31]}},emit_data[e][31:0]};
    end

    // synthesis translate_off
    always @(posedge clk)if(rst_n && state==SPLIT)begin
        if(!bound_valid)$fatal(1,"bound not ready before SPLIT");
        if(bound!=(96'(64'(base_reg-32'd1)*64'(base_reg-32'd1))<<(int'(lg)+1)))
            $fatal(1,"bound setup value mismatch");
        for(int g=0;g<LANES;g=g+1)
            if(first_valid[g] && first_q[g] != {{48{first_q[g][47]}},first_q[g][47:0]})
                $fatal(1,"first quotient outside signed48 range");
        for(int g=0;g<LANES;g=g+1)
            if(split_valid[g] != (split_valid[0] && g<int'(n)))$fatal(1,"wide split lane skew");
    end
    always @(posedge clk)if(emit_commit_valid)begin
        for(int e=0;e<LANES;e=e+1)if(emit_commit_mask[e])begin
            if(!mem_en[e] || !mem_we[e] || mem_addr[e]!=emit_row || mem_data[e]!=emit_data[e])
                $fatal(1,"T5_EMIT_NOT_ACTUAL_COMMIT");
            if(emit_data[e]!=$signed(emit_commit_data[e*96+:96]))
                $fatal(1,"T5_EMIT_SIGNED32_REPRESENTATION");
        end
    end
    // synthesis translate_on
endmodule

// Separate pipelined-normalization candidate; frozen narrow math/domain unchanged.
// Vector-host banked bounded-domain prefix carry. LANES is power-of-two [2,16].
// Math is frozen wide-v3; idle vector host access is the only difference.
// Coefficient and signed33 intermediate RAM each have LANES physical banks.
// Each group uses a parallel prefix tree, not a serial carry chain.
module genefer_carry_prefix_vector_pipe #(parameter int AW=16, LANES=4) (
    input logic clk, rst_n, load_we, read_en, start,
    input logic [AW-1:0] host_addr,
    input logic signed [95:0] write_data,
    input logic [4:0] size_log2,
    input logic [31:0] base,
    input logic vector_load_we, vector_read_en,
    input logic [AW-1:0] vector_addr,
    input logic [LANES-1:0] vector_lane_mask,
    input logic [LANES*96-1:0] vector_write_data,
    output logic vector_read_valid, host_error,
    output logic [LANES-1:0] vector_read_mask,
    output logic [LANES*96-1:0] vector_read_data,
    output logic read_valid,
    output logic signed [95:0] read_data,
    output logic busy, done, error,
    output logic [63:0] cycles,
    output logic [6:0] passes
);
    localparam int LGW=$clog2(LANES);
    localparam int RW=AW>LGW ? AW-LGW : 1;
    localparam int DEPTH=AW>LGW ? (1<<(AW-LGW)) : 1;
    localparam logic [14:0] IDENTITY={3'd4,3'd3,3'd2,3'd1,3'd0};
    typedef enum logic [3:0] {IDLE,BOUND,RECIP,SPLIT,WRAP,SOLVE,EMIT} state_t;
    state_t state;
    logic [AW:0] n,groups,issue,received,written;
    logic [4:0] lg;
    logic [31:0] base_reg;
    logic [63:0] base_square;
    logic [95:0] bound,reciprocal;
    logic [31:0] reciprocal_rem;
    logic [32:0] reciprocal_shift;
    logic [6:0] reciprocal_round;
    logic input_d,small_d,special;
    logic [LGW-1:0] host_bank_d;
    logic [LANES-1:0] first_valid,split_valid;
    logic signed [95:0] coeff_q[0:LANES-1],first_q[0:LANES-1],split_q[0:LANES-1];
    logic signed [32:0] small_q[0:LANES-1],stream_s[0:LANES-1],s0,s1,previous_q,previous_previous_q;
    logic [31:0] first_r[0:LANES-1],split_r0[0:LANES-1],split_r1[0:LANES-1];
    logic [31:0] first_r00,first_r01,first_r10,previous_r1;
    logic [14:0] suffix,transfer_all;
    logic [14:0] a_transfer[0:LANES-1],a_prefix[0:LANES-1],b_transfer[0:LANES-1],b_prefix[0:LANES-1];
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
    logic [14:0] raw_leaf[0:LANES-1];
    logic [2:0] digit_in[0:LANES-1],digit_out[0:LANES-1];
    integer last_active;
    logic vector_request,vector_ok;
    logic [31:0] host_n;
    logic [LANES-1:0] effective_mask;
    assign vector_request=vector_load_we || vector_read_en;
    assign host_n=(size_log2>=1 && int'(size_log2)<=AW) ? (32'd1<<size_log2) : 32'd0;
    assign vector_ok=host_n!=0 && (32'(vector_addr)&32'(LANES-1))==0 && 32'(vector_addr)<host_n;
    for(genvar h=0;h<LANES;h=h+1)begin: host_lane
        assign effective_mask[h]=vector_lane_mask[h] && (32'(vector_addr)+32'(h))<host_n;
        assign vector_read_data[h*96+:96]=coeff_q[h];
    end

    function automatic logic [2:0] next_encoded(input logic signed [33:0] x,b);
        if(x < -b)next_encoded=0;
        else if(x<0)next_encoded=1;
        else if(x<b)next_encoded=2;
        else if(x<(b<<<1))next_encoded=3;
        else next_encoded=4;
    endfunction
    function automatic logic [14:0] make_transfer(input logic signed [32:0] s,input logic [31:0] b);
        logic signed [33:0] t;
        for(int k=0;k<5;k=k+1)begin
            t=34'(s)+34'(k)-34'sd2;
            make_transfer[k*3+:3]=next_encoded(t,$signed({2'b0,b}));
        end
    endfunction
    function automatic logic [14:0] compose(input logic [14:0] first,second);
        for(int k=0;k<5;k=k+1)compose[k*3+:3]=second[first[k*3+:3]*3+:3];
    endfunction
    assign read_data=coeff_q[host_bank_d];
    assign base_square=64'(base_reg-32'd1)*64'(base_reg-32'd1);
    assign reciprocal_shift={reciprocal_rem,1'b0};
    assign last_active=(int'(n)>=2 && int'(n)<LANES) ? int'(n)-1 : LANES-1;
    assign transfer_all=compose(compose(make_transfer(s0,base_reg),make_transfer(s1,base_reg)),suffix);
    assign emit_base=$signed({2'b0,base_reg});
    assign next_group=b_prefix[LANES-1][current_carry*3+:3];
    genefer_carry_transfer_tree #(.LANES(LANES)) summary_tree(.transfer(a_transfer),.prefix(a_prefix));
    genefer_carry_transfer_tree #(.LANES(LANES)) digit_tree(.transfer(b_transfer),.prefix(b_prefix));
    always_comb begin
        found_carry=0;multiple_carries=0;solved_carry=2;
        for(int k=0;k<5;k=k+1)if(k+int'(transfer_all[k*3+:3])==4)begin
            if(found_carry)multiple_carries=1;
            found_carry=1;solved_carry=3'(k);
        end
    end
    for(genvar g=0;g<LANES;g=g+1)begin: lane
        genefer_sp_ram #(.WIDTH(96),.AW(RW),.DEPTH(DEPTH)) coefficient_ram (
            .clk,.rst_n,.en(mem_en[g]),.write_en(mem_we[g]),.addr(mem_addr[g]),
            .write_data(mem_data[g]),.read_data(coeff_q[g])
        );
        genefer_sp_ram #(.WIDTH(33),.AW(RW),.DEPTH(DEPTH)) intermediate_ram (
            .clk,.rst_n,.en(small_en[g]),.write_en(small_we[g]),.addr(small_addr[g]),
            .write_data(small_data[g]),.read_data(small_q[g])
        );
        logic signed [32:0] predecessor_r1,predecessor_q;
        logic signed [77:0] first_q_narrow;
        logic signed [47:0] split_q_narrow;
        logic coefficient_in_range;
        assign coefficient_in_range=coeff_q[g]>=-$signed(bound) && coeff_q[g]<=$signed(bound);
        assign first_q[g]={{18{first_q_narrow[77]}},first_q_narrow};
        assign split_q[g]={{48{split_q_narrow[47]}},split_q_narrow};
        if(g==0)assign predecessor_r1=$signed({1'b0,previous_r1});
        else assign predecessor_r1=$signed({1'b0,split_r1[g-1]});
        if(g==0)assign predecessor_q=previous_previous_q;
        else if(g==1)assign predecessor_q=previous_q;
        else assign predecessor_q=33'(split_q[g-2]);
        assign stream_s[g]=$signed({1'b0,split_r0[g]})+predecessor_r1+predecessor_q;
        assign a_transfer[g]=(g<int'(n) && ((int'(received)<<LGW)+g)>=2) ? make_transfer(stream_s[g],base_reg) : IDENTITY;
        assign raw_leaf[g]=g<int'(n) ? make_transfer(small_q[g],base_reg) : IDENTITY;
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
        genefer_div_recip_narrow #(.MAG_W(77),.PAYLOAD_W(1)) first_div (
            .clk,.rst_n,.in_valid(state==SPLIT && input_d && g<int'(n) && coefficient_in_range),.value(coeff_q[g][77:0]),
            .base(base_reg),.reciprocal,.payload_in(1'b0),.out_valid(first_valid[g]),
            .quotient(first_q_narrow),.remainder(first_r[g]),.payload_out()
        );
        genefer_div_recip_narrow #(.MAG_W(47),.PAYLOAD_W(32)) second_div (
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
                        if(vector_ok)begin
                            mem_en[g]=effective_mask[g];mem_we[g]=vector_load_we;
                            mem_addr[g]=RW'(vector_addr>>LGW);
                            mem_data[g]=$signed(vector_write_data[g*96+:96]);
                        end
                    end else if((int'(host_addr)&(LANES-1))==g)begin
                        mem_en[g]=load_we||read_en;mem_we[g]=load_we;
                    end
                end
                SPLIT:begin
                    mem_en[g]=issue<groups && g<int'(n);mem_addr[g]=RW'(issue);
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
            // Leaf formation, prefix/carry selection and digit arithmetic
            // are separate stages; feedback advances once per leaf-valid group.
            if(rst_n && state==EMIT && small_d)begin
                leaf_small[g]<=small_q[g];b_transfer[g]<=raw_leaf[g];
            end
            if(rst_n && state==EMIT && leaf_valid)begin
                digit_small[g]<=leaf_small[g];digit_in[g]<=lane_in[g];digit_out[g]<=lane_out[g];
            end
            if(rst_n && state==EMIT && digit_valid)
                emit_data[g]<=special ? (digit_row==0 && g==0 ? -96'sd1 : 96'sd0) : $signed({62'b0,lane_digit[g]});
        end
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;busy<=0;done<=0;error<=0;read_valid<=0;cycles<=0;passes<=0;
            n<=0;groups<=0;issue<=0;received<=0;written<=0;lg<=0;base_reg<=2;bound<=0;
            reciprocal<=0;reciprocal_rem<=0;reciprocal_round<=0;input_d<=0;small_d<=0;host_bank_d<=0;
            emit_valid<=0;emit_row<=0;leaf_valid<=0;digit_valid<=0;leaf_row<=0;digit_row<=0;
            vector_read_valid<=0;vector_read_mask<=0;host_error<=0;
            first_r00<=0;first_r01<=0;first_r10<=0;previous_r1<=0;previous_q<=0;previous_previous_q<=0;
            s0<=0;s1<=0;suffix<=IDENTITY;current_carry<=2;initial_carry<=2;special<=0;
        end else begin
            done<=0;read_valid<=state==IDLE && !start && !vector_request && read_en && !load_we;
            vector_read_valid<=state==IDLE && !start && vector_read_en && !vector_load_we && vector_ok;
            vector_read_mask<=state==IDLE && !start && vector_read_en && !vector_load_we && vector_ok ? effective_mask : '0;
            host_error<=state==IDLE && !start && vector_request && !vector_ok;
            if(state==IDLE)host_bank_d<=LGW'(host_addr);
            input_d<=state==SPLIT && issue<groups;
            small_d<=state==EMIT && issue<groups;
            leaf_valid<=state==EMIT && small_d;
            digit_valid<=state==EMIT && leaf_valid;
            emit_valid<=state==EMIT && digit_valid;
            if(state==EMIT && small_d)leaf_row<=RW'(written);
            if(state==EMIT && leaf_valid)digit_row<=leaf_row;
            if(state==EMIT && digit_valid)emit_row<=digit_row;
            if(busy)cycles<=cycles+1;
            case(state)
                IDLE:if(start)begin
                    cycles<=0;error<=0;passes<=0;
                    if(size_log2<1 || size_log2>16 || int'(size_log2)>AW || base>1000000000 || base<=(32'd2<<size_log2)+32'd4 ||
                       LANES<2 || LANES>16 || (LANES&(LANES-1))!=0)begin done<=1;error<=1;end
                    else begin
                        n<=(AW+1)'(1)<<size_log2;groups<=(AW+1)'(((32'd1<<size_log2)+32'(LANES)-1)>>LGW);
                        lg<=size_log2;base_reg<=base;busy<=1;state<=BOUND;issue<=0;received<=0;written<=0;
                        suffix<=IDENTITY;reciprocal<=0;reciprocal_rem<=1;reciprocal_round<=0;
                        previous_r1<=0;previous_q<=0;previous_previous_q<=0;passes<=1;special<=0;
                    end
                end
                BOUND:begin bound<=96'(base_square)<<(int'(lg)+1);state<=RECIP;end
                RECIP:begin
                    reciprocal_round<=reciprocal_round+1;
                    if(reciprocal_shift>={1'b0,base_reg})begin
                        reciprocal_rem<=32'(reciprocal_shift-{1'b0,base_reg});reciprocal<={reciprocal[94:0],1'b1};
                    end else begin reciprocal_rem<=reciprocal_shift[31:0];reciprocal<={reciprocal[94:0],1'b0};end
                    if(reciprocal_round==95)state<=SPLIT;
                end
                SPLIT:begin
                    if(issue<groups)issue<=issue+1;
                    if(split_valid[0])begin
                        received<=received+1;suffix<=compose(suffix,a_prefix[LANES-1]);
                        previous_previous_q<=33'(split_q[last_active-1]);previous_q<=33'(split_q[last_active]);previous_r1<=split_r1[last_active];
                        if(received==0)begin first_r00<=split_r0[0];first_r01<=split_r0[1];first_r10<=split_r1[0];end
                        if(received==groups-1)begin
                            s0<=$signed({1'b0,(received==0 ? split_r0[0] : first_r00)})-$signed({1'b0,split_r1[last_active]})-33'(split_q[last_active-1]);
                            s1<=$signed({1'b0,(received==0 ? split_r0[1] : first_r01)})+$signed({1'b0,(received==0 ? split_r1[0] : first_r10)})-33'(split_q[last_active]);
                            state<=WRAP;
                        end
                    end
                    for(int g=0;g<LANES;g=g+1)if(input_d && g<int'(n) && (coeff_q[g]<-$signed(bound) || coeff_q[g]>$signed(bound)))begin
                        error<=1;done<=1;busy<=0;state<=IDLE;
                    end
                end
                WRAP:state<=SOLVE;
                SOLVE:begin
                    initial_carry<=solved_carry;current_carry<=solved_carry;special<=!found_carry;
                    issue<=0;written<=0;passes<=2;state<=EMIT;
                    if(multiple_carries)begin error<=1;done<=1;busy<=0;state<=IDLE;end
                end
                EMIT:begin
                    if(issue<groups)issue<=issue+1;
                    if(small_d)written<=written+1;
                    if(leaf_valid)current_carry<=next_group;
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
    // synthesis translate_off
    always @(posedge clk)if(rst_n && state==SPLIT)begin
        for(int g=0;g<LANES;g=g+1)
            if(first_valid[g] && first_q[g] != {{48{first_q[g][47]}},first_q[g][47:0]})
                $fatal(1,"first quotient outside signed48 range");
        for(int g=0;g<LANES;g=g+1)
            if(split_valid[g] != (split_valid[0] && g<int'(n)))$fatal(1,"wide split lane skew");
    end
    // synthesis translate_on
endmodule

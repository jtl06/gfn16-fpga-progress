// Exact two-pass bounded-domain carry candidate. Same host ports as carry_fast.
// Runtime-checked domain: N=2^size_log2>=2, base>2*N+4, base<=1e9,
// |input coefficient|<=2*N*(base-1)^2. Unsupported inputs report error.
// Coefficient RAM96 and separate redistributed RAM33, both synchronous.
// Reset aborts: reload all coefficients after reset or any reported error.
module genefer_carry_prefix #(parameter int AW=16) (
    input logic clk, rst_n, load_we, read_en, start,
    input logic [AW-1:0] host_addr,
    input logic signed [95:0] write_data,
    input logic [4:0] size_log2,
    input logic [31:0] base,
    output logic read_valid,
    output logic signed [95:0] read_data,
    output logic busy, done, error,
    output logic [63:0] cycles,
    output logic [6:0] passes
);
    typedef enum logic [3:0] {IDLE, BOUND, RECIP, SPLIT, WRAP0, WRAP1, SOLVE, EMIT} state_t;
    state_t state;
    logic signed [95:0] mem[0:(1<<AW)-1];
    logic signed [32:0] small_mem[0:(1<<AW)-1];
    logic signed [95:0] coeff_q;
    logic signed [32:0] small_q, s0, s1, stream_s;
    logic [AW:0] n, issue, received, written;
    logic [4:0] lg;
    logic [31:0] base_reg;
    logic [63:0] base_square;
    logic [95:0] bound, reciprocal;
    logic [31:0] reciprocal_rem;
    logic [32:0] reciprocal_shift;
    logic [6:0] reciprocal_round;
    logic input_d, small_d;
    logic first_valid, split_valid;
    logic signed [95:0] first_q, split_q;
    logic [31:0] first_r, split_r1, split_r0;
    logic [31:0] first_r00, first_r01, first_r10, previous_r1;
    logic signed [32:0] previous_q, previous_previous_q;
    logic [14:0] suffix, prefix0, transfer_all;
    logic [2:0] current_carry, initial_carry, solved_carry;
    logic found_carry, multiple_carries, special;
    logic signed [33:0] emit_total, emit_digit, emit_base;
    logic [2:0] emit_next;
    logic mem_en,mem_we,small_en,small_we;
    logic [AW-1:0] mem_addr,small_addr;
    logic signed [95:0] mem_data;
    logic signed [32:0] small_data;

    // Transfers encode carry c as unsigned c+2, keeping composition a tiny mux.
    function automatic logic [2:0] next_encoded(input logic signed [33:0] x, b);
        if(x < -b) next_encoded=0;
        else if(x<0) next_encoded=1;
        else if(x<b) next_encoded=2;
        else if(x<(b<<<1)) next_encoded=3;
        else next_encoded=4;
    endfunction
    function automatic logic [14:0] make_transfer(input logic signed [32:0] s, input logic [31:0] b);
        logic signed [33:0] t;
        for(int k=0;k<5;k=k+1) begin
            t=34'(s)+34'(k)-34'sd2;
            make_transfer[k*3+:3]=next_encoded(t,$signed({2'b0,b}));
        end
    endfunction
    function automatic logic [14:0] compose(input logic [14:0] first, second);
        for(int k=0;k<5;k=k+1) compose[k*3+:3]=second[first[k*3+:3]*3+:3];
    endfunction
    localparam logic [14:0] IDENTITY={3'd4,3'd3,3'd2,3'd1,3'd0};
    assign read_data=coeff_q;
    assign base_square=64'(base_reg-32'd1)*64'(base_reg-32'd1);
    assign reciprocal_shift={reciprocal_rem,1'b0};
    assign stream_s=$signed({1'b0,split_r0})+$signed({1'b0,previous_r1})+previous_previous_q;
    assign transfer_all=compose(compose(prefix0,make_transfer(s1,base_reg)),suffix);
    always_comb begin
        found_carry=0; multiple_carries=0; solved_carry=2;
        for(int k=0;k<5;k=k+1) begin
            if(k+int'(transfer_all[k*3+:3])==4) begin
                if(found_carry) multiple_carries=1;
                found_carry=1; solved_carry=3'(k);
            end
        end
    end
    assign emit_base=$signed({2'b0,base_reg});
    assign emit_total=34'(small_q)+$signed({31'b0,current_carry})-34'sd2;
    assign emit_next=next_encoded(emit_total,emit_base);
    always_comb begin
        case(emit_next)
            0: emit_digit=emit_total+(emit_base<<<1);
            1: emit_digit=emit_total+emit_base;
            2: emit_digit=emit_total;
            3: emit_digit=emit_total-emit_base;
            default: emit_digit=emit_total-(emit_base<<<1);
        endcase
    end
    genefer_div96_recip_prefix #(.PAYLOAD_W(1)) split_first (
        .clk,.rst_n,.in_valid(state==SPLIT && input_d),.value(coeff_q),
        .base(base_reg),.reciprocal,.payload_in(1'b0),.out_valid(first_valid),
        .quotient(first_q),.remainder(first_r),.payload_out()
    );
    genefer_div96_recip_prefix #(.PAYLOAD_W(32)) split_second (
        .clk,.rst_n,.in_valid(first_valid),.value(first_q),
        .base(base_reg),.reciprocal,.payload_in(first_r),.out_valid(split_valid),
        .quotient(split_q),.remainder(split_r1),.payload_out(split_r0)
    );
    always_comb begin
        mem_en=0;mem_we=0;mem_addr=host_addr;mem_data=write_data;
        small_en=0;small_we=0;small_addr=0;small_data=0;
        case(state)
            IDLE: if(!start) begin mem_en=load_we||read_en;mem_we=load_we;end
            SPLIT: begin
                mem_en=issue<n;mem_addr=AW'(issue);
                if(split_valid && received>=2) begin
                    small_en=1;small_we=1;small_addr=AW'(received);small_data=stream_s;
                end
            end
            WRAP0: begin small_en=1;small_we=1;small_addr=0;small_data=s0;end
            WRAP1: begin small_en=1;small_we=1;small_addr=AW'(1);small_data=s1;end
            EMIT: begin
                small_en=issue<n;small_addr=AW'(issue);
                if(small_d) begin
                    mem_en=1;mem_we=1;mem_addr=AW'(written);
                    mem_data=special ? (written==0 ? -96'sd1 : 96'sd0) : $signed({62'b0,emit_digit});
                end
            end
            default: ;
        endcase
    end
    always_ff @(posedge clk) begin
        if(rst_n && mem_en) begin
            if(mem_we) mem[mem_addr]<=mem_data;
            else coeff_q<=mem[mem_addr];
        end
        if(rst_n && small_en) begin
            if(small_we) small_mem[small_addr]<=small_data;
            else small_q<=small_mem[small_addr];
        end
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE;busy<=0;done<=0;error<=0;read_valid<=0;cycles<=0;passes<=0;
            n<=0;issue<=0;received<=0;written<=0;lg<=0;base_reg<=2;bound<=0;
            reciprocal<=0;reciprocal_rem<=0;reciprocal_round<=0;input_d<=0;small_d<=0;
            first_r00<=0;first_r01<=0;first_r10<=0;previous_r1<=0;
            previous_q<=0;previous_previous_q<=0;s0<=0;s1<=0;suffix<=IDENTITY;prefix0<=IDENTITY;
            current_carry<=2;initial_carry<=2;special<=0;
        end else begin
            done<=0;read_valid<=state==IDLE && !start && read_en && !load_we;
            input_d<=state==SPLIT && issue<n;
            small_d<=state==EMIT && issue<n;
            if(busy)cycles<=cycles+1;
            case(state)
                IDLE: if(start) begin
                    cycles<=0;error<=0;passes<=0;
                    if(size_log2<1 || int'(size_log2)>AW || base>1000000000 ||
                       base<=(32'd2<<size_log2)+32'd4) begin done<=1;error<=1;end
                    else begin
                        n<=(AW+1)'(1)<<size_log2;lg<=size_log2;base_reg<=base;busy<=1;state<=BOUND;
                        issue<=0;received<=0;written<=0;suffix<=IDENTITY;prefix0<=IDENTITY;
                        reciprocal<=0;reciprocal_rem<=1;reciprocal_round<=0;
                        previous_r1<=0;previous_q<=0;previous_previous_q<=0;passes<=1;special<=0;
                    end
                end
                BOUND: begin bound<=96'(base_square)<<(int'(lg)+1);state<=RECIP;end
                RECIP: begin
                    reciprocal_round<=reciprocal_round+1;
                    if(reciprocal_shift>={1'b0,base_reg}) begin
                        reciprocal_rem<=32'(reciprocal_shift-{1'b0,base_reg});reciprocal<={reciprocal[94:0],1'b1};
                    end else begin reciprocal_rem<=reciprocal_shift[31:0];reciprocal<={reciprocal[94:0],1'b0};end
                    if(reciprocal_round==95)state<=SPLIT;
                end
                SPLIT: begin
                    if(issue<n)issue<=issue+1;
                    if(split_valid) begin
                        received<=received+1;
                        previous_previous_q<=previous_q;previous_q<=33'(split_q);previous_r1<=split_r1;
                        if(received==0)begin first_r00<=split_r0;first_r10<=split_r1;end
                        if(received==1)first_r01<=split_r0;
                        if(received>=2)suffix<=compose(suffix,make_transfer(stream_s,base_reg));
                        if(received==n-1) begin
                            s0<=$signed({1'b0,first_r00})-$signed({1'b0,split_r1})-previous_q;
                            s1<=$signed({1'b0,(n==2 ? split_r0 : first_r01)})+$signed({1'b0,first_r10})-33'(split_q);
                            state<=WRAP0;
                        end
                    end
                    if(input_d && (coeff_q < -$signed(bound) || coeff_q>$signed(bound))) begin
                        error<=1;done<=1;busy<=0;state<=IDLE;
                    end
                end
                WRAP0: begin prefix0<=make_transfer(s0,base_reg);state<=WRAP1;end
                WRAP1: state<=SOLVE;
                SOLVE: begin
                    initial_carry<=solved_carry;current_carry<=solved_carry;special<=!found_carry;
                    issue<=0;written<=0;passes<=2;state<=EMIT;
                    if(multiple_carries)begin error<=1;done<=1;busy<=0;state<=IDLE;end
                end
                EMIT: begin
                    if(issue<n)issue<=issue+1;
                    if(small_d) begin
                        written<=written+1;current_carry<=emit_next;
                        if(written==n-1) begin
                            busy<=0;done<=1;state<=IDLE;
                            if(!special && int'(emit_next)+int'(initial_carry)!=4)error<=1;
                        end
                    end
                end
                default:begin busy<=0;done<=1;error<=1;state<=IDLE;end
            endcase
        end
    end
endmodule

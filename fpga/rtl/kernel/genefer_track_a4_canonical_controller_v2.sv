// Provisional executable canonical-pass controller. RAM frontend must provide
// synchronous natural-order signed effective reads and block-banked1R1W writes.
// begin E0, first read E1; ordinary one-pass done E(N+3). No hidden ready stalls:
// one accepted read per read_en edge and exactly one tagged response next edge.
module genefer_track_a4_canonical_controller_v2 #(parameter int AW=16) (
    input logic clk,rst_n,begin_canonical,cancel,
    input logic [31:0] base,generation,
    output logic busy,done,error,minus_one,
    output logic [3:0] error_code,
    output logic [31:0] out_generation,max_digit,
    output logic [1:0] passes,
    output logic mem_read_en,mem_read_apply_corrections,
    output logic [AW-1:0] mem_read_address,
    output logic [31:0] mem_generation,
    input logic mem_read_valid,mem_error,
    input logic signed [32:0] mem_read_value,
    input logic [AW-1:0] mem_read_tag,
    input logic [31:0] mem_read_generation,
    output logic [15:0] mem_write_mask,
    output logic [AW-1:0] mem_write_offset,
    output logic [511:0] mem_write_words,
    output logic clear_corrections,set_minus_one,
    output logic registered_child_tail_checked
);
    localparam int N=1<<AW,T=N/16,K=2*N+384;
    localparam int MIN_PROOF=(2*K+2)/3+1;
    localparam int MIN_BASE=(2*N+5)>MIN_PROOF ? (2*N+5) : MIN_PROOF;
    typedef enum logic [2:0] {IDLE,PASS,DRAIN,CHECK,CLEAR,CLEAR_CHECK,FAILED} state_t;
    state_t state;
    logic [31:0] base_reg;
    logic [AW:0] issued,received,written,clear_offset;
    logic all_zero,all_max,read_due;
    logic signed [2:0] seed,terminal_carry,cell_carry;
    logic cell_valid,cell_error;
    logic [31:0] cell_digit;
    logic [AW-1:0] cell_tag;
    logic fault;
    logic [3:0] fault_code;
    wire streaming=state==PASS || state==DRAIN;
    wire read_ok=mem_read_generation==out_generation && mem_read_tag==AW'(received) && int'(received)<N;
    wire write_ok=cell_tag==AW'(written) && int'(written)<N;
    wire [3:0] write_bank=4'(cell_tag>>(AW-4));
    wire special=(terminal_carry==3'sd1 && all_zero) || (terminal_carry==-3'sd1 && all_max);
    assign busy=state!=IDLE && state!=FAILED;
    assign mem_generation=out_generation;
    assign mem_read_en=state==PASS && int'(issued)<N && !fault && !cancel;
    assign mem_read_address=AW'(issued);
    assign mem_read_apply_corrections=passes==1;
    assign clear_corrections=state==CHECK && passes==1 && !fault && !cancel;
    assign set_minus_one=state==CLEAR_CHECK && !fault && !cancel;
    genefer_track_a4_canonical_cell_v1 #(.AW(AW),.PAYLOAD_W(AW)) normalize_cell (
        .clk,.rst_n,.in_valid(streaming && mem_read_valid && read_ok && !fault && !cancel),
        .base(base_reg),.value(mem_read_value),.carry_in(mem_read_tag==0 ? seed : cell_carry),
        .payload_in(mem_read_tag),.out_valid(cell_valid),.out_error(cell_error),
        .digit(cell_digit),.carry_out(cell_carry),.payload_out(cell_tag)
    );
    always_comb begin
        mem_write_mask=0;mem_write_offset=0;mem_write_words=0;
        if(!fault && !cancel)begin
            if(streaming && cell_valid)begin
                mem_write_mask=16'd1<<int'(write_bank);
                mem_write_offset=AW'(32'(cell_tag)&32'(T-1));
                mem_write_words[int'(write_bank)*32+:32]=cell_digit;
            end
            if(state==CLEAR && int'(clear_offset)<T)begin
                mem_write_mask=16'hffff;mem_write_offset=AW'(clear_offset);
            end
        end
    end
    always_comb begin
        fault=0;fault_code=0;
        if(busy)begin
            if(begin_canonical)begin fault=1;fault_code=4'd1;end
            else if(mem_error || cell_error)begin fault=1;fault_code=4'd2;end
            else if(streaming && mem_read_valid!=read_due)begin fault=1;fault_code=4'd3;end
            else if(streaming && mem_read_valid && !read_ok)begin fault=1;fault_code=4'd4;end
            else if(streaming && cell_valid && !write_ok)begin fault=1;fault_code=4'd5;end
            else if(state==CHECK && (int'(issued)!=N || int'(received)!=N || int'(written)!=N ||
                    mem_read_valid || cell_valid || read_due))begin fault=1;fault_code=4'd6;end
            else if(state==CHECK && terminal_carry!=0 && !special && passes==3)begin
                fault=1;fault_code=4'd7;
            end
        end
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;done<=0;error<=0;minus_one<=0;error_code<=0;out_generation<=0;
            max_digit<=0;passes<=0;base_reg<=0;issued<=0;received<=0;written<=0;clear_offset<=0;
            all_zero<=1;all_max<=1;read_due<=0;seed<=0;terminal_carry<=0;registered_child_tail_checked<=0;
        end else begin
            done<=0;read_due<=mem_read_en;
            if(state==IDLE && begin_canonical)begin
                error<=0;error_code<=0;minus_one<=0;registered_child_tail_checked<=0;
                out_generation<=generation;base_reg<=base;
                if(base<32'(MIN_BASE) || base>32'd1000000000)begin
                    error<=1;error_code<=4'd8;done<=1;state<=FAILED;
                end else begin
                    state<=PASS;passes<=1;issued<=0;received<=0;written<=0;
                    seed<=0;all_zero<=1;all_max<=1;max_digit<=0;
                end
            end
            if(mem_read_en)begin issued<=issued+1'b1;if(int'(issued)==N-1)state<=DRAIN;end
            if(streaming && mem_read_valid && !fault)received<=received+1'b1;
            if(streaming && cell_valid && !fault)begin
                written<=written+1'b1;all_zero<=all_zero && cell_digit==0;
                all_max<=all_max && cell_digit==base_reg-1'b1;
                if(cell_digit>max_digit)max_digit<=cell_digit;
                if(int'(written)==N-1)begin terminal_carry<=cell_carry;state<=CHECK;end
            end
            if(state==CHECK && !fault)begin
                if(special)begin state<=CLEAR;clear_offset<=0;end
                else if(terminal_carry==0)begin
                    state<=IDLE;done<=1;minus_one<=0;registered_child_tail_checked<=1;
                end else begin
                    passes<=passes+1'b1;state<=PASS;issued<=0;received<=0;written<=0;
                    seed<=-terminal_carry;all_zero<=1;all_max<=1;max_digit<=0;
                end
            end
            if(state==CLEAR && !fault)begin
                clear_offset<=clear_offset+1'b1;
                if(int'(clear_offset)==T-1)state<=CLEAR_CHECK;
            end
            if(state==CLEAR_CHECK && !fault)begin
                state<=IDLE;done<=1;minus_one<=1;max_digit<=0;registered_child_tail_checked<=1;
            end
            if(fault)begin
                state<=FAILED;error<=1;error_code<=fault_code;done<=0;registered_child_tail_checked<=0;read_due<=0;
            end
            if(cancel)begin
                state<=IDLE;done<=0;error<=0;minus_one<=0;read_due<=0;registered_child_tail_checked<=0;
            end
        end
    end
    // synthesis translate_off
    initial if(AW<5 || AW>16)$fatal(1,"A4_CANON_CONTROLLER_GEOMETRY");
    // synthesis translate_on
endmodule

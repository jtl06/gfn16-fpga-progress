// Provisional executable controller for the v1 interface. Children still require
// connection/qualification. START/WAIT adds2edges around EACH child invocation;
// this overhead is outside a child's cycle count and must not be hidden.
module genefer_track_a4_control_fsm_v2 #(parameter int AW=16) (
    genefer_track_a4_control_contract_v1.controller bus
);
    localparam int N=1<<AW,K=2*N+384;
    localparam int MIN_PROOF=(2*K+2)/3+1;
    localparam int MIN_BASE=(2*N+5)>MIN_PROOF ? (2*N+5) : MIN_PROOF;
    typedef enum logic [3:0] {COMMAND,SETUP_START,SETUP_WAIT,CANON_START,CANON_WAIT,
        WORD_START,WORD_WAIT,SQUARE_START,SQUARE_WAIT,BASE_CHECK} state_t;
    state_t state;
    logic [2:0] opcode;
    logic [AW-1:0] address;
    logic signed [31:0] word;
    logic [31:0] base_reg,new_base,generation,max_digit;
    logic [76:0] limit_reg;
    logic [95:0] reciprocal_reg;
    logic setup_valid,loading,canonical,mutated,prefilled_snapshot,double_reg;
    logic [AW:0] loaded;
    wire accepted=bus.cmd_valid && bus.cmd_ready;
    wire cmd_base_ok=bus.cmd_base>=32'(MIN_BASE) && bus.cmd_base<=32'd1000000000;
    wire cmd_word_ok=bus.cmd_word>=-32'sd1 &&
        $signed({bus.cmd_word[31],bus.cmd_word})<$signed({1'b0,base_reg});
    assign bus.cmd_ready=state==COMMAND && !bus.rsp_valid;
    assign bus.busy=state!=COMMAND;
    assign bus.image_generation=generation;
    // RELOAD emits a cancel pulse first. Never assert begin on that pulse:
    // shared children give cancel priority and would otherwise lose setup.
    assign bus.setup_begin=state==SETUP_START && !bus.cancel;
    assign bus.setup_base=new_base;
    assign bus.setup_generation=generation;
    assign bus.square_begin=state==SQUARE_START;
    assign bus.square_base=base_reg;
    assign bus.square_generation=generation;
    assign bus.square_double=double_reg;
    assign bus.square_prefilled=prefilled_snapshot;
    assign bus.square_coefficient_limit=limit_reg;
    assign bus.square_reciprocal=reciprocal_reg;
    assign bus.canonical_begin=state==CANON_START;
    assign bus.canonical_base=base_reg;
    assign bus.canonical_generation=generation;
    assign bus.host_word_begin=state==WORD_START;
    assign bus.host_word_write=opcode==bus.WRITE || opcode==bus.LOAD_WORD;
    assign bus.host_word_address=address;
    assign bus.host_word_write_data=word;
    assign bus.host_word_generation=generation;

    task automatic respond(input logic [2:0] op,input logic signed [31:0] data);
        begin
            state<=COMMAND;bus.rsp_valid<=1;bus.rsp_opcode<=op;
            bus.rsp_word<=data;bus.rsp_error<=0;bus.rsp_error_code<=0;bus.rsp_generation<=generation;
        end
    endtask
    task automatic fail(input logic [7:0] code,input logic [2:0] op);
        begin
            state<=COMMAND;bus.image_valid<=0;bus.prefill_valid<=0;bus.fault_sticky<=1;
            setup_valid<=0;loading<=0;canonical<=0;bus.cancel<=1;bus.cancel_generation<=generation;
            // Preserve a response already held under backpressure.
            if(!bus.rsp_valid)begin
                bus.rsp_valid<=1;bus.rsp_opcode<=op;bus.rsp_word<=0;
                bus.rsp_error<=1;bus.rsp_error_code<=code;bus.rsp_generation<=generation;
            end
        end
    endtask
    always_ff @(posedge bus.clk or negedge bus.rst_n)begin
        if(!bus.rst_n)begin
            state<=COMMAND;opcode<=0;address<=0;word<=0;base_reg<=0;new_base<=0;generation<=0;
            max_digit<=0;limit_reg<=0;reciprocal_reg<=0;setup_valid<=0;loading<=0;canonical<=0;
            mutated<=0;prefilled_snapshot<=0;double_reg<=0;loaded<=0;
            bus.rsp_valid<=0;bus.rsp_opcode<=0;bus.rsp_word<=0;bus.rsp_error<=0;bus.rsp_error_code<=0;
            bus.rsp_generation<=0;bus.image_valid<=0;bus.prefill_valid<=0;bus.fault_sticky<=0;
            bus.cancel<=0;bus.cancel_generation<=0;
        end else begin
            bus.cancel<=0;
            if(bus.rsp_valid && bus.rsp_ready)bus.rsp_valid<=0;
            if(accepted)begin
                opcode<=bus.cmd_opcode;address<=bus.cmd_address;word<=bus.cmd_word;
                new_base<=bus.cmd_base;double_reg<=bus.cmd_double;mutated<=0;
                if(bus.cmd_opcode==bus.RELOAD_BEGIN)begin
                    bus.image_valid<=0;bus.prefill_valid<=0;setup_valid<=0;loading<=0;canonical<=0;
                    bus.cancel<=1;bus.cancel_generation<=generation;generation<=generation+1'b1;
                    if(!cmd_base_ok)fail(8'd1,bus.cmd_opcode);
                    else begin state<=SETUP_START;bus.fault_sticky<=0;end
                end else if(loading)begin
                    if(bus.cmd_opcode!=bus.LOAD_WORD || bus.cmd_address!=AW'(loaded) ||
                        int'(loaded)>=N || !cmd_word_ok)fail(8'd2,bus.cmd_opcode);
                    else state<=WORD_START;
                end else if(!bus.image_valid || !setup_valid || bus.fault_sticky)fail(8'd3,bus.cmd_opcode);
                else if(bus.cmd_opcode==bus.SQUARE)begin
                    prefilled_snapshot<=bus.prefill_valid;bus.prefill_valid<=0;bus.image_valid<=0;
                    generation<=generation+1'b1;state<=SQUARE_START;
                end else if(bus.cmd_opcode==bus.READ || bus.cmd_opcode==bus.WRITE || bus.cmd_opcode==bus.SET_BASE)begin
                    generation<=generation+1'b1;bus.prefill_valid<=0;bus.image_valid<=0;
                    if(bus.cmd_opcode==bus.WRITE && !cmd_word_ok)fail(8'd4,bus.cmd_opcode);
                    else if(!canonical)state<=CANON_START;
                    else if(bus.cmd_opcode==bus.SET_BASE)state<=BASE_CHECK;
                    else state<=WORD_START;
                end else fail(8'd5,bus.cmd_opcode);
            end
            case(state)
                SETUP_START:if(!bus.cancel)state<=SETUP_WAIT;
                SETUP_WAIT:if(bus.setup_done)begin
                    if(bus.setup_error || bus.setup_out_generation!=generation || bus.setup_coefficient_limit==0 ||
                       bus.setup_reciprocal==0)fail(8'd6,opcode);
                    else begin
                        base_reg<=new_base;limit_reg<=bus.setup_coefficient_limit;
                        reciprocal_reg<=bus.setup_reciprocal;setup_valid<=1;
                        if(opcode==bus.RELOAD_BEGIN)begin loading<=1;loaded<=0;bus.image_valid<=0;end
                        else begin loading<=0;bus.image_valid<=1;canonical<=1;end
                        respond(opcode,32'sd0);
                    end
                end
                CANON_START:state<=CANON_WAIT;
                CANON_WAIT:if(bus.canonical_done)begin
                    if(bus.canonical_error || bus.canonical_out_generation!=generation ||
                       !bus.canonical_registered_child_tail_checked || bus.canonical_passes==0 ||
                       bus.canonical_max_digit>=base_reg)fail(8'd7,opcode);
                    else begin
                        canonical<=1;max_digit<=bus.canonical_max_digit;
                        if(opcode==bus.LOAD_WORD || (opcode==bus.WRITE && mutated))begin
                            bus.image_valid<=1;loading<=0;respond(opcode,32'sd0);
                        end else if(opcode==bus.SET_BASE)state<=BASE_CHECK;
                        else state<=WORD_START;
                    end
                end
                WORD_START:state<=WORD_WAIT;
                WORD_WAIT:if(bus.host_word_done)begin
                    if(bus.host_word_error || bus.host_word_out_generation!=generation)fail(8'd8,opcode);
                    else if(opcode==bus.READ)begin
                        bus.image_valid<=1;respond(opcode,bus.host_word_read_data);
                    end else if(opcode==bus.WRITE)begin mutated<=1;canonical<=0;state<=CANON_START;end
                    else if(opcode==bus.LOAD_WORD)begin
                        loaded<=loaded+1'b1;
                        if(int'(loaded)==N-1)state<=CANON_START;else respond(opcode,32'sd0);
                    end else fail(8'd5,opcode);
                end
                BASE_CHECK:begin
                    if(new_base<32'(MIN_BASE) || new_base>32'd1000000000)fail(8'd1,opcode);
                    else if(max_digit>=new_base)fail(8'd9,opcode);
                    else state<=SETUP_START;
                end
                SQUARE_START:state<=SQUARE_WAIT;
                SQUARE_WAIT:if(bus.square_done)begin
                    if(bus.square_error || bus.square_out_generation!=generation ||
                       int'(bus.square_coefficients_seen)!=N || int'(bus.square_digits_written)!=N ||
                       bus.square_patch_words_written!=6'd32 || !bus.square_registered_child_tail_checked ||
                       !bus.square_root_profile_coherent)fail(8'd10,opcode);
                    else begin
                        bus.image_valid<=1;bus.prefill_valid<=1;canonical<=0;respond(opcode,32'sd0);
                    end
                end
                default:;
            endcase
            // Child errors may precede done. Terminal done cannot override this.
            if(bus.registered_child_fault || (state==SETUP_WAIT && bus.setup_error) ||
               (state==CANON_WAIT && bus.canonical_error) || (state==WORD_WAIT && bus.host_word_error) ||
               (state==SQUARE_WAIT && bus.square_error))fail(8'd11,opcode);
        end
    end
    // synthesis translate_off
    initial if(AW<5 || AW>16)$fatal(1,"A4_CONTROL_GEOMETRY");
    // synthesis translate_on
endmodule

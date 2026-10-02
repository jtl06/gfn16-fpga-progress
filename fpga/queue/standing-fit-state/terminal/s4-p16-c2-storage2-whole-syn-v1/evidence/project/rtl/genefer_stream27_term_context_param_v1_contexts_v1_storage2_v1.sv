// Additive r17 successor: pending faults never gate current-edge transport.
// Source-only scalable correction-term producer. Four contexts per lane,
// two epoch-parity banks. Initial rows0..3 seed; row m updates row m+4.
// The product captured at edge k+4 is also bypassed to that edge's consumer:
// a RAM/register write at k+4 cannot supply a pre-edge read at k+4.
// ROOT inputs must use the exact owner/row calendar; source wrapper owns ROMs.
module genefer_stream27_term_context_param_v1_contexts_v1_storage2_v1 #(
    parameter int unsigned AW=16, LANES=16,
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] Q=32'd4190109697
) (
    input logic clk,rst_n,quarantine,
    input logic seed_slot,seed_start,
    input logic [26:0] seed_owner,
    input logic [1:0] seed_row,
    input logic [LANES*27-1:0] seed_coeff,seed_R_roots,
    input logic pointwise_slot,pointwise_start,
    input logic [26:0] pointwise_owner,
    input logic [AW-$clog2(LANES)-1:0] pointwise_row,
    input logic [LANES*27-1:0] next_coeff,next_seed_R_roots,
    input logic [26:0] update_R_factor,
    output logic term_slot,term_start,
    output logic [26:0] term_owner,
    output logic [AW-$clog2(LANES)-1:0] term_row,
    output logic [LANES*27-1:0] term_data,
    output logic cache_ready,
    output logic [26:0] cache_owner,
    output logic out_error,fault_pending
);
    localparam int ROW_W=AW-$clog2(LANES), LANE_W=$clog2(LANES),ROWS=1<<ROW_W,TAG_W=27+ROW_W;
    logic [LANES*27-1:0] context_data[0:1][0:3];
    logic [ROW_W-1:0] context_row[0:1][0:3];
    logic [3:0] context_valid[0:1];
    logic [26:0] bank_owner[0:1];
    logic [2:0] seed_remaining;
    logic [26:0] active_seed_owner,active_pw_owner;
    logic [ROW_W:0] pw_remaining;
    logic [ROW_W-1:0] expected_pw_row;
    logic local_bad,consumer_missing,product_owner_bad;
    logic [LANES*27-1:0] current_term;
    wire stop=quarantine || out_error;
    wire [ROW_W:0] wide_target={1'b0,pointwise_row}+(ROW_W+1)'(4);
    wire update_slot=pointwise_slot && wide_target<(ROW_W+1)'(ROWS);
    wire [ROW_W-1:0] next_row=wide_target[ROW_W-1:0];
    wire reseed=next_row[ROW_W-1-:LANE_W]!=pointwise_row[ROW_W-1-:LANE_W];
    wire product_slot,product_error,product_pending;
    wire [TAG_W-1:0] product_tag;
    wire [26:0] product_owner=product_tag[TAG_W-1:ROW_W];
    wire [ROW_W-1:0] product_row=product_tag[ROW_W-1:0];
    wire [LANES*27-1:0] product_data;
    wire pw_bank=pointwise_owner[24],prod_bank=product_owner[24],seed_bank=seed_owner[24];
    wire [1:0] pw_context=pointwise_row[1:0];
    wire bypass=product_slot && product_owner==pointwise_owner && product_row==pointwise_row;

    // Selection is independent of resulting fault/accept authority.
    always_comb begin : select_current_term
        current_term=context_data[pw_bank][pw_context];
        consumer_missing=pointwise_slot && (!context_valid[pw_bank][pw_context] ||
            bank_owner[pw_bank]!=pointwise_owner || context_row[pw_bank][pw_context]!=pointwise_row);
        if(bypass)begin current_term=product_data;consumer_missing=1'b0;end
        product_owner_bad=product_slot && bank_owner[prod_bank]!=product_owner;
    end
    always_comb begin : validate_calendar
        local_bad=consumer_missing || product_owner_bad || product_pending ||
            (seed_slot && update_slot) ||
            (seed_slot && seed_start && product_slot && seed_bank==prod_bank && seed_owner!=product_owner) ||
            (seed_slot && seed_start && pointwise_slot && seed_bank==pw_bank && seed_owner!=pointwise_owner) ||
            (seed_start && (!seed_slot || seed_remaining!=0 || seed_row!=0)) ||
            (seed_slot && !seed_start && (seed_remaining==0 || seed_owner!=active_seed_owner ||
              seed_row!=2'(3'd4-seed_remaining))) || (!seed_slot && seed_remaining!=0) ||
            (pointwise_start && (!pointwise_slot || pw_remaining!=0 || pointwise_row!=0)) ||
            (pointwise_slot && !pointwise_start && (pw_remaining==0 ||
              pointwise_owner!=active_pw_owner || pointwise_row!=expected_pw_row)) ||
            (!pointwise_slot && pw_remaining!=0);
    end
    assign fault_pending=out_error || product_error || (!quarantine && local_bad);
    // Raw occupied work may advance once on the edge detecting a fault.
    // Registered stop takes effect at the next edge; pending is diagnostic.
    wire product_accept=(seed_slot || update_slot) && !stop;
    wire [TAG_W-1:0] issue_tag=seed_slot ? {seed_owner,ROW_W'(seed_row)} : {pointwise_owner,next_row};
    wire [LANES*27-1:0] issue_lhs=seed_slot ? seed_coeff : (reseed ? next_coeff : current_term);
    wire [LANES*27-1:0] repeated_factor={LANES{update_R_factor}};
    wire [LANES*27-1:0] issue_rhs=seed_slot ? seed_R_roots : (reseed ? next_seed_R_roots : repeated_factor);
    genefer_stream27_mul_param_v1 #(.LANES(LANES),.P(P),.Q(Q),.GEN_W(TAG_W)) products (
        .clk,.rst_n,.in_slot_valid(product_accept),.frame_start(seed_slot && seed_start),.quarantine(stop),
        .generation_in(issue_tag),.lhs(issue_lhs),.rhs(issue_rhs),
        .out_slot_valid(product_slot),.out_frame_start(),.out_error(product_error),
        .fault_pending(product_pending),.generation_out(product_tag),.result(product_data));
    // Physical readiness token is not filtered by acceptance/fault_pending.
    // The enclosing protocol must check aggregate faults at its capture edge.
    assign cache_ready=product_slot && product_row==ROW_W'(3) && !stop &&
                       bank_owner[prod_bank]==product_owner;
    assign cache_owner=product_owner;
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            for(int bank=0;bank<2;bank=bank+1)context_valid[bank]<='0;seed_remaining<=0;pw_remaining<=0;
            expected_pw_row<=0;out_error<=0;term_slot<=0;term_start<=0;
        end else begin
            if(!quarantine && (local_bad || product_error))out_error<=1;
            term_slot<=pointwise_slot && !stop;
            term_start<=pointwise_slot && pointwise_start && !stop;
            if(!stop)begin
                if(seed_slot)begin
                    if(seed_start)begin
                        bank_owner[seed_bank]<=seed_owner;context_valid[seed_bank]<=0;
                        active_seed_owner<=seed_owner;seed_remaining<=3;
                    end else seed_remaining<=seed_remaining-3'd1;
                end
                if(pointwise_slot)begin
                    term_data<=current_term;term_owner<=pointwise_owner;term_row<=pointwise_row;
                    if(pointwise_start)begin
                        active_pw_owner<=pointwise_owner;pw_remaining<=(ROW_W+1)'(ROWS-1);
                    end else pw_remaining<=pw_remaining-(ROW_W+1)'(1);
                    expected_pw_row<=pointwise_row+ROW_W'(1);
                end
                // Do not write another epoch's bank, even during the one-edge tail.
                if(product_slot && bank_owner[prod_bank]==product_owner)begin
                    context_data[prod_bank][product_row[1:0]]<=product_data;
                    context_row[prod_bank][product_row[1:0]]<=product_row;
                    context_valid[prod_bank][product_row[1:0]]<=1'b1;
                end
            end
        end
    end
    // synthesis translate_off
    initial if(AW>16 || ROW_W<LANE_W || (LANES!=8 && LANES!=16))$fatal(1,"TERM_CONTEXT_AW8_16");
    // synthesis translate_on
endmodule

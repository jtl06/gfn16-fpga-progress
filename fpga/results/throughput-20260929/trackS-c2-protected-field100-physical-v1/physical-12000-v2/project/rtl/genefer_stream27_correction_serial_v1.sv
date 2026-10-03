// Isolated two-vector correction DIF; no shared-generator modification.
// Input/output lane order exactly matches the frozen small physical DIF.
// A/B input edges are consecutive, with equal owner; output edges consecutive.
// Existing canonical butterfly has issue->output5, consumer capture6.
module genefer_stream27_correction_serial_v1 #(
    parameter int LANES=16, GEN_W=24,
    parameter logic [31:0] MODULUS=32'd104857601, Q=32'd4190109697,
    parameter logic [$clog2(LANES)*(LANES/2)*27-1:0] ROOTS='0
) (
    input logic clk,rst_n,in_slot_valid,frame_start,quarantine,context_enabled,
    input logic [GEN_W-1:0] generation_in,live_generation,
    input logic [LANES*27-1:0] data_in,
    output logic out_slot_valid,out_frame_start,out_eligible,out_error,fault_pending,
    output logic [GEN_W-1:0] generation_out,
    output logic [LANES*27-1:0] data_out
);
    localparam int PW=$clog2(LANES), STAGES=PW, PAIRS=LANES/2, WAVES=LANES/2;
    localparam int SW=$clog2(STAGES), WW=$clog2(WAVES+1);
    typedef enum logic [2:0] {IDLE,CAPTURE_B,RUN,EMIT_A,EMIT_B} state_t;
    state_t state;
    logic [26:0] values[0:1][0:LANES-1];
    logic [GEN_W-1:0] owner;
    logic [SW-1:0] stage;
    logic [WW-1:0] wave,returned;
    logic aborted,malformed;
    wire stop=quarantine || out_error || aborted;
    wire issue=(state==RUN) && (wave<WW'(WAVES)) && !stop;
    logic [5:0] tag_valid;
    logic tag_bank[0:5][0:1];
    logic [PW-1:0] tag_low[0:5][0:1],tag_high[0:5][0:1];
    logic issue_bank[0:1];
    logic [PW-1:0] issue_low[0:1],issue_high[0:1];
    logic [31:0] u[0:1],v[0:1],w[0:1];
    wire [1:0] valid;
    wire [31:0] y0[0:1],y1[0:1];

    always_comb begin
        malformed=(frame_start && !in_slot_valid);
        if(state==IDLE) malformed=malformed || (in_slot_valid && !frame_start);
        else if(state==CAPTURE_B)
            malformed=malformed || !in_slot_valid || !frame_start || generation_in!=owner;
        else malformed=malformed || in_slot_valid;
        if(in_slot_valid)for(int lane=0;lane<LANES;lane=lane+1)
            if({5'b0,data_in[lane*27+:27]}>=MODULUS)malformed=1;
    end
    assign fault_pending=out_error || aborted || (!quarantine && (malformed || valid!={2{tag_valid[5]}}));
    assign out_eligible=out_slot_valid && context_enabled && generation_out==live_generation;

    always_comb begin : issue_select
        integer op,pair_index,low_index,root_index;
        op=0;pair_index=0;low_index=0;root_index=0;
        for(int unit_index=0;unit_index<2;unit_index=unit_index+1)begin
            op=int'(wave)*2+unit_index;
            pair_index=op%PAIRS;
            low_index=(pair_index & ((1<<int'(stage))-1)) | ((pair_index>>int'(stage))<<(int'(stage)+1));
            root_index=int'(stage)*PAIRS+pair_index;
            issue_bank[unit_index]=(op>=PAIRS);
            issue_low[unit_index]=PW'(low_index);
            issue_high[unit_index]=PW'(low_index | (1<<int'(stage)));
            u[unit_index]={5'b0,values[issue_bank[unit_index]][issue_low[unit_index]]};
            v[unit_index]={5'b0,values[issue_bank[unit_index]][issue_high[unit_index]]};
            w[unit_index]={5'b0,ROOTS[root_index*27+:27]};
        end
    end
    for(genvar unit_index=0;unit_index<2;unit_index=unit_index+1)begin: pool
        genefer_ntt_difdit_butterfly27 #(.P(MODULUS),.Q(Q)) butterfly (
            .clk,.rst_n,.in_valid(issue),.dif(1'b1),
            .u(u[unit_index]),.v(v[unit_index]),.w(w[unit_index]),
            .out_valid(valid[unit_index]),.y0(y0[unit_index]),.y1(y1[unit_index]));
    end

    function automatic integer reverse_lane(input integer lane);
        integer result;
        begin result=0;for(int bit_index=0;bit_index<PW;bit_index=bit_index+1)
            result=(result<<1)|((lane>>bit_index)&1);return result;end
    endfunction
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;stage<=0;wave<=0;returned<=0;tag_valid<=0;
            out_slot_valid<=0;out_frame_start<=0;out_error<=0;aborted<=0;
        end else begin
            out_slot_valid<=0;out_frame_start<=0;
            if(quarantine)aborted<=1;
            if(!stop && fault_pending)out_error<=1;
            if(stop)begin state<=IDLE;tag_valid<=0;end
            else begin
                tag_valid<={tag_valid[4:0],issue};
                for(int unit_index=0;unit_index<2;unit_index=unit_index+1)begin
                    tag_bank[0][unit_index]<=issue_bank[unit_index];
                    tag_low[0][unit_index]<=issue_low[unit_index];tag_high[0][unit_index]<=issue_high[unit_index];
                    for(int delay_index=1;delay_index<6;delay_index=delay_index+1)begin
                        tag_bank[delay_index][unit_index]<=tag_bank[delay_index-1][unit_index];
                        tag_low[delay_index][unit_index]<=tag_low[delay_index-1][unit_index];
                        tag_high[delay_index][unit_index]<=tag_high[delay_index-1][unit_index];
                    end
                    if(tag_valid[5] && (&valid))begin
                        values[tag_bank[5][unit_index]][tag_low[5][unit_index]]<=y0[unit_index][26:0];
                        values[tag_bank[5][unit_index]][tag_high[5][unit_index]]<=y1[unit_index][26:0];
                    end
                end
                case(state)
                    IDLE:if(in_slot_valid)begin
                        owner<=generation_in;
                        for(int lane=0;lane<LANES;lane=lane+1)values[0][lane]<=data_in[lane*27+:27];
                        state<=CAPTURE_B;
                    end
                    CAPTURE_B:begin
                        if(in_slot_valid)for(int lane=0;lane<LANES;lane=lane+1)values[1][lane]<=data_in[lane*27+:27];
                        stage<=0;wave<=0;returned<=0;state<=RUN;
                    end
                    RUN:begin
                        if(issue)wave<=wave+WW'(1);
                        if(tag_valid[5] && (&valid))begin
                            if(returned==WW'(WAVES-1))begin
                                returned<=0;wave<=0;
                                if(stage==SW'(STAGES-1))state<=EMIT_A;
                                else stage<=stage+SW'(1);
                            end else returned<=returned+WW'(1);
                        end
                    end
                    EMIT_A,EMIT_B:begin
                        out_slot_valid<=1;out_frame_start<=1;generation_out<=owner;
                        for(int lane=0;lane<LANES;lane=lane+1)
                            data_out[lane*27+:27]<=values[state==EMIT_B][reverse_lane(lane)];
                        state<=(state==EMIT_A)?EMIT_B:IDLE;
                    end
                    default:begin state<=IDLE;out_error<=1;end
                endcase
            end
        end
    end
    // synthesis translate_off
    initial if((LANES!=8 && LANES!=16) || GEN_W<1 || Q!=(32'd2-MODULUS))
        $fatal(1,"CORR_SERIAL_PARAMETERS");
    // synthesis translate_on
endmodule

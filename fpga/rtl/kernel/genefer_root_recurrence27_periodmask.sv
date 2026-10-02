// Standalone direct root-vector recurrence, not a replacement for arbitrary
// root_we caches. Caller supplies coherent canonical seeds and a Montgomery
// step for its field/stage/phase. Ordinary post seeds remain ordinary.
// Request at edge t -> registered roots/tag after edge t, like sync RAM q.
// Four-stage update results are bypassed before same-edge context writeback.
module genefer_root_recurrence27_periodmask #(
    parameter int LANES=16,TAG_W=32,
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
) (
    input logic clk,rst_n,
    input logic seed_we,seed_clear,seed_bank,
    input logic [1:0] seed_context,
    input logic [6:0] seed_lane,
    input logic [31:0] seed_data,
    input logic start,config_bank,
    input logic [16:0] config_groups,config_period,
    input logic [6:0] config_active_lanes,
    input logic [31:0] config_step,
    input logic request_valid,
    output logic request_ready,
    input logic [TAG_W-1:0] request_tag,
    output logic root_valid,
    output logic [LANES*32-1:0] roots,
    output logic [LANES-1:0] root_mask,
    output logic [TAG_W-1:0] root_tag,
    output logic [16:0] root_group,
    output logic busy,done,error,seed_error,
    output logic [63:0] cycles
);
    localparam int SLW=LANES>1 ? $clog2(LANES) : 1;
    typedef enum logic [1:0] {IDLE,RUN,DRAIN} state_t;
    state_t state;
    logic [31:0] seeds[0:1][0:3][0:LANES-1];
    logic [LANES-1:0] seed_valid[0:1][0:3];
    logic [31:0] context_value[0:3][0:LANES-1];
    logic [3:0] available;
    logic [1:0] context_pipe[0:3];
    logic active_bank,fire,use_seed,bypass,config_ok,seed_access,seed_legal;
    logic [16:0] groups,repeat_mask,issued,position;
    logic [6:0] active_lanes;
    logic [31:0] step;
    logic [2:0] drain_left,required_contexts;
    logic [1:0] context_id,seed_id;
    logic [LANES-1:0] update_valid;
    logic [31:0] current_root[0:LANES-1],update_result[0:LANES-1];
    // Cache the 17-bit period-minus-one on accepted start; zero wraps to all ones.
    assign position=issued&repeat_mask;
    assign context_id=issued[1:0];
    assign seed_id=position[1:0];
    assign use_seed=position<4;
    assign bypass=update_valid[0] && context_pipe[3]==context_id;
    assign request_ready=rst_n && state==RUN && issued<groups && (use_seed || available[context_id] || bypass);
    assign fire=request_valid && request_ready;
    assign seed_access=!(state==IDLE && start) && (!busy || seed_bank!=active_bank);
    assign seed_legal=int'(seed_lane)<LANES && seed_data<P;
    always_comb begin
        required_contexts=config_groups<4 ? 3'(config_groups) : 3'd4;
        if(config_period!=0 && config_period<17'(required_contexts))required_contexts=3'(config_period);
        config_ok=config_groups>=1 && config_groups<=65536 && config_active_lanes>=1 &&
                  int'(config_active_lanes)<=LANES && config_step<P && config_period<=65536 &&
                  (config_period==0 || (config_period&(config_period-17'd1))==0);
        for(int c=0;c<4;c=c+1)for(int j=0;j<LANES;j=j+1)
            if(c<int'(required_contexts) && j<int'(config_active_lanes) && !seed_valid[config_bank][c][j])config_ok=0;
    end
    for(genvar j=0;j<LANES;j=j+1)begin: lane
        assign current_root[j]=use_seed ? seeds[active_bank][seed_id][j] :
            bypass ? update_result[j] : context_value[context_id][j];
        genefer_montgomery_mul27_sparse_pipe #(.P(P),.Q(Q)) update_pipe (
            .clk,.rst_n,.in_valid(fire && j<int'(active_lanes)),
            .lhs(current_root[j]),.rhs(step),.out_valid(update_valid[j]),.result(update_result[j])
        );
        always_ff @(posedge clk)begin
            if(rst_n && seed_we && !seed_clear && seed_access && seed_legal && int'(seed_lane)==j)
                seeds[seed_bank][seed_context][j]<=seed_data;
            if(rst_n && busy && update_valid[j])context_value[context_pipe[3]][j]<=update_result[j];
        end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)roots[j*32+:32]<=0;
            else if(fire)roots[j*32+:32]<=j<int'(active_lanes) ? current_root[j] : 32'd0;
        end
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;busy<=0;done<=0;error<=0;seed_error<=0;cycles<=0;
            root_valid<=0;root_mask<=0;root_tag<=0;root_group<=0;
            groups<=0;repeat_mask<=17'h1ffff;issued<=0;active_lanes<=0;active_bank<=0;step<=0;drain_left<=0;
            available<=0;
            for(int c=0;c<4;c=c+1)begin
                context_pipe[c]<=0;seed_valid[0][c]<=0;seed_valid[1][c]<=0;
            end
        end else begin
            done<=0;seed_error<=0;root_valid<=fire;root_mask<=0;
            context_pipe[0]<=context_id;
            for(int c=1;c<4;c=c+1)context_pipe[c]<=context_pipe[c-1];
            if(busy)cycles<=cycles+1;
            if(busy && update_valid[0])available[context_pipe[3]]<=1;
            if(!(state==IDLE && start) && (seed_clear || seed_we))begin
                if(!seed_access || (!seed_clear && !seed_legal))seed_error<=1;
                else if(seed_clear)begin
                    for(int c=0;c<4;c=c+1)seed_valid[seed_bank][c]<=0;
                end else seed_valid[seed_bank][seed_context][SLW'(seed_lane)]<=1;
            end
            if(fire)begin
                root_tag<=request_tag;root_group<=issued;
                for(int j=0;j<LANES;j=j+1)root_mask[j]<=j<int'(active_lanes);
                available[context_id]<=0;issued<=issued+1;
                if(issued+1==groups)begin state<=DRAIN;drain_left<=4;end
            end
            case(state)
                IDLE:if(start)begin
                    cycles<=0;error<=0;available<=0;
                    if(!config_ok)begin error<=1;done<=1;end
                    else begin
                        busy<=1;state<=RUN;active_bank<=config_bank;groups<=config_groups;
                        repeat_mask<=config_period-17'd1;active_lanes<=config_active_lanes;step<=config_step;issued<=0;
                    end
                end
                DRAIN:begin
                    drain_left<=drain_left-1;
                    if(drain_left==1)begin state<=IDLE;busy<=0;done<=1;end
                end
                default:;
            endcase
        end
    end
    // synthesis translate_off
    initial if(LANES<1 || LANES>64 || TAG_W<1)$fatal(1,"invalid root recurrence parameters");
    always @(posedge clk)if(rst_n)begin
        if(state==RUN && issued<groups && !request_ready)$fatal(1,"unexpected root recurrence stall");
        for(int j=0;j<LANES;j=j+1)
            if(busy && update_valid[j]!=(update_valid[0] && j<int'(active_lanes)))$fatal(1,"root update lane skew");
    end
    // synthesis translate_on
endmodule

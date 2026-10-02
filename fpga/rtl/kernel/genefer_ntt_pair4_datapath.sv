// Shared two-butterfly adjacent-stage prototype, not a complete banked NTT.
// External memory supplies each requested root/data beat BEFORE its sampled
// read edge. Internal registers model its one-cycle synchronous response.
// A group is [a,b,c,d] in four-point dependency order, NOT physical bank order.
// No backpressure: issue timing is the separately gated fixed-latency schedule.
module genefer_ntt_pair4_datapath #(
    parameter int GROUP_AW=12,
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] Q=32'd4190109697
) (
    input logic clk,rst_n,start,dif,
    input logic [GROUP_AW:0] group_count,
    input logic [127:0] data_beat,
    input logic [63:0] root_beat,
    output logic busy,done,error,
    output logic root_read,root_second,data_read,
    output logic [GROUP_AW-1:0] root_group,
    output logic write_valid,
    output logic [GROUP_AW-1:0] write_group,
    output logic [127:0] write_data,
    output logic [GROUP_AW+4:0] active_cycles
);
    logic issue,issue_second,hold_first,commit,schedule_error;
    logic [GROUP_AW-1:0] issue_group,hold_group,commit_group;
    logic active_dif,fault;
    logic [31:0] input_words[0:3],held[0:3],roots[0:1];
    logic [31:0] u[0:1],v[0:1],y0[0:1],y1[0:1];
    logic [1:0] result_valid;
    logic [5:0] kind_pipe,valid_pipe;
    logic [GROUP_AW-1:0] group_pipe[0:5];
    logic root_kind_d;
    logic [GROUP_AW-1:0] root_group_d;

    genefer_ntt_pair_schedule #(.GROUP_AW(GROUP_AW)) schedule (
        .clk,.rst_n,.start,.group_count,.busy,.done,.error(schedule_error),
        .root_read,.root_second,.root_group,.issue,.issue_second,.issue_group,
        .hold_first,.hold_group,.commit,.commit_group,.active_cycles
    );
    assign data_read=root_read && !root_second;
    assign error=schedule_error || fault;
    // Reject a bad token on its prospective write edge, before sticky fault
    // can update. A registered fault alone permits one wrong-group write.
    assign write_valid=commit && (&result_valid) && valid_pipe[5] &&
                       kind_pipe[5] && (group_pipe[5]==commit_group) &&
                       !fault && !schedule_error;
    assign write_group=commit_group;
    always_comb begin
        if(!issue_second) begin
            u[0]=input_words[0];
            v[0]=active_dif ? input_words[2] : input_words[1];
            u[1]=active_dif ? input_words[1] : input_words[2];
            v[1]=input_words[3];
        end else begin
            u[0]=held[0];
            v[0]=active_dif ? held[1] : held[2];
            u[1]=active_dif ? held[2] : held[1];
            v[1]=held[3];
        end
        // DIF's second layer is adjacent; DIT's second layer is strided.
        write_data[0+:32]=y0[0];
        write_data[32+:32]=active_dif ? y1[0] : y0[1];
        write_data[64+:32]=active_dif ? y0[1] : y1[0];
        write_data[96+:32]=y1[1];
    end
    for(genvar lane=0;lane<2;lane=lane+1) begin: butterflies
        genefer_ntt_difdit_butterfly27 #(.P(P),.Q(Q)) butterfly (
            .clk,.rst_n,.in_valid(issue),.dif(active_dif),
            .u(u[lane]),.v(v[lane]),.w(roots[lane]),
            .out_valid(result_valid[lane]),.y0(y0[lane]),.y1(y1[lane])
        );
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            active_dif<=0;fault<=0;kind_pipe<=0;valid_pipe<=0;
            root_kind_d<=0;root_group_d<=0;
            for(int k=0;k<4;k=k+1) begin input_words[k]<=0;held[k]<=0;end
            for(int k=0;k<2;k=k+1) roots[k]<=0;
            for(int k=0;k<6;k=k+1) group_pipe[k]<=0;
        end else begin
            if(start && !busy) begin active_dif<=dif;fault<=0;end
            if(root_read) begin
                roots[0]<=root_beat[0+:32];roots[1]<=root_beat[32+:32];
                root_kind_d<=root_second;root_group_d<=root_group;
            end
            if(data_read)
                for(int k=0;k<4;k=k+1) input_words[k]<=data_beat[k*32+:32];
            kind_pipe<={kind_pipe[4:0],issue_second};
            valid_pipe<={valid_pipe[4:0],issue};
            group_pipe[0]<=issue_group;
            for(int k=1;k<6;k=k+1) group_pipe[k]<=group_pipe[k-1];
            if(issue && (root_kind_d!=issue_second || root_group_d!=issue_group)) fault<=1;
            if(hold_first) begin
                held[0]<=y0[0];
                held[1]<=active_dif ? y0[1] : y1[0];
                held[2]<=active_dif ? y1[0] : y0[1];
                held[3]<=y1[1];
                if(!(&result_valid) || !valid_pipe[5] || kind_pipe[5] || group_pipe[5]!=hold_group) fault<=1;
            end
            if(commit && (!(&result_valid) || !valid_pipe[5] || !kind_pipe[5] || group_pipe[5]!=commit_group)) fault<=1;
        end
    end
endmodule

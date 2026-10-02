// Experimental fixed-latency issue/tag controller, NOT an NTT engine.
// One unchanged six-stage butterfly array is shared by two adjacent layers.
// Relative to the first sampled read event, group g has:
// read A:2g; issue A:2g+1; hold A/read B roots:2g+7;
// issue B:2g+8; commit B:2g+14. No backpressure is supported.
// Data/group geometry, actual arithmetic and RAM ownership are outside this
// component. No frozen engine selects this controller.
module genefer_ntt_pair_schedule #(
    parameter int GROUP_AW=16
) (
    input logic clk, rst_n, start,
    input logic [GROUP_AW:0] group_count,
    output logic busy, done, error,
    output logic root_read, root_second,
    output logic [GROUP_AW-1:0] root_group,
    output logic issue, issue_second,
    output logic [GROUP_AW-1:0] issue_group,
    output logic hold_first,
    output logic [GROUP_AW-1:0] hold_group,
    output logic commit,
    output logic [GROUP_AW-1:0] commit_group,
    output logic [GROUP_AW+4:0] active_cycles
);
    localparam int TW=GROUP_AW+5;
    logic [TW-1:0] tick, twice_groups;
    logic read_a, read_b, issue_a, issue_b;

    always_comb begin
        read_a=busy && !tick[0] && tick<twice_groups;
        read_b=busy && tick[0] && tick>=TW'(7) && tick<twice_groups+TW'(7);
        issue_a=busy && tick[0] && tick>=TW'(1) && tick<twice_groups+TW'(1);
        issue_b=busy && !tick[0] && tick>=TW'(8) && tick<twice_groups+TW'(8);
        root_read=read_a || read_b;
        root_second=read_b;
        root_group='0;
        if(read_a) root_group=GROUP_AW'(tick>>1);
        if(read_b) root_group=GROUP_AW'((tick-TW'(7))>>1);
        issue=issue_a || issue_b;
        issue_second=issue_b;
        issue_group='0;
        if(issue_a) issue_group=GROUP_AW'((tick-TW'(1))>>1);
        if(issue_b) issue_group=GROUP_AW'((tick-TW'(8))>>1);
        hold_first=read_b;
        hold_group=read_b ? root_group : '0;
        commit=busy && !tick[0] && tick>=TW'(14) && tick<twice_groups+TW'(14);
        commit_group=commit ? GROUP_AW'((tick-TW'(14))>>1) : '0;
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            busy<=0;done<=0;error<=0;
            tick<='0;twice_groups<='0;active_cycles<='0;
        end else begin
            done<=0;
            if(!busy) begin
                if(start) begin
                    tick<='0;active_cycles<='0;
                    if(group_count==0 || group_count>({{GROUP_AW{1'b0}},1'b1}<<GROUP_AW)) begin
                        error<=1;done<=1;
                    end else begin
                        error<=0;busy<=1;twice_groups<=TW'(group_count)<<1;
                    end
                end
            end else begin
                // In-flight starts and group_count changes are ignored.
                active_cycles<=active_cycles+1'b1;
                if(tick==twice_groups+TW'(12)) begin
                    busy<=0;done<=1;
                end else tick<=tick+1'b1;
            end
        end
    end
    // synthesis translate_off
    initial if(GROUP_AW<1 || GROUP_AW>16) $fatal(1,"unsupported group width");
    // synthesis translate_on
endmodule

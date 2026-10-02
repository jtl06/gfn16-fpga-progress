// Source-only warm-field ownership/deadline shell. Two descriptors own late
// correction messages and terminal rows while forward/inverse frames overlap.
// Physical frame ordinals are regenerated from fixed occupied-row timing;
// epoch bits are descriptor registers, not silently added to every delay word.
// Integrating that specialization with the arithmetic requires native proof.
module genefer_stream27_epoch_protocol_v3 #(
    parameter int unsigned ROWS=8192,
    parameter int unsigned POINTWISE_FIRST=8308,
    parameter int unsigned SINK_FIRST=16618,
    parameter int unsigned EPOCH_W=16
) (
    input logic clk,rst_n,quarantine,external_fault_pending,
    input logic frame_begin,
    input logic [EPOCH_W-1:0] frame_epoch,
    input logic [7:0] frame_generation,
    input logic [31:0] frame_base,
    input logic correction_valid,
    input logic [EPOCH_W-1:0] correction_epoch,
    input logic [7:0] correction_generation,
    input logic cache_ready,
    input logic [EPOCH_W-1:0] cache_epoch,
    input logic [7:0] cache_generation,
    input logic pointwise_slot,pointwise_frame_start,
    input logic [7:0] pointwise_generation,
    input logic sink_slot,sink_frame_start,
    input logic [7:0] sink_generation,
    input logic context_enabled,
    input logic [7:0] live_generation,
    output logic correction_accept,
    output logic [31:0] correction_base,
    output logic pointwise_accept,commit_enable,
    output logic [EPOCH_W-1:0] pointwise_epoch,sink_epoch,
    output logic [$clog2(ROWS)-1:0] pointwise_row,sink_row,
    output logic [1:0] owner_count,
    output logic out_error,fault_pending
);
    localparam int ROW_W=$clog2(ROWS);
    logic [1:0] valid,received,ready;
    logic [EPOCH_W-1:0] epoch[0:1],next_epoch;
    logic [7:0] generation[0:1];
    logic [31:0] base[0:1],pw_first[0:1],sink_first[0:1];
    logic [31:0] cycle_count;
    logic sequence_initialized;
    logic bad,free_found,free_index,corr_found,corr_index,cache_found,cache_index;
    logic pw_found,pw_index,sink_found,sink_index;
    logic [31:0] pw_age[0:1],sink_age[0:1];
    logic [1:0] pw_matches,sink_matches;
    wire stop=quarantine || out_error;
    assign owner_count={1'b0,valid[0]}+{1'b0,valid[1]};
    always_comb begin
        bad=1'b0;free_found=1'b0;free_index=1'b0;
        corr_found=1'b0;corr_index=1'b0;cache_found=1'b0;cache_index=1'b0;
        pw_found=1'b0;pw_index=1'b0;sink_found=1'b0;sink_index=1'b0;
        pw_matches='0;sink_matches='0;
        correction_base='0;pointwise_epoch='0;sink_epoch='0;
        pointwise_row='0;sink_row='0;
        for(int i=0;i<2;i=i+1)begin
            pw_age[i]=cycle_count-pw_first[i];sink_age[i]=cycle_count-sink_first[i];
            if(!valid[i] && !free_found)begin free_found=1'b1;free_index=1'(i);end
            if(valid[i])begin
                if(correction_valid && correction_epoch==epoch[i] && correction_generation==generation[i])begin
                    if(corr_found)bad=1'b1;corr_found=1'b1;corr_index=1'(i);correction_base=base[i];
                    if(received[i])bad=1'b1;
                end
                if(cache_ready && cache_epoch==epoch[i] && cache_generation==generation[i])begin
                    if(cache_found)bad=1'b1;cache_found=1'b1;cache_index=1'(i);
                    if(!received[i] || ready[i])bad=1'b1;
                end
                if(pw_age[i]<32'(ROWS))begin
                    pw_matches[i]=1'b1;pw_found=1'b1;pw_index=1'(i);
                    pointwise_epoch=epoch[i];pointwise_row=ROW_W'(pw_age[i]);
                    if(pointwise_slot && (!ready[i] || pointwise_generation!=generation[i] ||
                       pointwise_frame_start!=(pw_age[i]==0)))bad=1'b1;
                end
                if(sink_age[i]<32'(ROWS))begin
                    sink_matches[i]=1'b1;sink_found=1'b1;sink_index=1'(i);
                    sink_epoch=epoch[i];sink_row=ROW_W'(sink_age[i]);
                    if(sink_slot && (sink_generation!=generation[i] ||
                       sink_frame_start!=(sink_age[i]==0)))bad=1'b1;
                end
                if(frame_begin && frame_epoch==epoch[i])bad=1'b1;
            end
        end
        if(frame_begin && (!free_found || (sequence_initialized && frame_epoch!=next_epoch)))bad=1'b1;
        // A coherent first correction may accompany its image's first row.
        if(correction_valid && !corr_found && frame_begin && free_found &&
           correction_epoch==frame_epoch && correction_generation==frame_generation)begin
            corr_found=1'b1;corr_index=free_index;correction_base=frame_base;
        end
        if(correction_valid && !corr_found)bad=1'b1;
        if(cache_ready && !cache_found)bad=1'b1;
        if(pw_matches==2'b11 || sink_matches==2'b11)bad=1'b1;
        if(pointwise_slot!=pw_found || sink_slot!=sink_found)bad=1'b1;
        if(!pointwise_slot && pointwise_frame_start)bad=1'b1;
        if(!sink_slot && sink_frame_start)bad=1'b1;
        fault_pending=out_error || (!stop && (bad || external_fault_pending));
        correction_accept=correction_valid && corr_found && !stop && !fault_pending;
        pointwise_accept=pointwise_slot && pw_found && !stop && !fault_pending;
        commit_enable=sink_slot && sink_found && context_enabled &&
                      sink_generation==live_generation && !stop && !fault_pending;
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            valid<='0;received<='0;ready<='0;cycle_count<='0;
            sequence_initialized<=1'b0;out_error<=1'b0;
        end else begin
            cycle_count<=cycle_count+32'd1;
            if(!stop && (bad || external_fault_pending))out_error<=1'b1;
            if(!stop && !fault_pending)begin
                if(frame_begin)begin
                    valid[free_index]<=1'b1;received[free_index]<=1'b0;ready[free_index]<=1'b0;
                    epoch[free_index]<=frame_epoch;generation[free_index]<=frame_generation;base[free_index]<=frame_base;
                    pw_first[free_index]<=cycle_count+32'(POINTWISE_FIRST);
                    sink_first[free_index]<=cycle_count+32'(SINK_FIRST);
                    next_epoch<=frame_epoch+EPOCH_W'(1);sequence_initialized<=1'b1;
                end
                if(correction_accept)received[corr_index]<=1'b1;
                if(cache_ready && cache_found)ready[cache_index]<=1'b1;
                if(sink_slot && sink_found && sink_row==ROW_W'(ROWS-1))begin
                    valid[sink_index]<=1'b0;received[sink_index]<=1'b0;ready[sink_index]<=1'b0;
                end
            end
        end
    end
    // synthesis translate_off
    initial if(ROWS<2 || (ROWS & (ROWS-1))!=0 || POINTWISE_FIRST<1 ||
               SINK_FIRST<=POINTWISE_FIRST || EPOCH_W<2 || EPOCH_W>24)
        $fatal(1,"EPOCH_PROTOCOL_PARAMETERS");
    // synthesis translate_on
endmodule

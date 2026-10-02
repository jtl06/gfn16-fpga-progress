// LOCAL PREPARATION ONLY: paired host-memory bench, not a production core.
// instance_enable is 2'b11 normally. A focused assertion subprocess enables
// only one instance so the first fatal identifies baseline versus candidate.
module host_broadcast_memory_pair #(
    parameter int AW=8,
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
) (
    input logic clk,rst_n,
    input logic [1:0] instance_enable,
    input logic load_we,read_en,vector_load_we,vector_read_en,start,inverse,dif,
    input logic [AW-1:0] host_addr,vector_addr,
    input logic [31:0] write_data,scale,
    input logic [15:0] vector_lane_mask,
    input logic [511:0] vector_write_data,
    input logic profile_begin,profile_we,profile_commit,
    input logic [4:0] profile_size_log2,size_log2,
    input logic [31:0] profile_modulus,profile_data,
    input logic [7:0] profile_format,
    input logic [15:0] profile_addr,
    input logic [1:0] root_phase,op,
    output logic [1:0] read_valid,vector_read_valid,host_error,
    output logic [63:0] read_data,
    output logic [31:0] vector_read_mask,
    output logic [1023:0] vector_read_data,
    output logic [1:0] profile_loaded,profile_loading,profile_error,busy,done,error,
    output logic [9:0] profile_loaded_size,
    output logic [31:0] profile_next_addr,
    output logic [127:0] seed_setup_cycles,cycles,butterflies,data_reads,data_writes,root_reads,wait_cycles,
    output logic [4:0] configured_aw,
    output logic [31:0] configured_p,configured_q
);
    assign configured_aw=5'(AW);
    assign configured_p=P;
    assign configured_q=Q;
`define HOST_BROADCAST_PORTS \
    .clk,.rst_n(rst_n && instance_enable[i]), \
    .load_we,.read_en,.host_addr,.write_data,.read_valid(read_valid[i]),.read_data(read_data[i*32+:32]), \
    .vector_load_we,.vector_read_en,.vector_addr,.vector_lane_mask,.vector_write_data, \
    .vector_read_valid(vector_read_valid[i]),.host_error(host_error[i]), \
    .vector_read_mask(vector_read_mask[i*16+:16]),.vector_read_data(vector_read_data[i*512+:512]), \
    .profile_begin,.profile_we,.profile_commit,.profile_size_log2,.profile_modulus,.profile_data,.profile_format,.profile_addr, \
    .profile_loaded(profile_loaded[i]),.profile_loading(profile_loading[i]),.profile_error(profile_error[i]), \
    .profile_loaded_size(profile_loaded_size[i*5+:5]),.profile_next_addr(profile_next_addr[i*16+:16]), \
    .seed_setup_cycles(seed_setup_cycles[i*64+:64]),.start,.inverse,.dif,.root_phase,.op,.size_log2,.scale, \
    .busy(busy[i]),.done(done[i]),.error(error[i]),.cycles(cycles[i*64+:64]),.butterflies(butterflies[i*64+:64]), \
    .data_reads(data_reads[i*64+:64]),.data_writes(data_writes[i*64+:64]),.root_reads(root_reads[i*64+:64]), \
    .wait_cycles(wait_cycles[i*64+:64])
    for(genvar i=0;i<2;i=i+1)begin: instances
        if(i==0)begin: baseline
            genefer_ntt_banked27_prefetch_r2_host_engine #(.AW(AW),.P(P),.Q(Q)) dut (`HOST_BROADCAST_PORTS);
        end else begin: candidate
            genefer_ntt_banked27_prefetch_r2_host_broadcast_engine #(.AW(AW),.P(P),.Q(Q)) dut (`HOST_BROADCAST_PORTS);
        end
    end
`undef HOST_BROADCAST_PORTS
endmodule

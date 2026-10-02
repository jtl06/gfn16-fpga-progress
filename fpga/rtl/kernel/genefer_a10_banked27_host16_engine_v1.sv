// SOURCE-ONLY exact G4 host adapter delta; explicit format3 abort/metrics.
// Isolated format2 experiment; source/model checks are not RTL validation.
// Isolated 16-word host adapter for the frozen 64-lane prefetch engine.
// Profile requests suppress ALL ordinary host access on that edge, even when
// malformed. start/busy retain the frozen child's semantics. No root_we alias.
module genefer_a10_banked27_host16_engine_v1 #(
    parameter int AW=16, LANES=64, HOST_LANES=16,
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
) (
    input logic clk,rst_n,load_we,read_en,
    input logic [AW-1:0] host_addr,
    input logic [31:0] write_data,
    output logic read_valid,
    output logic [31:0] read_data,
    input logic vector_load_we,vector_read_en,
    input logic [AW-1:0] vector_addr,
    input logic [HOST_LANES-1:0] vector_lane_mask,
    input logic [HOST_LANES*32-1:0] vector_write_data,
    output logic vector_read_valid,host_error,
    output logic [HOST_LANES-1:0] vector_read_mask,
    output logic [HOST_LANES*32-1:0] vector_read_data,
    input logic profile_begin,profile_we,profile_commit,profile_abort,
    input logic [4:0] profile_size_log2,
    input logic [31:0] profile_modulus,profile_data,
    input logic [7:0] profile_format,
    input logic [15:0] profile_addr,
    output logic profile_loaded,profile_loading,profile_error,
    output logic [4:0] profile_loaded_size,
    output logic [15:0] profile_next_addr,
    output logic [63:0] seed_setup_cycles,root_rom_reads,normalization_products,
    output logic [31:0] profile_epoch,
    input logic start,inverse,dif,
    input logic [1:0] root_phase,op,
    input logic [4:0] size_log2,
    input logic [31:0] scale,
    output logic busy,done,error,
    output logic [63:0] cycles,butterflies,data_reads,data_writes,root_reads,wait_cycles
);
    localparam int HLW=$clog2(HOST_LANES),GROUPS=LANES/HOST_LANES;
    localparam int GW=GROUPS>1 ? $clog2(GROUPS) : 1;
    logic request,profile_request,descriptor_ok,local_error,child_host_error;
    logic [31:0] host_n;
    logic [GW-1:0] host_group,read_group;
    logic [AW-1:0] child_addr;
    logic [LANES-1:0] child_mask,child_read_mask;
    logic [LANES*32-1:0] child_write_data,child_read_data;
    assign profile_request=profile_begin || profile_we || profile_commit || profile_abort;
    assign request=vector_load_we || vector_read_en;
    assign host_n=(size_log2>=1 && int'(size_log2)<=AW) ? 32'd1<<size_log2 : 0;
    assign descriptor_ok=host_n!=0 && (32'(vector_addr)&32'(HOST_LANES-1))==0 && 32'(vector_addr)<host_n;
    assign host_group=GW'((32'(vector_addr)>>HLW)&32'(GROUPS-1));
    assign child_addr=AW'(32'(vector_addr)&~32'(LANES-1));
    assign host_error=local_error || child_host_error;
    for(genvar h=0;h<LANES;h=h+1) begin: expand_host
        assign child_mask[h]=host_group==GW'(h/HOST_LANES) && vector_lane_mask[h%HOST_LANES];
        assign child_write_data[h*32+:32]=vector_write_data[(h%HOST_LANES)*32+:32];
    end
    for(genvar h=0;h<HOST_LANES;h=h+1) begin: narrow_response
        assign vector_read_mask[h]=child_read_mask[int'(read_group)*HOST_LANES+h];
        assign vector_read_data[h*32+:32]=child_read_data[(int'(read_group)*HOST_LANES+h)*32+:32];
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n)begin local_error<=0;read_group<=0;end
        else begin
            local_error<=!busy && !start && !profile_request && request && !descriptor_ok;
            if(!busy && !start && !profile_request && vector_read_en && !vector_load_we && descriptor_ok)
                read_group<=host_group;
        end
    end
    genefer_a10_banked27_engine_v1 #(.AW(AW),.LANES(LANES),.P(P),.Q(Q)) child (
        .clk,.rst_n,.load_we(load_we && !request && !profile_request),
        .read_en(read_en && !request && !profile_request),.host_addr,.write_data,.read_valid,.read_data,
        .vector_load_we(vector_load_we && descriptor_ok && !profile_request),
        .vector_read_en(vector_read_en && descriptor_ok && !profile_request),.vector_addr(child_addr),
        .vector_lane_mask(child_mask),.vector_write_data(child_write_data),
        .vector_read_valid,.host_error(child_host_error),.vector_read_mask(child_read_mask),
        .vector_read_data(child_read_data),
        .profile_begin,.profile_we,.profile_commit,.profile_abort,.profile_size_log2,.profile_modulus,
        .profile_data,.profile_format,.profile_addr,.profile_loaded,.profile_loading,.profile_error,
        .profile_loaded_size,.profile_next_addr,.seed_setup_cycles,.root_rom_reads,.normalization_products,.profile_epoch,
        .start,.inverse,.dif,.root_phase,.op,.size_log2,.scale,.busy,.done,.error,
        .cycles,.butterflies,.data_reads,.data_writes,.root_reads,.wait_cycles
    );
    // synthesis translate_off
    initial if(AW<1 || AW>16 || LANES!=64 || HOST_LANES!=16)
        $fatal(1,"unsupported prefetch host geometry");
    // synthesis translate_on
endmodule


// Minimal executable block-banked RAM/canonicalizer probe. Initial RAM contains
// signed EFFECTIVE digits; sparse-correction frontend is a separate integration gate.
module track_a4_canonical_controller_probe_v2 #(parameter int AW=5) (
    input logic clk,rst_n,begin_canonical,cancel,load_we,read_en,
    input logic [31:0] base,generation,
    input logic [AW-1:0] host_address,
    input logic signed [31:0] host_write_data,
    input logic inject_drop,inject_tag,inject_generation,inject_mem_error,
    output logic host_read_valid,
    output logic signed [31:0] host_read_data,
    output logic busy,done,error,minus_one,tail_checked,
    output logic [3:0] error_code,
    output logic [31:0] out_generation,max_digit,
    output logic [1:0] passes
);
    localparam int RW=AW-4,T=1<<RW;
    logic mem_read_en,apply_corrections,mem_read_valid;
    logic [AW-1:0] mem_read_address,mem_read_tag,write_offset;
    logic [31:0] mem_generation,read_generation;
    logic [15:0] write_mask;
    logic [511:0] write_words;
    logic clear_corrections,set_minus_one;
    logic [3:0] read_bank,host_bank;
    logic [31:0] q[0:15];
    wire host_access=!busy && !begin_canonical;
    wire [3:0] canonical_request_bank=4'(mem_read_address>>RW);
    wire [3:0] host_request_bank=4'(host_address>>RW);
    wire signed [32:0] effective_read=$signed({q[read_bank][31],q[read_bank]});
    genefer_track_a4_canonical_controller_v2 #(.AW(AW)) controller (
        .clk,.rst_n,.begin_canonical,.cancel,.base,.generation,.busy,.done,.error,.minus_one,.error_code,
        .out_generation,.max_digit,.passes,.mem_read_en,.mem_read_apply_corrections(apply_corrections),
        .mem_read_address,.mem_generation,.mem_read_valid(mem_read_valid && !inject_drop),
        .mem_error(inject_mem_error),.mem_read_value(effective_read),
        .mem_read_tag(mem_read_tag ^ (inject_tag ? AW'(1) : AW'(0))),
        .mem_read_generation(read_generation ^ (inject_generation ? 32'd1 : 32'd0)),
        .mem_write_mask(write_mask),.mem_write_offset(write_offset),.mem_write_words(write_words),
        .clear_corrections,.set_minus_one,.registered_child_tail_checked(tail_checked)
    );
    for(genvar bank=0;bank<16;bank=bank+1)begin: banks
        wire can_read=mem_read_en && int'(canonical_request_bank)==bank;
        wire host_read=host_access && read_en && !load_we && int'(host_request_bank)==bank;
        wire host_write=host_access && load_we && int'(host_request_bank)==bank;
        genefer_sdp_ram32 #(.AW(RW),.DEPTH(T)) ram (
            .clk,.rst_n,.read_en(can_read || host_read),.write_en(write_mask[bank] || host_write),
            .read_addr(can_read ? RW'(mem_read_address) : RW'(host_address)),
            .write_addr(write_mask[bank] ? RW'(write_offset) : RW'(host_address)),
            .write_data(write_mask[bank] ? write_words[bank*32+:32] : host_write_data),.read_data(q[bank])
        );
    end
    assign host_read_data=$signed(q[host_bank]);
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            mem_read_valid<=0;mem_read_tag<=0;read_generation<=0;read_bank<=0;
            host_read_valid<=0;host_bank<=0;
        end else begin
            mem_read_valid<=mem_read_en;
            if(mem_read_en)begin mem_read_tag<=mem_read_address;read_generation<=mem_generation;read_bank<=4'(mem_read_address>>RW);end
            host_read_valid<=host_access && read_en && !load_we;
            if(host_access && read_en && !load_we)host_bank<=4'(host_address>>RW);
        end
    end
endmodule

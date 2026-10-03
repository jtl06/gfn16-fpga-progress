// Isolated simple-dual-port RAM template for early synthesis inference.
// Reset gates accesses; it does not clear memory or reset the read register.
// Read data is registered on an enabled edge; otherwise it holds.
// Mixed-port same-address read/write is outside the caller contract.
module genefer_sdp_ram32 #(parameter int AW=13, DEPTH=1<<AW) (
    input logic clk, rst_n, read_en, write_en,
    input logic [AW-1:0] read_addr, write_addr,
    input logic [31:0] write_data,
    output logic [31:0] read_data
);
    (* ramstyle="M20K, no_rw_check" *) logic [31:0] mem [0:DEPTH-1];
    always_ff @(posedge clk) begin
        if(rst_n && read_en) read_data<=mem[read_addr];
        if(rst_n && write_en) mem[write_addr]<=write_data;
    end
    // synthesis translate_off
    always @(posedge clk) if(rst_n) begin
        if(read_en && int'(read_addr)>=DEPTH) $fatal(1,"RAM read outside depth");
        if(write_en && int'(write_addr)>=DEPTH) $fatal(1,"RAM write outside depth");
        if(read_en && write_en && read_addr==write_addr) $fatal(1,"RAM mixed-port collision");
    end
    // synthesis translate_on
endmodule

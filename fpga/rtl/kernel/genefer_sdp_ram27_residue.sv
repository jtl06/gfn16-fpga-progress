// Canonical residue storage only. External words and Montgomery radix remain32.
// Same enabled-edge read/hold/reset-gating contract as genefer_sdp_ram32.
// Uninitialized locations and mixed-port collisions remain outside the contract.
module genefer_sdp_ram27_residue #(parameter int AW=13, DEPTH=1<<AW) (
    input logic clk, rst_n, read_en, write_en,
    input logic [AW-1:0] read_addr, write_addr,
    input logic [31:0] write_data,
    output logic [31:0] read_data
);
    (* ramstyle="M20K, no_rw_check" *) logic [26:0] mem [0:DEPTH-1];
    logic [26:0] read_q;
    assign read_data={5'b0,read_q};
    always_ff @(posedge clk) begin
        if(rst_n && read_en) read_q<=mem[read_addr];
        if(rst_n && write_en) mem[write_addr]<=write_data[26:0];
    end
    // synthesis translate_off
    always @(posedge clk) if(rst_n) begin
        if(read_en && int'(read_addr)>=DEPTH) $fatal(1,"RAM read outside depth");
        if(write_en && int'(write_addr)>=DEPTH) $fatal(1,"RAM write outside depth");
        if(write_en && write_data[31:27]!=0) $fatal(1,"RAM residue write exceeds27 bits");
        if(read_en && write_en && read_addr==write_addr) $fatal(1,"RAM mixed-port collision");
    end
    // synthesis translate_on
endmodule

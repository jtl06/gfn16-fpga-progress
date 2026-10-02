// Module-scoped single-port RAM for early block-memory inference.
// Reset gates access; neither memory nor the synchronous read register resets.
// An enabled write does not update read_data. Disabled cycles hold read_data.
module genefer_sp_ram #(parameter int WIDTH=96, AW=12, DEPTH=1<<AW) (
    input logic clk, rst_n, en, write_en,
    input logic [AW-1:0] addr,
    input logic [WIDTH-1:0] write_data,
    output logic [WIDTH-1:0] read_data
);
    (* ramstyle="M20K" *) logic [WIDTH-1:0] mem[0:DEPTH-1];
    always_ff @(posedge clk)begin
        if(rst_n && en)begin
            if(write_en)mem[addr]<=write_data;
            else read_data<=mem[addr];
        end
    end
    // synthesis translate_off
    always @(posedge clk)if(rst_n && en && int'(addr)>=DEPTH)
        $fatal(1,"single-port RAM address outside depth");
    // synthesis translate_on
endmodule

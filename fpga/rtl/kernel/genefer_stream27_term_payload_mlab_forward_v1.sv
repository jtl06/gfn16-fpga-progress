// Private inference experiment: exact asynchronous visible RAM semantics,
// explicit post-write forwarding. No collision don't-care/extra read latency.
module genefer_stream27_term_payload_mlab_forward_v1 (
    input logic clk,write_enable,
    input logic [2:0] write_address,read_address,
    input logic [26:0] write_data,
    output logic [26:0] read_data
);
    (* ramstyle = "MLAB" *) logic [26:0] memory[0:7];
    logic last_write_valid;
    logic [2:0] last_write_address;
    logic [26:0] last_write_data;
    // Last-edge write values replace the raw output only after sampling.
    // Before the current edge, a new write cannot alter the visible old word.
    assign read_data = last_write_valid && read_address==last_write_address ?
                       last_write_data : memory[read_address];
    always_ff @(posedge clk)begin
        last_write_valid<=write_enable;
        if(write_enable)begin
            memory[write_address]<=write_data;
            last_write_address<=write_address;
            last_write_data<=write_data;
        end
    end
endmodule

// Private storage2 experiment: one reset-free async read and qualified write.
// No no_rw_check waiver. The parent keeps validity/full owner and E4 bypass.
module genefer_stream27_term_payload_mlab_v1 (
    input logic clk,write_enable,
    input logic [2:0] write_address,read_address,
    input logic [26:0] write_data,
    output logic [26:0] read_data
);
    (* ramstyle = "MLAB" *) logic [26:0] memory[0:7];
    assign read_data=memory[read_address];
    always_ff @(posedge clk)if(write_enable)memory[write_address]<=write_data;
endmodule

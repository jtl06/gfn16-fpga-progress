module native_infrastructure_smoke_v1 (
    input logic clk, rst_n, valid,
    input logic [31:0] data_in,
    output logic out_valid,
    output logic [31:0] data_out
);
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            out_valid <= 1'b0;
            data_out <= '0;
        end else begin
            out_valid <= valid;
            if (valid) data_out <= data_in ^ 32'ha5c39e71;
        end
    end
endmodule

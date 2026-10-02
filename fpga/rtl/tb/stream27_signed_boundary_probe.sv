// Three exact field instances; one AW per independently approved native build.
module stream27_signed_boundary_probe #(
    parameter int AW=16
) (
    input logic clk,rst_n,in_valid,boundary_high,
    input logic signed [31:0] correction,
    input logic [31:0] base,
    input logic [15:0] payload_in,
    output logic [2:0] out_valid,out_error,
    output logic [95:0] residue,
    output logic [47:0] payload_out
);
    localparam logic [31:0] PRIME[0:2]='{32'd104857601,32'd69206017,32'd67239937};
    for(genvar field=0;field<3;field=field+1)begin: fields
        genefer_stream27_signed_boundary_reduce27_pipe #(
            .P(PRIME[field]),.AW(AW),.BLOCKS(8),.PAYLOAD_W(16)
        ) child (
            .clk,.rst_n,.in_valid,.boundary_high,.correction,.base,.payload_in,
            .out_valid(out_valid[field]),.out_error(out_error[field]),
            .residue(residue[field*32+:32]),.payload_out(payload_out[field*16+:16])
        );
    end
endmodule

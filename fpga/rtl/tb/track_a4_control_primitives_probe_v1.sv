module track_a4_control_primitives_probe_v1 #(parameter int AW=5) (
    input logic clk,rst_n,cancel,setup_begin,
    input logic [31:0] setup_base,setup_generation,
    output logic setup_busy,setup_done,setup_error,config_valid,
    output logic [31:0] accepted_base,out_generation,
    output logic [76:0] coefficient_limit,
    output logic [95:0] reciprocal,
    input logic cell_in_valid,
    input logic [31:0] cell_base,
    input logic signed [32:0] cell_value,
    input logic signed [2:0] cell_carry_in,
    input logic [15:0] cell_tag,
    output logic cell_valid,cell_error,
    output logic [31:0] cell_digit,
    output logic signed [2:0] cell_carry,
    output logic [15:0] cell_tag_out
);
    genefer_track_a4_setup_v1 #(.AW(AW)) setup_unit (
        .clk,.rst_n,.begin_setup(setup_begin),.cancel,.base(setup_base),.generation(setup_generation),
        .busy(setup_busy),.done(setup_done),.error(setup_error),.config_valid,.accepted_base,.out_generation,
        .coefficient_limit,.reciprocal
    );
    genefer_track_a4_canonical_cell_v1 #(.AW(AW),.PAYLOAD_W(16)) canonical_cell (
        .clk,.rst_n,.in_valid(cell_in_valid),.base(cell_base),.value(cell_value),.carry_in(cell_carry_in),
        .payload_in(cell_tag),.out_valid(cell_valid),.out_error(cell_error),.digit(cell_digit),
        .carry_out(cell_carry),.payload_out(cell_tag_out)
    );
endmodule

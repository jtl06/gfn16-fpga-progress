module genefer_stream27_correction_serial_p16_f2_v1 #(parameter int GEN_W=24) (
 input logic clk,rst_n,in_slot_valid,frame_start,quarantine,context_enabled,
 input logic [GEN_W-1:0] generation_in,live_generation,
 input logic [431:0] data_in,
 output logic out_slot_valid,out_frame_start,out_eligible,out_error,fault_pending,
 output logic [GEN_W-1:0] generation_out,
 output logic [431:0] data_out);
 genefer_stream27_correction_serial_v1 #(.LANES(16),.GEN_W(GEN_W),
 .MODULUS(32'd67239937),.Q(32'd4227727361),.ROOTS(864'h703ff82e07ff05c0ffe0b81ffc1703ff82e07ff05c0ffe0b81ffc16b94ab2d729565ae52acb5ca559703ff82e07ff05c0ffe0b81ffc1354170e6a82e1c3fb91307f72266b94ab2d729565c0ffe0b81ffc16169756b00aab9991772ae9b271354170e1fdc899ae52acb81ffc1)) engine (.*);
endmodule

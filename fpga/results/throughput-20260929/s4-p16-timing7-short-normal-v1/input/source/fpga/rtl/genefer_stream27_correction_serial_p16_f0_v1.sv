module genefer_stream27_correction_serial_p16_f0_v1 #(parameter int GEN_W=24) (
 input logic clk,rst_n,in_slot_valid,frame_start,quarantine,context_enabled,
 input logic [GEN_W-1:0] generation_in,live_generation,
 input logic [431:0] data_in,
 output logic out_slot_valid,out_frame_start,out_eligible,out_error,fault_pending,
 output logic [GEN_W-1:0] generation_out,
 output logic [431:0] data_out);
 genefer_stream27_correction_serial_v1 #(.LANES(16),.GEN_W(GEN_W),
 .MODULUS(32'd104857601),.Q(32'd4190109697),.ROOTS(864'hbffffb17ffff62ffffec5ffffd8bffffb17ffff62ffffec5ffffd878ccccef19999de33333bc66667bffffb17ffff62ffffec5ffffd86836e26d06dc4e6d7194cdae32978ccccef19999effffec5ffffd8c43b83028e63061ef341cc45cdb6836e2736b8ca5e33333dffffd8)) engine (.*);
endmodule

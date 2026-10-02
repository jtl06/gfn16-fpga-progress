module genefer_stream27_correction_serial_p16_f1_v1 #(parameter int GEN_W=24) (
 input logic clk,rst_n,in_slot_valid,frame_start,quarantine,context_enabled,
 input logic [GEN_W-1:0] generation_in,live_generation,
 input logic [431:0] data_in,
 output logic out_slot_valid,out_frame_start,out_eligible,out_error,fault_pending,
 output logic [GEN_W-1:0] generation_out,
 output logic [431:0] data_out);
 genefer_stream27_correction_serial_v1 #(.LANES(16),.GEN_W(GEN_W),
 .MODULUS(32'd69206017),.Q(32'd4225761281),.ROOTS(864'h7fff840ffff081fffe103fffc207fff840ffff081fffe103fffc253f03eaa7e07d54fc0faa9f81f507fff840ffff081fffe103fffc2358d7426b1ae860f144341e288653f03eaa7e07d41fffe103fffc24a5e286e948088de21f184be001358d743078a2194fc0fa83fffc2)) engine (.*);
endmodule

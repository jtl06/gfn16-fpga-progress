// Same scalar digit/readback contract; explicit finite batch extension.
// Host done includes real canonicalization AND copying every signed32 word.
module genefer_stream27_host_chain_t5b_paired_aw16_p16_diet_v1 #(parameter int CORR_SERIAL_BFS=2,COMM_STAGE_SHARED_MLAB=1,MONT_FACTORED=1,parameter int CANONICAL_PIPE_STAGES=1,parameter int unsigned EPOCH_SEED=0,parameter int AW=16,P=16,CONTEXTS=1) (
 input logic clk,rst_n,load_we,read_en,start,
 input logic [AW-1:0] host_addr,input logic signed [31:0] write_data,
 input logic [31:0] base,input logic double_bit,
 input logic batch_mode,input logic [31:0] warm_count,double_mask,
 output logic read_valid,output logic signed [95:0] read_data,
 output logic busy,done,error,
 output logic [63:0] cycles,conversion_cycles,root_cycles,ntt_cycles,crt_cycles,carry_cycles,
 output logic [6:0] carry_passes,output logic profile_cache_valid,profile_loads,profile_hits,
 output logic [15:0] profile_words_loaded,output logic [63:0] seed_setup_cycles,
 output logic warm_done,output logic [31:0] completed_squares,
 output logic [63:0] canonical_cycles,image_copy_cycles,
 input logic feed_mode,command_valid,command_double,
 input logic [31:0] command_index,input logic [7:0] command_generation,
 output logic command_ready,command_accept,operation_accept,
 output logic [7:0] accepted_generation,output logic [2:0] feed_level,
 output logic [31:0] operations_started,commands_enqueued,commands_consumed,final_image_rows,
 output logic [3:0] feed_error_code,
 output logic canonical_ready,
 input logic t5b_load_we,t5b_read_en,t5b_start,t5b_double_bit,
 input logic [AW-1:0] t5b_host_addr,input logic signed [31:0] t5b_write_data,
 output logic t5b_read_valid,t5b_busy,t5b_done,t5b_error,
 output logic signed [95:0] t5b_read_data);
 genefer_stream27_host_chain_aw16_p16_diet_v1 #(.EPOCH_SEED(EPOCH_SEED),.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) candidate (.*);
 genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1 #(.AW(AW),.NTT_LANES(64)) production (
  .clk,.rst_n,.load_we(t5b_load_we),.read_en(t5b_read_en),.start(t5b_start),
  .host_addr(t5b_host_addr),.write_data(t5b_write_data),.base,.double_bit(t5b_double_bit),
  .read_valid(t5b_read_valid),.read_data(t5b_read_data),.busy(t5b_busy),.done(t5b_done),.error(t5b_error),
  .cycles(),.conversion_cycles(),.root_cycles(),.ntt_cycles(),.crt_cycles(),.carry_cycles(),.carry_passes(),
  .profile_cache_valid(),.profile_loads(),.profile_hits(),.profile_words_loaded(),.seed_setup_cycles());
 // synthesis translate_off
 initial if(CORR_SERIAL_BFS!=2 || COMM_STAGE_SHARED_MLAB!=1 || MONT_FACTORED!=1 || CANONICAL_PIPE_STAGES!=1)$fatal(1,"S4_CANONICAL_PIPE_BUILD_FLAG");
 // synthesis translate_on
endmodule

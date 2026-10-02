// SOURCE-ONLY A4 integration skeleton: interface contract, NOT an executable core.
// Does not replace the T5 host API or claim native correctness/cycle equivalence.
// Connect a separately qualified controller, setup unit, canonicalizer and
// square datapath before this interface can form a usable whole-core wrapper.
interface genefer_track_a4_control_contract_v1 #(parameter int AW=16) (
    input logic clk,rst_n
);
    localparam logic [2:0] RELOAD_BEGIN=3'd0,LOAD_WORD=3'd1,READ=3'd2,
        WRITE=3'd3,SET_BASE=3'd4,SQUARE=3'd5;

    // Host accepts a command ONLY on cmd_valid&&cmd_ready. Fields are latched
    // then; changing base/double/address while busy cannot alter the operation.
    // A response holds every field until rsp_valid&&rsp_ready. One outstanding
    // command. RELOAD_BEGIN and reset are the only quarantine recovery paths.
    logic cmd_valid,cmd_ready,rsp_valid,rsp_ready;
    logic [2:0] cmd_opcode,rsp_opcode;
    logic [AW-1:0] cmd_address;
    logic signed [31:0] cmd_word,rsp_word;
    logic [31:0] cmd_base;
    logic cmd_double,rsp_error;
    logic [7:0] rsp_error_code;
    logic [31:0] rsp_generation;
    logic busy,fault_sticky,image_valid,prefill_valid;
    logic [31:0] image_generation;

    // One shared97-edge setup per accepted reload/base change, never16 lane
    // copies. exact A=2*((N+48)*B^2+64*B*K+16*K^2), B=base-1,K=2N+384.
    // base>=max(2N+5,ceil(2K/3)+1),base<=1e9; A<2^77 and centered CRT limit.
    // reciprocal is EXACT floor(2^96/base). No lane begin before setup_done,
    // tag/base match, and complete97-step division/bound checks.
    logic setup_begin,setup_done,setup_error;
    logic [31:0] setup_base,setup_generation,setup_out_generation;
    logic [76:0] setup_coefficient_limit;
    logic [95:0] setup_reciprocal;

    // Existing A4 lanes and block-route successors sit below square_datapath.
    // The final boundary low/high pair rotates from k to(k+1)%16; negate BOTH
    // only at15->0. Retain32 first-digit shadows. Patch d and signed c through
    // separate legal reducers, modular add, register, then write field RAM.
    logic square_begin,square_done,square_error,square_double,square_prefilled;
    logic [31:0] square_base,square_generation,square_out_generation;
    logic [76:0] square_coefficient_limit;
    logic [95:0] square_reciprocal;
    logic [AW:0] square_coefficients_seen,square_digits_written;
    logic [5:0] square_patch_words_written;
    logic square_registered_child_tail_checked,square_root_profile_coherent;

    // Canonicalization reads the COMPLETE effective d/c image in natural order.
    // Each pass has1R1W digit RAM: readE0, normalizeE1, writeE2; final write
    // atN+1, registered-error checkN+2. Fold finalq with next initialcarry=-q.
    // Terminal q=1/allzero or q=-1/allmax is canonical -1, not another fold.
    // At most3passes; special result materializes zeroRAM inN/16 writes,
    // then c0[0]=-1 and all other c0/c1=0 with a final write/error barrier.
    // Canonical cell requires its OWN guard: effective y may be<-Q of the
    // existing S3 small cell. Use -max(B,K)<=y<=max(2B,B+K),carry[-2,2].
    logic canonical_begin,canonical_done,canonical_error,canonical_minus_one;
    logic [31:0] canonical_base,canonical_generation,canonical_out_generation;
    logic [1:0] canonical_passes;
    logic [31:0] canonical_max_digit;
    logic canonical_registered_child_tail_checked;

    // Single host word operation after required canonicalization: issue one
    // synchronous RAM access, then capture/check its registered response.
    // Budget2edges. LOAD_WORD uses the same write/check before acknowledging.
    // A canonical -1 is logically[-1,0,...] but storedzeroRAM+c0[0]=-1:
    // replacing address0 must clear that c0 before storing the replacement.
    logic host_word_begin,host_word_write,host_word_done,host_word_error;
    logic [AW-1:0] host_word_address;
    logic signed [31:0] host_word_write_data,host_word_read_data;
    logic [31:0] host_word_generation,host_word_out_generation;

    // A held successful response never grants continued eligibility after a
    // later fault: fault_sticky is separate and can invalidate image_valid.
    // Cancellation flushes generation/valid eligibility; no RAM rollback promise.
    logic registered_child_fault,cancel;
    logic [31:0] cancel_generation;

    modport host (
        input clk,rst_n,cmd_ready,rsp_valid,rsp_opcode,rsp_word,rsp_error,rsp_error_code,
              rsp_generation,busy,fault_sticky,image_valid,prefill_valid,image_generation,
        output cmd_valid,cmd_opcode,cmd_address,cmd_word,cmd_base,cmd_double,rsp_ready
    );
    modport controller (
        input clk,rst_n,cmd_valid,cmd_opcode,cmd_address,cmd_word,cmd_base,cmd_double,rsp_ready,
              setup_done,setup_error,setup_out_generation,setup_coefficient_limit,setup_reciprocal,
              square_done,square_error,square_out_generation,square_coefficients_seen,
              square_digits_written,square_patch_words_written,square_registered_child_tail_checked,square_root_profile_coherent,
              canonical_done,canonical_error,canonical_minus_one,canonical_out_generation,
              canonical_passes,canonical_max_digit,canonical_registered_child_tail_checked,
              host_word_done,host_word_error,host_word_read_data,host_word_out_generation,registered_child_fault,
        output cmd_ready,rsp_valid,rsp_opcode,rsp_word,rsp_error,rsp_error_code,rsp_generation,
               busy,fault_sticky,image_valid,prefill_valid,image_generation,
               setup_begin,setup_base,setup_generation,
               square_begin,square_double,square_prefilled,square_base,square_generation,
               square_coefficient_limit,square_reciprocal,
               canonical_begin,canonical_base,canonical_generation,
               host_word_begin,host_word_write,host_word_address,host_word_write_data,host_word_generation,
               cancel,cancel_generation
    );
    modport setup_unit (
        input clk,rst_n,setup_begin,setup_base,setup_generation,cancel,cancel_generation,
        output setup_done,setup_error,setup_out_generation,setup_coefficient_limit,setup_reciprocal
    );
    modport square_datapath (
        input clk,rst_n,square_begin,square_double,square_prefilled,square_base,square_generation,
              square_coefficient_limit,square_reciprocal,cancel,cancel_generation,
        output square_done,square_error,square_out_generation,square_coefficients_seen,
               square_digits_written,square_patch_words_written,square_registered_child_tail_checked,square_root_profile_coherent
    );
    modport canonicalizer (
        input clk,rst_n,canonical_begin,canonical_base,canonical_generation,cancel,cancel_generation,
        output canonical_done,canonical_error,canonical_minus_one,canonical_out_generation,
               canonical_passes,canonical_max_digit,canonical_registered_child_tail_checked
    );
    modport host_word_port (
        input clk,rst_n,host_word_begin,host_word_write,host_word_address,host_word_write_data,
              host_word_generation,cancel,cancel_generation,
        output host_word_done,host_word_error,host_word_read_data,host_word_out_generation
    );
endinterface

// SOURCE-ONLY S3 candidate: accepted edge k responds at k+4, II=1.
// A frozen four-stage magnitude path (D3) plus one sign-output register.
// Full signed32 c0/c1 words are checked before magnitude narrowing; data are
// ordinary residues. Controller owns base/generation coherence and quarantine.
module genefer_stream27_signed_boundary_reduce27_pipe #(
    parameter logic [31:0] P=32'd104857601,
    parameter int AW=16,
    parameter int BLOCKS=8,
    parameter int PAYLOAD_W=1
) (
    input logic clk,rst_n,in_valid,boundary_high,
    input logic signed [31:0] correction,
    input logic [31:0] base,
    input logic [PAYLOAD_W-1:0] payload_in,
    output logic out_valid,out_error,
    output logic [31:0] residue,
    output logic [PAYLOAD_W-1:0] payload_out
);
    localparam logic [63:0] N=64'd1<<AW;
    localparam logic [63:0] K=64'd2*N+64'd24*64'(BLOCKS);
    localparam logic [63:0] BASE_MIN_A=64'd2*N+64'd5;
    localparam logic [63:0] BASE_MIN_B=(64'd2*K+64'd2)/64'd3+64'd1;
    localparam logic [63:0] BASE_MIN=BASE_MIN_A>BASE_MIN_B ? BASE_MIN_A : BASE_MIN_B;
    localparam bit GEOMETRY_OK=AW>=5 && AW<=16 && BLOCKS>=1 &&
        (BLOCKS & (BLOCKS-1))==0 && 64'(BLOCKS)<=N/64'd2;
    localparam bit FIELD_OK=P==32'd104857601 || P==32'd69206017 || P==32'd67239937;

    wire signed [32:0] wide_correction={correction[31],correction};
    wire [32:0] magnitude=correction[31] ? 33'(-wide_correction) : 33'(wide_correction);
    wire [32:0] admitted_limit=boundary_high ? 33'(K) : {1'b0,base}-33'd1;
    wire legal=GEOMETRY_OK && FIELD_OK && base>=32'(BASE_MIN) &&
        base<=32'd1000000000 && magnitude<=admitted_limit;
    // 0x80000000 is never legal in the frozen magnitude reducer. Passing a
    // rejected token as that poison preserves the child's exact D3 error/tag
    // path; 0xffffffff must NOT be used because it means legal signed -1 there.
    wire [31:0] magnitude_digit=legal ? magnitude[31:0] : 32'h80000000;
    logic magnitude_valid,magnitude_error;
    logic [31:0] magnitude_residue;
    logic [PAYLOAD_W:0] magnitude_payload;
    genefer_digit_reduce27_pipe #(.P(P),.PAYLOAD_W(PAYLOAD_W+1)) magnitude_path (
        .clk,.rst_n,.in_valid,.digit(magnitude_digit),
        .payload_in({correction[31],payload_in}),
        .out_valid(magnitude_valid),.out_error(magnitude_error),
        .residue(magnitude_residue),.payload_out(magnitude_payload)
    );
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            out_valid<=0;out_error<=0;residue<=0;payload_out<='0;
        end else begin
            out_valid<=magnitude_valid;
            out_error<=magnitude_error;
            if(magnitude_valid) begin
                // A negative multiple of P has residue0, not the noncanonical P.
                residue<=magnitude_payload[PAYLOAD_W] && magnitude_residue!=0 ?
                    P-magnitude_residue : magnitude_residue;
            end
            if(magnitude_valid || magnitude_error)payload_out<=magnitude_payload[PAYLOAD_W-1:0];
        end
    end
    // synthesis translate_off
    initial begin
        if(!GEOMETRY_OK)$fatal(1,"stream27 boundary reducer geometry");
        if(!FIELD_OK)$fatal(1,"stream27 boundary reducer field");
        if(PAYLOAD_W<1)$fatal(1,"stream27 boundary reducer payload width");
    end
    always @(posedge clk)if(rst_n)begin
        if(in_valid && legal && (magnitude>33'd999999999 || magnitude[32]))
            $fatal(1,"stream27 boundary reducer admitted magnitude");
        if(magnitude_valid && (magnitude_error || magnitude_residue>=P))
            $fatal(1,"stream27 boundary reducer magnitude output");
        if(out_valid && (out_error || residue>=P))
            $fatal(1,"stream27 boundary reducer signed output");
    end
    // synthesis translate_on
endmodule

// Isolated mapping experiment, NOT a modular multiplier or NTT replacement.
// Fixed 36-bit host inputs/72-bit output; WIDTH27 requires canonical 27-bit inputs.
// Three registered stages: acceptance at edge k -> result at edge k+2; II=1.
module genefer_raw_mul_probe #(
    parameter integer WIDTH=36,
    parameter bit SPLIT18=0
) (
    input logic clk, rst_n, in_valid,
    input logic [35:0] lhs, rhs,
    output logic out_valid,
    output logic [71:0] result
);
    logic [WIDTH-1:0] a_s0,b_s0;
    logic [1:0] valid_pipe;
    wire [71:0] product;
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            a_s0<='0; b_s0<='0; valid_pipe<='0; out_valid<=0; result<='0;
        end else begin
            valid_pipe<={valid_pipe[0],in_valid}; out_valid<=valid_pipe[1];
            if(in_valid) begin a_s0<=lhs[WIDTH-1:0]; b_s0<=rhs[WIDTH-1:0]; end
            if(valid_pipe[1]) result<=product;
        end
    end
    generate if(SPLIT18 && WIDTH==36) begin: split
        logic [35:0] ll,lh,hl,hh;
        always_ff @(posedge clk or negedge rst_n) begin
            if(!rst_n) begin ll<='0;lh<='0;hl<='0;hh<='0;end
            else if(valid_pipe[0]) begin
                ll<=a_s0[17:0]*b_s0[17:0];
                lh<=a_s0[17:0]*b_s0[35:18];
                hl<=a_s0[35:18]*b_s0[17:0];
                hh<=a_s0[35:18]*b_s0[35:18];
            end
        end
        assign product={36'b0,ll}+{18'b0,lh,18'b0}
                      +{18'b0,hl,18'b0}+{hh,36'b0};
    end else begin: direct
        logic [2*WIDTH-1:0] ab;
        always_ff @(posedge clk or negedge rst_n) begin
            if(!rst_n) ab<='0;
            else if(valid_pipe[0]) ab<=a_s0*b_s0;
        end
        assign product={{(72-2*WIDTH){1'b0}},ab};
    end endgenerate
    // synthesis translate_off
    initial begin
        if(WIDTH!=27 && WIDTH!=36) $fatal(1,"unsupported raw multiplier width");
        if(SPLIT18 && WIDTH!=36) $fatal(1,"split18 requires WIDTH36");
    end
    always @(posedge clk) if(rst_n && in_valid && WIDTH==27 &&
                           ((lhs>>27)!=0 || (rhs>>27)!=0))
        $fatal(1,"raw27 input exceeds width");
    // synthesis translate_on
endmodule

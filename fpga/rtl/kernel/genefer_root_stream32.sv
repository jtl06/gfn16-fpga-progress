// Fixed-size N=2^AW root-table generator, one output per cycle after start.
// Four interleaved power sequences hide the four-cycle multiplier feedback.
// phase 0: psi^i*R; 1: omega^i*R; 2: omega^-i*R;
// phase 3: psi^-i/N (ordinary residues for fused inverse/postconversion).
// All powers below are elaboration-time constants, not hardware dividers.
module genefer_root_stream32 #(
    parameter int AW=16,
    parameter logic [31:0] P=32'd2130706433,
    parameter logic [31:0] Q=32'd2164260865,
    parameter logic [31:0] GENERATOR=32'd3
) (
    input logic clk, rst_n, start,
    input logic [1:0] phase,
    output logic busy, done, error, root_valid,
    output logic [AW-1:0] root_addr,
    output logic [31:0] root_data
);
    function automatic logic [31:0] cmul(input logic [31:0] x, y);
        logic [63:0] wide;
        begin wide=64'(x)*64'(y); cmul=32'(wide%64'(P)); end
    endfunction
    function automatic logic [31:0] cpow(input logic [31:0] x, exponent);
        logic [31:0] result, power;
        begin
            result=1; power=x;
            for(int k=0;k<32;k=k+1) begin
                if(exponent[k]) result=cmul(result,power);
                power=cmul(power,power);
            end
            cpow=result;
        end
    endfunction
    localparam int N=1<<AW;
    localparam logic [31:0] R=32'(64'h100000000%64'(P));
    localparam logic [31:0] PSI=cpow(GENERATOR,(P-1)/32'(2*N));
    localparam logic [31:0] OMEGA=cmul(PSI,PSI);
    localparam logic [31:0] IPSI=cpow(PSI,P-2);
    localparam logic [31:0] IOMEGA=cpow(OMEGA,P-2);
    localparam logic [31:0] IN=cpow(32'(N),P-2);
    localparam logic [31:0] S0[0:3]='{R,cmul(R,PSI),cmul(R,cpow(PSI,2)),cmul(R,cpow(PSI,3))};
    localparam logic [31:0] S1[0:3]='{R,cmul(R,OMEGA),cmul(R,cpow(OMEGA,2)),cmul(R,cpow(OMEGA,3))};
    localparam logic [31:0] S2[0:3]='{R,cmul(R,IOMEGA),cmul(R,cpow(IOMEGA,2)),cmul(R,cpow(IOMEGA,3))};
    localparam logic [31:0] S3[0:3]='{IN,cmul(IN,IPSI),cmul(IN,cpow(IPSI,2)),cmul(IN,cpow(IPSI,3))};
    localparam logic [31:0] STEP[0:3]='{cmul(R,cpow(PSI,4)),cmul(R,cpow(OMEGA,4)),
                                                      cmul(R,cpow(IOMEGA,4)),cmul(R,cpow(IPSI,4))};
    logic [AW:0] index;
    logic [1:0] phase_reg;
    logic [31:0] seed, word_value, feedback;
    logic feedback_valid, multiply;
    always_comb begin
        case(phase_reg)
            0: seed=S0[index[1:0]];
            1: seed=S1[index[1:0]];
            2: seed=S2[index[1:0]];
            default: seed=S3[index[1:0]];
        endcase
    end
    assign word_value=int'(index)<4 ? seed : feedback;
    // Last four outputs need no successor; the pipeline is empty when done.
    assign multiply=busy && (int'(index)+4<N);
    genefer_montgomery_mul32_pipe #(.P(P),.Q(Q)) powers (
        .clk,.rst_n,.in_valid(multiply),.lhs(word_value),.rhs(STEP[phase_reg]),
        .out_valid(feedback_valid),.result(feedback)
    );
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            busy<=0; done<=0; error<=0; root_valid<=0;
            root_addr<=0; root_data<=0; phase_reg<=0; index<=0;
        end else begin
            done<=0; root_valid<=0;
            if(!busy) begin
                if(start) begin busy<=1; error<=0; index<=0; phase_reg<=phase; end
            end else begin
                root_valid<=1; root_addr<=AW'(index); root_data<=word_value;
                if(int'(index)>=4 && !feedback_valid) error<=1;
                if(int'(index)==N-1) begin busy<=0; done<=1; end
                else index<=index+1;
            end
        end
    end
endmodule

// SOURCE-ONLY format3: fixed compiled merged CT/GS roots, ordinary input/output.
// Modular arithmetic below is constant elaboration, never a datapath recurrence.
// Header: identity/domain R32, exact N, R^2/N, primitive 2N-th root psi.
module genefer_a10_profile3_constants_v1 #(
    parameter int AW=5,
    parameter logic [31:0] P=32'd104857601
) (
    input logic [15:0] address,
    output logic [31:0] word,normalization,psi
);
    localparam int N=1<<AW;
    localparam logic [31:0] G=P==104857601 ? 3 : P==69206017 ? 5 : P==67239937 ? 10 : 0;
    function automatic logic [31:0] cmul(input logic [31:0] x,y);
        logic [63:0] product;
        begin product=64'(x)*64'(y);cmul=32'(product%64'(P));end
    endfunction
    function automatic logic [31:0] cpow(input logic [31:0] x,e);
        logic [31:0] r,b;
        begin r=1;b=x;for(int j=0;j<32;j=j+1)begin
            if(e[j])r=cmul(r,b);b=cmul(b,b);end cpow=r;end
    endfunction
    localparam logic [31:0] R=32'(64'h100000000%64'(P));
    localparam logic [31:0] SCALE=cmul(cmul(R,R),cpow(32'(N),P-2));
    localparam logic [31:0] PSI=cpow(G,(P-1)/32'(2*N));
    assign normalization=SCALE;
    assign psi=PSI;
    always_comb case(address)
        16'd0:word=32'h41313000;
        16'd1:word=32'(N);
        16'd2:word=SCALE;
        16'd3:word=PSI;
        default:word=32'hffffffff;
    endcase
    // synthesis translate_off
    initial begin
        if(AW<1 || AW>16 || G==0 || (P-1)%32'(2*N)!=0)
            $fatal(1,"A10_PROFILE3_CONSTANT_GEOMETRY");
        if(cpow(PSI,32'(N))!=P-1 || cpow(PSI,32'(2*N))!=1)
            $fatal(1,"A10_PROFILE3_PSI_ORDER");
    end
    // synthesis translate_on
endmodule

module genefer_a10_profile3_rom_v1 #(
    parameter int AW=5,
    parameter logic [31:0] P=32'd104857601
) (
    input logic clk,rst_n,start,
    output logic busy,done,word_valid,
    output logic [15:0] word_addr,
    output logic [31:0] word_data
);
    logic [1:0] index;
    logic [31:0] selected_word;
    genefer_a10_profile3_constants_v1 #(.AW(AW),.P(P)) constants (
        .address({14'd0,index}),.word(selected_word),.normalization(),.psi()
    );
    // Exactly the parent's synchronous ROM eligibility/calendar; four words.
    always_ff @(posedge clk)if(rst_n && busy)word_data<=selected_word;
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin busy<=0;done<=0;word_valid<=0;word_addr<=0;index<=0;end
        else begin
            done<=0;word_valid<=busy;
            if(!busy)begin if(start)begin busy<=1;index<=0;end end
            else begin
                word_addr<={14'd0,index};
                if(index==2'd3)begin busy<=0;done<=1;end else index<=index+1'b1;
            end
        end
    end
endmodule

// Scalar physical comparison only. SAME control/tag/clock contract; DIFFERENT
// input ranges: parent requires u,v<P, candidate allows u,v<2P. No hidden
// parent-side canonicalizer; no engine integration or lazy28x28 point square.
module lazy28_butterfly_resource_v1 #(
    parameter int USE_LAZY=1,TAG_W=32,
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
) (
    input logic clk,rst_n,in_valid,gs,
    input logic [27:0] u,v,
    input logic [26:0] w,
    input logic [TAG_W-1:0] in_tag,
    output logic out_valid,
    output logic [27:0] y0,y1,
    output logic [TAG_W-1:0] out_tag
);
    generate if(USE_LAZY!=0)begin: lazy_cell
        genefer_ntt_lazy28_butterfly_v1 #(.P(P),.Q(Q),.TAG_W(TAG_W)) cell_instance (
            .clk,.rst_n,.in_valid,.gs,.u,.v,.w,.in_tag,.out_valid,.y0,.y1,.out_tag);
    end else begin: canonical_parent
        logic [31:0] parent0,parent1;
        logic [TAG_W-1:0] tag_pipe[0:4];
        genefer_ntt_difdit_butterfly27 #(.P(P),.Q(Q)) cell_instance (
            .clk,.rst_n,.in_valid,.dif(gs),.u({5'b0,u[26:0]}),.v({5'b0,v[26:0]}),.w({5'b0,w}),
            .out_valid,.y0(parent0),.y1(parent1));
        assign y0=28'(parent0);assign y1=28'(parent1);
        // product_valid before the final output edge is delayed input by five
        // register positions; out_valid after that edge has the same latency.
        logic [4:0] valid_pipe;
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin
                out_tag<=0;valid_pipe<=0;
                for(int k=0;k<5;k=k+1)tag_pipe[k]<=0;
            end else begin
                valid_pipe<={valid_pipe[3:0],in_valid};tag_pipe[0]<=in_tag;
                for(int k=1;k<5;k=k+1)tag_pipe[k]<=tag_pipe[k-1];
                if(valid_pipe[4])out_tag<=tag_pipe[4];
                // synthesis translate_off
                if(in_valid && ({4'b0,u}>=P || {4'b0,v}>=P))$fatal(1,"Canonical parent range");
                if(out_valid && (parent0>=P || parent1>=P))$fatal(1,"Canonical parent output range");
                // synthesis translate_on
            end
        end
    end endgenerate
endmodule

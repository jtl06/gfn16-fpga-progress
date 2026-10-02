// Combinational parallel inclusive scan, log2(LANES) composition levels.
// Each packed15 transfer maps encoded carry0..4 to encoded carry0..4.
module genefer_carry_transfer_tree #(parameter int LANES=4) (
    input logic [14:0] transfer[0:LANES-1],
    output logic [14:0] prefix[0:LANES-1]
);
    localparam int LEVELS=$clog2(LANES);
    function automatic logic [14:0] compose(input logic [14:0] first,second);
        for(int k=0;k<5;k=k+1)compose[k*3+:3]=second[first[k*3+:3]*3+:3];
    endfunction
    // Separate generated arrays make the acyclic stage boundaries explicit
    // to synthesis and simulation dependency analysis.
    for(genvar s=0;s<=LEVELS;s=s+1)begin: level
        logic [14:0] value[0:LANES-1];
        for(genvar i=0;i<LANES;i=i+1)begin: lane
            if(s==0)assign value[i]=transfer[i];
            else if(i>=(1<<(s-1)))assign value[i]=compose(level[s-1].value[i-(1<<(s-1))],level[s-1].value[i]);
            else assign value[i]=level[s-1].value[i];
            if(s==LEVELS)assign prefix[i]=value[i];
        end
    end
endmodule

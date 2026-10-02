// Isolated36-bit Montgomery experiment, R=2^36, canonical lhs,rhs<P.
// Six registered stages, II=1: input edge k -> output edge k+5.
// One variable36x36 product; all reduction products are explicit shifts/adds.
module genefer_montgomery_mul36_sparse_pipe #(
    parameter logic [35:0] P=36'd34896609281,
    parameter logic [35:0] Q=36'd33822867457
) (
    input logic clk,rst_n,in_valid,
    input logic [35:0] lhs,rhs,
    output logic out_valid,
    output logic [35:0] result
);
    localparam integer S=(P==36'd34896609281)?29:
                         (P==36'd34426847233)?26:34;
    logic [4:0] valid_pipe;
    logic [71:0] ab_s1,sum_low_s4,sum_high_s4;
    logic [35:0] m_head_s2,m_tail_s2,m_s3;
    logic [35:0] hi_s2,hi_s3,hi_s4,hi_s5,mp_hi_s5;
    wire [35:0] lo=ab_s1[35:0];
    wire [35:0] extra_q=(P==36'd52613349377)?(lo<<30):36'd0;
    wire [71:0] m_ext={36'b0,m_s3};
    wire [71:0] extra_p=(P==36'd52613349377)?(m_ext<<30):72'd0;
    wire [71:0] mp_sum=sum_low_s4+sum_high_s4;
    wire [36:0] corrected={1'b0,hi_s5}+{1'b0,P}-{1'b0,mp_hi_s5};
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            valid_pipe<='0;out_valid<=0;result<=0;
            ab_s1<=0;m_head_s2<=0;m_tail_s2<=0;m_s3<=0;
            sum_low_s4<=0;sum_high_s4<=0;
            hi_s2<=0;hi_s3<=0;hi_s4<=0;hi_s5<=0;mp_hi_s5<=0;
        end else begin
            valid_pipe<={valid_pipe[3:0],in_valid};out_valid<=valid_pipe[4];
            if(in_valid)ab_s1<=lhs*rhs;
            if(valid_pipe[0])begin
                m_head_s2<=lo-(lo<<35);
                m_tail_s2<=(lo<<S)+extra_q;
                hi_s2<=ab_s1[71:36];
            end
            if(valid_pipe[1])begin
                m_s3<=m_head_s2-m_tail_s2;hi_s3<=hi_s2;
            end
            if(valid_pipe[2])begin
                sum_low_s4<=m_ext+(m_ext<<S);
                sum_high_s4<=(m_ext<<35)+extra_p;hi_s4<=hi_s3;
            end
            if(valid_pipe[3])begin
                mp_hi_s5<=mp_sum[71:36];hi_s5<=hi_s4;
            end
            if(valid_pipe[4])begin
                if(hi_s5>=mp_hi_s5)result<=hi_s5-mp_hi_s5;
                else result<=corrected[35:0];
            end
        end
    end
    // synthesis translate_off
    initial begin
        if(P!=36'd34896609281 && P!=36'd34426847233 && P!=36'd52613349377)
            $fatal(1,"unsupported sparse Montgomery36 modulus");
        if(Q!=(36'd2-P))$fatal(1,"invalid sparse Montgomery36 inverse");
    end
    always @(posedge clk)if(rst_n && in_valid && (lhs>=P || rhs>=P))
        $fatal(1,"noncanonical Montgomery36 input");
    // synthesis translate_on
endmodule

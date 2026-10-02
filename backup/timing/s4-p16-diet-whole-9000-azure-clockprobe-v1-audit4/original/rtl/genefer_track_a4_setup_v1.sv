// Provisional shared A4 setup. begin E0 -> checked result E97, no lane copies.
// Exact floor(2^96/base) via96 restoring rounds; bounded A calculation overlaps.
module genefer_track_a4_setup_v1 #(parameter int AW=16) (
    input logic clk,rst_n,begin_setup,cancel,
    input logic [31:0] base,generation,
    output logic busy,done,error,config_valid,
    output logic [31:0] accepted_base,out_generation,
    output logic [76:0] coefficient_limit,
    output logic [95:0] reciprocal
);
    localparam int N=1<<AW,K=2*N+384;
    localparam int MIN_PROOF=(2*K+2)/3+1;
    localparam int MIN_BASE=(2*N+5)>MIN_PROOF ? (2*N+5) : MIN_PROOF;
    localparam logic [95:0] HALF_CRT=96'd243972611374018097905664;
    localparam logic [95:0] TERM2=96'd16*96'(K)*96'(K);
    typedef enum logic [1:0] {IDLE,DIVIDE,CHECK} state_t;
    state_t state;
    logic [6:0] round;
    logic [31:0] remainder,b;
    wire [32:0] shifted={remainder,1'b0};
    logic [63:0] b_squared;
    logic [49:0] bk;
    logic [80:0] term0;
    logic [95:0] term1,bound;
    logic bound_checked;
    assign busy=state!=IDLE;
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;done<=0;error<=0;config_valid<=0;accepted_base<=0;out_generation<=0;
            coefficient_limit<=0;reciprocal<=0;round<=0;remainder<=0;b<=0;
            b_squared<=0;bk<=0;term0<=0;term1<=0;bound<=0;bound_checked<=0;
        end else begin
            done<=0;error<=0;
            if(state==IDLE && begin_setup)begin
                config_valid<=0;out_generation<=generation;accepted_base<=base;
                if(base<32'(MIN_BASE) || base>32'd1000000000)begin done<=1;error<=1;end
                else begin
                    state<=DIVIDE;round<=0;remainder<=1;reciprocal<=0;
                    b<=base-1'b1;bound_checked<=0;
                end
            end
            if(state==DIVIDE)begin
                if(shifted>={1'b0,accepted_base})begin
                    remainder<=32'(shifted-{1'b0,accepted_base});reciprocal<={reciprocal[94:0],1'b1};
                end else begin remainder<=shifted[31:0];reciprocal<={reciprocal[94:0],1'b0};end
                if(round==0)begin b_squared<=64'(b)*64'(b);bk<=50'(b)*50'(K);end
                if(round==1)begin term0<=81'(b_squared)*81'(N+48);term1<=96'(bk)<<6;end
                if(round==2)bound<=(96'(term0)+term1+TERM2)<<1;
                if(round==3)begin
                    bound_checked<=bound!=0 && bound<=HALF_CRT && bound[95:77]==0;
                    coefficient_limit<=bound[76:0];
                end
                if(round==95)state<=CHECK;else round<=round+1'b1;
            end
            if(state==CHECK)begin
                state<=IDLE;done<=1;
                if(!bound_checked || reciprocal==0 || remainder>=accepted_base)begin error<=1;config_valid<=0;end
                else config_valid<=1;
            end
            if(state!=IDLE && begin_setup)begin
                state<=IDLE;done<=1;error<=1;config_valid<=0;
            end
            if(cancel)begin state<=IDLE;done<=0;error<=0;config_valid<=0;bound_checked<=0;end
        end
    end
    // synthesis translate_off
    initial if(AW<5 || AW>16)$fatal(1,"A4_SETUP_GEOMETRY");
    always @(posedge clk)if(rst_n && state==CHECK && bound_checked && !cancel && !begin_setup)begin
        if(128'(reciprocal)*128'(accepted_base)+128'(remainder)!=(128'd1<<96))
            $fatal(1,"A4_SETUP_RECIPROCAL_IDENTITY");
    end
    // synthesis translate_on
endmodule

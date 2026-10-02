// Isolated format2 experiment; source/model checks are not RTL validation.
// LOCAL UNVALIDATED RTL: fixed-size format2 profile for ordinary input residues.
// Only twist seeds use R2; recurrence steps remain R-scaled, post ordinary.
// All modular calculations initialize a constant ROM, never an input-dependent
// arithmetic path. ROM inference and physical cost still require Quartus checks.
// Ordered words include unused zero entries. Caller must begin the child profile
// before word0 and commit strictly AFTER the last valid write has been consumed.
module genefer_root_profile27_r2_rom #(
    parameter int AW=16,
    parameter int LANES=64,
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] GENERATOR=32'd3
) (
    input logic clk,rst_n,start,
    output logic busy,done,word_valid,
    output logic [15:0] word_addr,
    output logic [31:0] word_data
);
    localparam int N=1<<AW,K=$clog2(2*LANES);
    localparam int SEED_WORDS=4*LANES+1,WORDS=(2*AW+2)*SEED_WORDS,PAW=$clog2(WORDS);
    localparam logic [31:0] R=32'(64'h100000000%64'(P));
    localparam logic [31:0] R2=32'((64'(R)*64'(R))%64'(P));
    function automatic logic [31:0] cmul(input logic [31:0] x,y);
        logic [63:0] product;
        begin product=64'(x)*64'(y);cmul=32'(product%64'(P));end
    endfunction
    function automatic logic [31:0] cpow(input logic [31:0] x,exponent);
        logic [31:0] result,power;
        begin
            result=1;power=x;
            for(int bitno=0;bitno<32;bitno=bitno+1) begin
                if(exponent[bitno])result=cmul(result,power);
                power=cmul(power,power);
            end
            cpow=result;
        end
    endfunction
    localparam logic [31:0] PSI=cpow(GENERATOR,(P-1)/32'(2*N));
    localparam logic [31:0] OMEGA=cmul(PSI,PSI);
    localparam logic [31:0] IPSI=cpow(PSI,P-2),IOMEGA=cpow(OMEGA,P-2);
    localparam logic [31:0] IN=cpow(32'(N),P-2);
    function automatic logic [31:0] profile_word(input integer address);
        integer key,offset,context_id,lane,stage,h,period,g,base,coordinate,v,active;
        logic [31:0] alpha,factor;
        begin
            key=address/SEED_WORDS;offset=address%SEED_WORDS;
            context_id=offset/LANES;lane=offset%LANES;
            stage=0;h=0;period=1;g=0;base=0;coordinate=0;v=0;active=0;
            alpha=1;factor=R;profile_word=0;
            if(key==0 || key==2*AW+1) begin
                alpha=key==0 ? PSI : IPSI;
                factor=key==0 ? R2 : IN;
                if(offset==4*LANES)profile_word=cmul(cpow(alpha,32'(4*LANES)),R);
                else profile_word=cmul(cpow(alpha,32'(context_id*LANES+lane)),factor);
            end else begin
                stage=key-1-(key>AW ? AW : 0);
                alpha=key>AW ? IOMEGA : OMEGA;
                h=AW-1-stage;
                period=stage<K ? 1 : 1<<(stage-K+1);
                active=(1<<stage)<LANES ? 1<<stage : LANES;
                if(offset==4*LANES)
                    profile_word=period<=4 ? R : cmul(cpow(alpha,32'(1<<(K+h+1))),R);
                else if(lane<active) begin
                    g=context_id%period;
                    if(stage<K) begin base=0;v=lane;end
                    else begin
                        coordinate=stage%K;
                        base=(g&1)*(1<<coordinate)+((g>>1)%(1<<(stage-K)))*(1<<K);
                        v=(lane&((1<<coordinate)-1))|((lane>>coordinate)<<(coordinate+1));
                    end
                    profile_word=cmul(cpow(alpha,32'((base+v)<<h)),R);
                end
            end
        end
    endfunction
    (* ramstyle="M20K" *) logic [31:0] rom[0:WORDS-1];
    logic [PAW-1:0] index;
    initial for(int address=0;address<WORDS;address=address+1)
        rom[address]=profile_word(address);
    // Match the existing RAM inference boundary: no asynchronous data reset.
    // word_valid, not data contents during reset/idle, defines eligibility.
    always_ff @(posedge clk)
        if(rst_n && busy)word_data<=rom[index];
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            busy<=0;done<=0;word_valid<=0;word_addr<=0;index<=0;
        end else begin
            done<=0;word_valid<=busy;
            if(!busy) begin
                if(start)begin busy<=1;index<=0;end
            end else begin
                word_addr<=16'(index);
                if(index==PAW'(WORDS-1))begin busy<=0;done<=1;end
                else index<=index+1'b1;
            end
        end
    end
    // synthesis translate_off
    initial begin
        if(AW<1 || AW>16 || (LANES!=16 && LANES!=64))$fatal(1,"unsupported profile geometry");
        if(!((P==104857601 && GENERATOR==3) || (P==69206017 && GENERATOR==5) ||
             (P==67239937 && GENERATOR==10)))$fatal(1,"unsupported profile field");
    end
    // synthesis translate_on
endmodule

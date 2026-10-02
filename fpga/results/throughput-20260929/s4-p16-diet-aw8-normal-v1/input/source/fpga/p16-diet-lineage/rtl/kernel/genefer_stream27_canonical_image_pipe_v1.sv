// Required S4 canonical readback barrier; outside warm recurrence.
// Raw load is natural block order d[b*T+row], not streaming bitreverse lanes.
// Registered value boundary: three edges/digit, 9N normal / 10N special.
// Both fold/write-data and legality/write-enable consume the same value token.
// Warm recurrence, arithmetic, E0-to-E1 readback and published-image ABI unchanged.
module genefer_stream27_canonical_image_pipe_v1 #(
    parameter int AW=5,P=8,
    parameter int ROW_W=AW-$clog2(P)
) (
    input logic clk,rst_n,load_valid,begin_canonical,read_req,
    input logic [ROW_W-1:0] load_row,
    input logic [P*32-1:0] load_data,c0,c1,
    input logic [31:0] base,
    input logic [AW-1:0] read_address,
    output logic busy,done,error,image_valid,
    output logic [7:0] error_code,
    output logic [63:0] cycles,
    output logic read_valid,
    output logic [AW-1:0] read_address_out,
    output logic signed [95:0] read_data
);
    localparam int LP=$clog2(P),N=1<<AW,T=1<<ROW_W,K=2*N+24*P;
    localparam int CORR_MIN=(2*K+2)/3+1;
    localparam int BASE_MIN=(2*N+5)>CORR_MIN ? 2*N+5 : CORR_MIN;
    localparam logic [7:0] CONFLICT=1,LOAD_ORDER=2,BASE_RANGE=3,
        CORRECTION_RANGE=4,NOT_READY=5,DIGIT_RANGE=6,INTERNAL_RANGE=7;
    typedef enum logic[2:0] {IDLE,READ_WORD,VALUE_WORD,PROCESS_WORD,SPECIAL_WRITE,FAILED} state_t;
    state_t state;
    logic [ROW_W:0] loaded_count;
    logic raw_ready,read_pending;
    logic [LP-1:0] read_bank_d;
    logic [AW-1:0] read_address_d,address;
    logic [1:0] pass_index;
    logic signed [2:0] carry,fold_q;
    logic [31:0] base_reg,fold_r;
    logic signed [31:0] correction0[0:P-1],correction1[0:P-1];
    logic all_zero,all_max,next_all_zero,next_all_max;
    logic [P-1:0] ram_re,ram_we;
    logic [ROW_W-1:0] ram_ra[0:P-1],ram_wa[0:P-1];
    logic [31:0] ram_w[0:P-1],ram_q[0:P-1];
    wire [LP-1:0] bank=address[AW-1:ROW_W];
    wire [ROW_W-1:0] row=address[ROW_W-1:0];
    wire base_ok=base>=32'(BASE_MIN) && base<=32'd1000000000;
    logic load_bad,correction_bad,idle_reject,process_bad;
    logic [7:0] idle_code,process_code;
    logic signed [33:0] value,value_next,remainder,base_ext,two_base,three_base;
    logic stored_digit_bad; // Payload need not reset; PROCESS follows VALUE eligibility.
    logic signed [32:0] bound_c0,input_c0,input_c1;
    wire legal_load=rst_n && state==IDLE && !error && !idle_reject && load_valid;
    wire legal_begin=rst_n && state==IDLE && !error && !idle_reject && begin_canonical;
    wire legal_read=rst_n && state==IDLE && !error && !idle_reject && read_req;
    always_comb begin
        load_bad=0;correction_bad=0;
        bound_c0=$signed({1'b0,base})-33'sd1;
        input_c0=0;input_c1=0;
        for(int b=0;b<P;b=b+1)begin
            if(load_data[b*32+:32]>=base)load_bad=1;
            input_c0=$signed({c0[b*32+31],c0[b*32+:32]});
            input_c1=$signed({c1[b*32+31],c1[b*32+:32]});
            if(input_c0>bound_c0 || input_c0< -bound_c0 ||
               input_c1>33'(K) || input_c1< -33'(K))correction_bad=1;
        end
        idle_reject=0;idle_code=0;
        if(state==IDLE && !error)begin
            if((int'(load_valid)+int'(begin_canonical)+int'(read_req))>1 ||
               (read_pending && (load_valid || begin_canonical)))begin idle_reject=1;idle_code=CONFLICT;end
            else if(load_valid)begin
                if(!base_ok)begin idle_reject=1;idle_code=BASE_RANGE;end
                else if(load_bad)begin idle_reject=1;idle_code=DIGIT_RANGE;end
                else if((loaded_count==(ROW_W+1)'(T) && load_row!=0) ||
                    (loaded_count!=(ROW_W+1)'(T) && (ROW_W+1)'(load_row)!=loaded_count))begin
                    idle_reject=1;idle_code=LOAD_ORDER;
                end
            end else if(begin_canonical)begin
                if(!raw_ready)begin idle_reject=1;idle_code=NOT_READY;end
                else if(!base_ok)begin idle_reject=1;idle_code=BASE_RANGE;end
                else if(correction_bad)begin idle_reject=1;idle_code=CORRECTION_RANGE;end
            end else if(read_req && !image_valid)begin idle_reject=1;idle_code=NOT_READY;end
        end
    end
    // The supported profile closes -2b<=value<3b, hence five exact quotients.
    // Nonnegative Euclidean remainder for negative values, not signed truncation.
    always_comb begin
        base_ext=$signed({2'b00,base_reg});two_base=base_ext<<<1;three_base=two_base+base_ext;
        value_next=$signed({2'b00,ram_q[bank]})+$signed({{31{carry[2]}},carry});
        if(pass_index==0)begin
            if(row==0)value_next=value_next+$signed({{2{correction0[bank][31]}},correction0[bank]});
            else if(row==ROW_W'(1))value_next=value_next+$signed({{2{correction1[bank][31]}},correction1[bank]});
        end
        if(value>=two_base)begin fold_q=3'sd2;remainder=value-two_base;end
        else if(value>=base_ext)begin fold_q=3'sd1;remainder=value-base_ext;end
        else if(value>=0)begin fold_q=3'sd0;remainder=value;end
        else if(value>= -base_ext)begin fold_q=-3'sd1;remainder=value+base_ext;end
        else begin fold_q=-3'sd2;remainder=value+two_base;end
        fold_r=32'(remainder);
        next_all_zero=all_zero && remainder==0;
        next_all_max=all_max && remainder==base_ext-34'sd1;
        process_bad=0;process_code=0;
        if(stored_digit_bad)begin process_bad=1;process_code=DIGIT_RANGE;end
        else if(value< -two_base || value>=three_base || remainder<0 || remainder>=base_ext ||
            (pass_index!=0 && (fold_q< -3'sd1 || fold_q>3'sd1)) ||
            (pass_index==2 && address==AW'(N-1) && fold_q!=0 &&
             !((fold_q==3'sd1 && next_all_zero) || (fold_q== -3'sd1 && next_all_max))))begin
            process_bad=1;process_code=INTERNAL_RANGE;
        end
    end
    for(genvar b=0;b<P;b=b+1)begin: image_banks
        always_comb begin
            ram_re[b]=0;ram_we[b]=0;ram_ra[b]=0;ram_wa[b]=0;ram_w[b]=0;
            if(rst_n && !error)begin
                if(legal_load)begin ram_we[b]=1;ram_wa[b]=load_row;ram_w[b]=load_data[b*32+:32];end
                if(legal_read && read_address[AW-1:ROW_W]==LP'(b))begin
                    ram_re[b]=1;ram_ra[b]=read_address[ROW_W-1:0];
                end
                if(state==READ_WORD && bank==LP'(b))begin ram_re[b]=1;ram_ra[b]=row;end
                if(state==PROCESS_WORD && bank==LP'(b) && !process_bad)begin
                    ram_we[b]=1;ram_wa[b]=row;ram_w[b]=fold_r;
                end
                if(state==SPECIAL_WRITE && bank==LP'(b))begin
                    ram_we[b]=1;ram_wa[b]=row;ram_w[b]=address==0 ? 32'hffffffff : 32'd0;
                end
            end
        end
        genefer_sdp_ram32 #(.AW(ROW_W),.DEPTH(T)) image_ram (
            .clk,.rst_n,.read_en(ram_re[b]),.write_en(ram_we[b]),.read_addr(ram_ra[b]),
            .write_addr(ram_wa[b]),.write_data(ram_w[b]),.read_data(ram_q[b])
        );
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;loaded_count<=0;raw_ready<=0;read_pending<=0;
            busy<=0;done<=0;error<=0;error_code<=0;image_valid<=0;cycles<=0;
            read_valid<=0;read_address_out<=0;read_bank_d<=0;read_address_d<=0;
            base_reg<=2;address<=0;pass_index<=0;carry<=0;all_zero<=1;all_max<=1;
        end else begin
            done<=0;read_valid<=0;read_pending<=legal_read;
            if(legal_read)begin read_bank_d<=read_address[AW-1:ROW_W];read_address_d<=read_address;end
            if(read_pending && state==IDLE && image_valid && !error && !idle_reject)begin
                read_valid<=1;read_address_out<=read_address_d;
            end
            if(busy)cycles<=cycles+64'd1;
            if(idle_reject)begin
                state<=FAILED;error<=1;error_code<=idle_code;image_valid<=0;busy<=0;raw_ready<=0;read_pending<=0;
            end else case(state)
                IDLE:begin
                    if(legal_load)begin
                        image_valid<=0;
                        if(loaded_count==(ROW_W+1)'(T))begin loaded_count<=1;raw_ready<=T==1;end
                        else begin loaded_count<=loaded_count+1;raw_ready<=loaded_count==(ROW_W+1)'(T-1);end
                    end
                    if(legal_begin)begin
                        raw_ready<=0;loaded_count<=0;image_valid<=0;busy<=1;cycles<=0;
                        base_reg<=base;address<=0;pass_index<=0;carry<=0;all_zero<=1;all_max<=1;state<=READ_WORD;
                        for(int b=0;b<P;b=b+1)begin correction0[b]<=$signed(c0[b*32+:32]);correction1[b]<=$signed(c1[b*32+:32]);end
                    end
                end
                READ_WORD:state<=VALUE_WORD;
                VALUE_WORD:begin
                    value<=value_next;stored_digit_bad<=pass_index==0 && ram_q[bank]>=base_reg;
                    state<=PROCESS_WORD;
                end
                PROCESS_WORD:begin
                    if(process_bad)begin
                        state<=FAILED;error<=1;error_code<=process_code;image_valid<=0;busy<=0;read_pending<=0;
                    end else begin
                        if(pass_index==2)begin all_zero<=next_all_zero;all_max<=next_all_max;end
                        if(address==AW'(N-1))begin
                            address<=0;
                            if(pass_index<2)begin pass_index<=pass_index+1;carry<= -fold_q;state<=READ_WORD;end
                            else if(fold_q==0)begin state<=IDLE;busy<=0;done<=1;image_valid<=1;end
                            else state<=SPECIAL_WRITE;
                        end else begin address<=address+1;carry<=fold_q;state<=READ_WORD;end
                    end
                end
                SPECIAL_WRITE:begin
                    if(address==AW'(N-1))begin state<=IDLE;busy<=0;done<=1;image_valid<=1;end
                    else address<=address+1;
                end
                default:;
            endcase
        end
    end
    // Payload holds/reset eligibility separate: no stale RAM token may publish.
    always_ff @(posedge clk)if(rst_n && read_pending && state==IDLE && image_valid && !error && !idle_reject)
        read_data<=$signed({{64{ram_q[read_bank_d][31]}},ram_q[read_bank_d]});
    // synthesis translate_off
    initial if(AW<5 || AW>16 || (P!=8 && P!=16) || ROW_W!=AW-$clog2(P) || ROW_W<1)
        $fatal(1,"CANON_IMAGE_GEOMETRY");
    always @(posedge clk)if(rst_n)begin
        if(done && (!image_valid || error || busy))$fatal(1,"CANON_IMAGE_DONE_ELIGIBILITY");
        if(read_valid && (!image_valid || error))$fatal(1,"CANON_IMAGE_READ_ELIGIBILITY");
    end
    // synthesis translate_on
endmodule

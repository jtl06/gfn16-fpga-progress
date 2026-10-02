// Isolated 27-bit selector measurement. No arithmetic, RAM or N1 engine.
// MODE0 frozen-style radix2 routes; MODE1 canonical pair; MODE2 local pair.
module radix22_selector_network_v1 #(parameter int MODE=2) (
    input logic [2:0] pattern,pass_sel,
    input logic [1:0] orientation,
    input logic inverse,
    input logic [5:0] root_xor,root_mask,
    input logic [3455:0] data_payload,write_payload,
    input logic [7613:0] root_payload,
    output wire [3455:0] read_result,write_result,
    output wire [2591:0] root_result
);
    function automatic int insert_one(input int lane,p);
        return (lane&((1<<p)-1))|((lane>>p)<<(p+1));
    endfunction
    function automatic int remove_one(input int bank,p);
        return (bank&((1<<p)-1))|((bank>>(p+1))<<p);
    endfunction
    function automatic int pair_bank(input int lane,index,p);
        int bank,bit_number,low;
        begin
            bank=0;bit_number=0;low=(p+6)%7;
            for(int bit_index=0;bit_index<7;bit_index++)begin
                if(bit_index!=p && bit_index!=low)begin
                    bank|=((lane>>bit_number)&1)<<bit_index;
                    bit_number++;
                end
            end
            return bank|((index>>1)<<p)|((index&1)<<low);
        end
    endfunction
    function automatic int pair_word(input int bank,p);
        int lane,bit_number,low;
        begin
            lane=0;bit_number=0;low=(p+6)%7;
            for(int bit_index=0;bit_index<7;bit_index++)begin
                if(bit_index!=p && bit_index!=low)begin
                    lane|=((bank>>bit_index)&1)<<bit_number;
                    bit_number++;
                end
            end
            return lane*4+(((bank>>p)&1)<<1)+((bank>>low)&1);
        end
    endfunction
    function automatic logic [26:0] select7(input logic [188:0] words,input logic [2:0] sel);
        case(sel)
            0:select7=words[0*27+:27]; 1:select7=words[1*27+:27];
            2:select7=words[2*27+:27]; 3:select7=words[3*27+:27];
            4:select7=words[4*27+:27]; 5:select7=words[5*27+:27];
            6:select7=words[6*27+:27]; default:select7='0;
        endcase
    endfunction
    function automatic logic [26:0] select8(input logic [215:0] words,input logic [2:0] sel);
        case(sel)
            0:select8=words[0*27+:27]; 1:select8=words[1*27+:27];
            2:select8=words[2*27+:27]; 3:select8=words[3*27+:27];
            4:select8=words[4*27+:27]; 5:select8=words[5*27+:27];
            6:select8=words[6*27+:27]; default:select8=words[7*27+:27];
        endcase
    endfunction
    wire [26:0] read_unoriented[0:127],read_low[0:127],write_low[0:127],write_oriented[0:127];
    for(genvar word_index=0;word_index<128;word_index++)begin: data_words
        wire [188:0] read_options,write_options;
        for(genvar p=0;p<7;p++)begin: patterns
            localparam int BANK=(MODE==0)?insert_one(word_index/2,p)|((word_index%2)<<p):
                pair_bank(word_index/4,word_index%4,p);
            localparam int WORD=(MODE==0)?remove_one(word_index,p)*2+((word_index>>p)&1):pair_word(word_index,p);
            assign read_options[p*27+:27]=data_payload[BANK*27+:27];
            assign write_options[p*27+:27]=write_oriented[WORD];
        end
        assign read_unoriented[word_index]=select7(read_options,pattern);
        assign read_low[word_index]=orientation[0]?read_unoriented[word_index^1]:read_unoriented[word_index];
        assign write_low[word_index]=orientation[0]?write_payload[(word_index^1)*27+:27]:write_payload[word_index*27+:27];
        if(MODE==0)begin: single
            assign read_result[word_index*27+:27]=read_low[word_index];
            assign write_oriented[word_index]=write_low[word_index];
        end else begin: paired
            assign read_result[word_index*27+:27]=orientation[1]?read_low[word_index^2]:read_low[word_index];
            assign write_oriented[word_index]=orientation[1]?write_low[word_index^2]:write_low[word_index];
        end
        assign write_result[word_index*27+:27]=select7(write_options,pattern);
    end
    if(MODE==0)begin: parent_root
        for(genvar d=0;d<=6;d++)begin: route
            wire [26:0] words[0:63];
            for(genvar lane=0;lane<64;lane++)begin: lanes
                if(d==0)assign words[lane]=root_payload[lane*27+:27];
                else begin: inherited_clip
                    wire select_neighbor;
                    if((lane&(1<<(d-1)))==0)assign select_neighbor=root_mask[d-1]&root_xor[d-1];
                    else assign select_neighbor=~root_mask[d-1]|root_xor[d-1];
                    assign words[lane]=select_neighbor?route[d-1].words[lane^(1<<(d-1))]:route[d-1].words[lane];
                end
            end
        end
        for(genvar word_index=0;word_index<96;word_index++)begin: outputs
            if(word_index<64)assign root_result[word_index*27+:27]=route[6].words[word_index];
            else assign root_result[word_index*27+:27]='0;
        end
    end else if(MODE==1)begin: packed_root
        for(genvar p=0;p<8;p++)begin: passes
            localparam int STREAMS=(p==0)?32:(p==1)?8:(p==2)?2:1;
            localparam int LEVELS=(p==0)?5:(p==1)?3:(p==2)?1:0;
            localparam int OFFSET=(p==0)?0:(p==1)?96:(p==2)?120:126+(p-3)*3;
            for(genvar d=0;d<=LEVELS;d++)begin: stream_route
                wire [80:0] words[0:STREAMS-1];
                for(genvar stream=0;stream<STREAMS;stream++)begin: streams
                    if(d==0)assign words[stream]=inverse?root_payload[(141+OFFSET+stream*3)*27+:81]:root_payload[(OFFSET+stream*3)*27+:81];
                    else assign words[stream]=root_xor[d-1]?stream_route[d-1].words[stream^(1<<(d-1))]:stream_route[d-1].words[stream];
                end
            end
        end
        for(genvar group=0;group<32;group++)begin: consumers
            for(genvar root_index=0;root_index<3;root_index++)begin: roots
                wire [215:0] options;
                for(genvar p=0;p<8;p++)begin: pass_options
                    localparam int LEVELS=(p==0)?5:(p==1)?3:(p==2)?1:0;
                    localparam int STREAM=(p<3)?(group>>(2*p)):0;
                    assign options[p*27+:27]=passes[p].stream_route[LEVELS].words[STREAM][root_index*27+:27];
                end
                assign root_result[(group*3+root_index)*27+:27]=select8(options,pass_sel);
            end
        end
    end else begin: local_root
        // Source0:32 local triples; source1:8; source2:2 fused-upper triples.
        // Inverse/pass address generation and RAM inference are NOT measured here.
        for(genvar group=0;group<32;group++)begin: consumers
            for(genvar root_index=0;root_index<3;root_index++)begin: roots
                assign root_result[(group*3+root_index)*27+:27]=
                    pass_sel==0?root_payload[(group*3+root_index)*27+:27]:
                    pass_sel==1?root_payload[(96+(group/4)*3+root_index)*27+:27]:
                                root_payload[(120+(group/16)*3+root_index)*27+:27];
            end
        end
    end
endmodule

// Identical launch/capture shell for each MODE; payload cost is outside network.
module radix22_selector_probe_v1 #(parameter int MODE=2) (
    input logic clk,rst_n,in_valid,inverse,
    input logic [2:0] pattern,pass_sel,
    input logic [1:0] orientation,
    input logic [5:0] root_xor,root_mask,
    input logic [3455:0] data_payload,write_payload,
    input logic [7613:0] root_payload,
    output logic out_valid,out_fault,
    output logic [3455:0] read_result,write_result,
    output logic [2591:0] root_result
);
    logic inverse_q,valid_q,fault_q;
    logic [2:0] pattern_q,pass_q;
    logic [1:0] orientation_q;
    logic [5:0] xor_q,mask_q;
    logic [3455:0] data_q,write_q;
    logic [7613:0] root_q;
    wire [3455:0] read_d,write_d;
    wire [2591:0] root_d;
    radix22_selector_network_v1 #(.MODE(MODE)) network (
        .pattern(pattern_q),.pass_sel(pass_q),.orientation(orientation_q),.inverse(inverse_q),
        .root_xor(xor_q),.root_mask(mask_q),.data_payload(data_q),.write_payload(write_q),
        .root_payload(root_q),.read_result(read_d),.write_result(write_d),.root_result(root_d)
    );
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            inverse_q<=0;valid_q<=0;fault_q<=0;pattern_q<=0;pass_q<=0;
            orientation_q<=0;xor_q<=0;mask_q<=0;data_q<='0;write_q<='0;root_q<='0;
            out_valid<=0;out_fault<=0;read_result<='0;write_result<='0;root_result<='0;
        end else begin
            inverse_q<=inverse;valid_q<=in_valid && pattern<3'd7;fault_q<=in_valid && pattern==3'd7;
            pattern_q<=pattern;pass_q<=pass_sel;orientation_q<=orientation;xor_q<=root_xor;mask_q<=root_mask;
            data_q<=data_payload;write_q<=write_payload;root_q<=root_payload;
            out_valid<=valid_q;out_fault<=fault_q;read_result<=read_d;write_result<=write_d;root_result<=root_d;
        end
    end
endmodule

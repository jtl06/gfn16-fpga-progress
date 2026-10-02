// PROVISIONAL A4 block host route. No native/physical qualification.
// 16 contiguous blocks into the frozen128-bank XOR fold. Independent offsets,
// masks and1R1W ports. All requests reject atomically on collision or bad mode.
// Read request accepted at E0: synchronous RAM q and registered descriptor
// become valid after E0; the consuming CRT accepts on E1, as in the A4 model.
module genefer_track_a4_blockroute_v1 #(
    parameter int AW=16,
    parameter int RW=AW>7 ? AW-7 : 1
) (
    input logic clk,rst_n,enable,read_en,write_en,
    input logic [AW-1:0] read_offset,write_offset,
    input logic [15:0] read_mask,write_mask,
    input logic [511:0] write_words,
    input logic [31:0] ram_q[0:127],
    output logic request,error,read_valid,
    output logic [AW-1:0] read_offset_out,
    output logic [15:0] read_mask_out,
    output logic [511:0] read_words,
    output logic [127:0] ram_re,ram_we,
    output logic [RW-1:0] ram_ra[0:127],ram_wa[0:127],
    output logic [31:0] ram_w[0:127]
);
    localparam int T=1<<(AW-4);
    function automatic logic [6:0] fold(input logic [AW-1:0] a);
        logic [6:0] bank;
        begin bank=0;for(int j=0;j<AW;j=j+1)bank[j%7]=bank[j%7]^a[j];fold=bank;end
    endfunction
    function automatic logic [6:0] encode_lane(input logic [3:0] lane);
        logic [6:0] bank;
        begin bank=0;for(int j=0;j<4;j=j+1)bank[(AW-4+j)%7]=lane[j];encode_lane=bank;end
    endfunction
    function automatic logic [3:0] decode_lane(input logic [6:0] bank);
        logic [3:0] lane;
        begin for(int j=0;j<4;j=j+1)lane[j]=bank[(AW-4+j)%7];decode_lane=lane;end
    endfunction
    localparam logic [6:0] LANE_MASK=encode_lane(4'hf);
    wire [6:0] rb=fold(read_offset),wb=fold(write_offset);
    logic [6:0] rb_d;
    wire legal=enable && (!read_en || int'(read_offset)<T) &&
        (!write_en || int'(write_offset)<T) &&
        !(read_en && write_en && read_offset==write_offset && (|(read_mask & write_mask)));
    wire read_accept=rst_n && read_en && legal;
    wire write_accept=rst_n && write_en && legal;
    assign request=read_en || write_en;
    // Four XOR stages shared by the8 physical tiles. This avoids one128-way
    // data mux per output or a separate16-way word mux at every physical bank.
    for(genvar stage=0;stage<=4;stage=stage+1)begin: write_route
        logic [31:0] words[0:15];
        logic [15:0] mask;
        for(genvar lane=0;lane<16;lane=lane+1)begin: lanes
            if(stage==0)begin
                assign words[lane]=write_words[lane*32+:32];
                assign mask[lane]=write_mask[lane];
            end else begin
                assign words[lane]=wb[(AW-4+stage-1)%7] ?
                    write_route[stage-1].words[lane^(1<<(stage-1))] : write_route[stage-1].words[lane];
                assign mask[lane]=wb[(AW-4+stage-1)%7] ?
                    write_route[stage-1].mask[lane^(1<<(stage-1))] : write_route[stage-1].mask[lane];
            end
        end
    end
    for(genvar stage=0;stage<=4;stage=stage+1)begin: read_route
        logic [31:0] words[0:15];
        for(genvar lane=0;lane<16;lane=lane+1)begin: lanes
            if(stage==0)assign words[lane]=ram_q[(rb_d & ~LANE_MASK)|encode_lane(4'(lane))];
            else assign words[lane]=rb_d[(AW-4+stage-1)%7] ?
                read_route[stage-1].words[lane^(1<<(stage-1))] : read_route[stage-1].words[lane];
        end
    end
    for(genvar lane=0;lane<16;lane=lane+1)begin: responses
        assign read_words[lane*32+:32]=read_route[4].words[lane];
    end
    for(genvar bank=0;bank<128;bank=bank+1)begin: banks
        wire [3:0] read_lane=decode_lane(7'(bank)^rb);
        wire [3:0] write_lane=decode_lane(7'(bank)^wb);
        wire [AW-1:0] read_address=(AW'(read_lane)<<(AW-4))|read_offset;
        wire [AW-1:0] write_address=(AW'(write_lane)<<(AW-4))|write_offset;
        assign ram_re[bank]=read_accept && ((7'(bank)^rb)&~LANE_MASK)==0 && read_mask[read_lane];
        assign ram_we[bank]=write_accept && ((7'(bank)^wb)&~LANE_MASK)==0 &&
            write_route[4].mask[decode_lane(7'(bank))];
        assign ram_ra[bank]=RW'(read_address>>7);
        assign ram_wa[bank]=RW'(write_address>>7);
        assign ram_w[bank]=write_route[4].words[decode_lane(7'(bank))];
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            error<=0;read_valid<=0;read_offset_out<=0;read_mask_out<=0;rb_d<=0;
        end else begin
            error<=request && !legal;
            read_valid<=read_accept;
            read_mask_out<=read_accept ? read_mask : 16'd0;
            if(read_accept)begin rb_d<=rb;read_offset_out<=read_offset;end
        end
    end
    // synthesis translate_off
    initial if(AW<5 || AW>16 || RW!=(AW>7 ? AW-7 : 1))$fatal(1,"A4_BLOCK_ROUTE_GEOMETRY");
    always @(posedge clk)if(rst_n)begin
        for(int bank=0;bank<128;bank=bank+1)
            if(ram_re[bank] && ram_we[bank] && ram_ra[bank]==ram_wa[bank])
                $fatal(1,"A4_BLOCK_ROUTE_MIXED_COLLISION");
    end
    // synthesis translate_on
endmodule

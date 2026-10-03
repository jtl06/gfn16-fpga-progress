// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw8_p16_f2_s0_v1_bf_outreg_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=0,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h35ca559,
    parameter string HEX_FILE="EMBEDDED_SOURCE_ONLY"
) (
    input logic clk,rst_n,in_slot_valid,frame_start,
    output logic [WIDTH-1:0] root
);
    generate if(ADDRESS_BITS==0)begin : constant_root
        assign root=FIRST_ROOT;
    end else begin : gathered_root
        localparam int WORDS=1<<ADDRESS_BITS;
        (* ramstyle = "M20K" *) logic [WIDTH-1:0] roots[0:WORDS-1];
        logic [ROW_W-1:0] current_row,following_row;
        wire [ADDRESS_BITS-1:0] following_address;
        logic [WIDTH-1:0] prefetched,rom_output;
        logic first_q;
        assign following_row=frame_start ? ROW_W'(1) : current_row+ROW_W'(1);
        for(genvar bit_index=0;bit_index<ADDRESS_BITS;bit_index=bit_index+1)begin : address_bits
            localparam int ROW_BIT=int'(ADDRESS_ROW_POSITIONS[bit_index*ROW_W+:ROW_W]);
            assign following_address[bit_index]=following_row[ROW_BIT];
        end
        assign root=first_q ? FIRST_ROOT : rom_output;
        initial begin
            roots[0]=27'h35ca559;
        end
        // Memory and read output have no reset; row0 static bypass is mandatory.
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid)begin
                prefetched<=roots[following_address];
                rom_output<=prefetched;
            end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin current_row<='0;first_q<=0;end
            else if(in_slot_valid)begin current_row<=following_row;first_q<=frame_start;end
        end
        // synthesis translate_off
        initial begin
            if(FRAME_T<2 || (FRAME_T&(FRAME_T-1))!=0 || ADDRESS_BITS<1 || ADDRESS_BITS>ROW_W || HEX_FILE=="")
                $fatal(1,"S_M2_COMPACT_ROOT_GEOMETRY_OR_FILE");
            for(int k=0;k<ADDRESS_BITS;k=k+1)begin
                if(int'(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W])>=ROW_W)$fatal(1,"S_M2_ROOT_ROW_BIT");
                for(int j=0;j<k;j=j+1)
                    if(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W]==ADDRESS_ROW_POSITIONS[j*ROW_W+:ROW_W])
                        $fatal(1,"S_M2_DUPLICATE_ROOT_ROW_BIT");
            end
        end
        // synthesis translate_on
    end endgenerate
endmodule

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw8_p16_f2_s1_v1_bf_outreg_v1 #(
    parameter int WIDTH=54,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=0,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=54'h0d505c387f7226,
    parameter string HEX_FILE="EMBEDDED_SOURCE_ONLY"
) (
    input logic clk,rst_n,in_slot_valid,frame_start,
    output logic [WIDTH-1:0] root
);
    generate if(ADDRESS_BITS==0)begin : constant_root
        assign root=FIRST_ROOT;
    end else begin : gathered_root
        localparam int WORDS=1<<ADDRESS_BITS;
        (* ramstyle = "M20K" *) logic [WIDTH-1:0] roots[0:WORDS-1];
        logic [ROW_W-1:0] current_row,following_row;
        wire [ADDRESS_BITS-1:0] following_address;
        logic [WIDTH-1:0] prefetched,rom_output;
        logic first_q;
        assign following_row=frame_start ? ROW_W'(1) : current_row+ROW_W'(1);
        for(genvar bit_index=0;bit_index<ADDRESS_BITS;bit_index=bit_index+1)begin : address_bits
            localparam int ROW_BIT=int'(ADDRESS_ROW_POSITIONS[bit_index*ROW_W+:ROW_W]);
            assign following_address[bit_index]=following_row[ROW_BIT];
        end
        assign root=first_q ? FIRST_ROOT : rom_output;
        initial begin
            roots[0]=54'h0d505c387f7226;
        end
        // Memory and read output have no reset; row0 static bypass is mandatory.
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid)begin
                prefetched<=roots[following_address];
                rom_output<=prefetched;
            end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin current_row<='0;first_q<=0;end
            else if(in_slot_valid)begin current_row<=following_row;first_q<=frame_start;end
        end
        // synthesis translate_off
        initial begin
            if(FRAME_T<2 || (FRAME_T&(FRAME_T-1))!=0 || ADDRESS_BITS<1 || ADDRESS_BITS>ROW_W || HEX_FILE=="")
                $fatal(1,"S_M2_COMPACT_ROOT_GEOMETRY_OR_FILE");
            for(int k=0;k<ADDRESS_BITS;k=k+1)begin
                if(int'(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W])>=ROW_W)$fatal(1,"S_M2_ROOT_ROW_BIT");
                for(int j=0;j<k;j=j+1)
                    if(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W]==ADDRESS_ROW_POSITIONS[j*ROW_W+:ROW_W])
                        $fatal(1,"S_M2_DUPLICATE_ROOT_ROW_BIT");
            end
        end
        // synthesis translate_on
    end endgenerate
endmodule

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw8_p16_f2_s2_v1_bf_outreg_v1 #(
    parameter int WIDTH=108,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=0,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=108'h6169756b00aab9991772ae9b271,
    parameter string HEX_FILE="EMBEDDED_SOURCE_ONLY"
) (
    input logic clk,rst_n,in_slot_valid,frame_start,
    output logic [WIDTH-1:0] root
);
    generate if(ADDRESS_BITS==0)begin : constant_root
        assign root=FIRST_ROOT;
    end else begin : gathered_root
        localparam int WORDS=1<<ADDRESS_BITS;
        (* ramstyle = "M20K" *) logic [WIDTH-1:0] roots[0:WORDS-1];
        logic [ROW_W-1:0] current_row,following_row;
        wire [ADDRESS_BITS-1:0] following_address;
        logic [WIDTH-1:0] prefetched,rom_output;
        logic first_q;
        assign following_row=frame_start ? ROW_W'(1) : current_row+ROW_W'(1);
        for(genvar bit_index=0;bit_index<ADDRESS_BITS;bit_index=bit_index+1)begin : address_bits
            localparam int ROW_BIT=int'(ADDRESS_ROW_POSITIONS[bit_index*ROW_W+:ROW_W]);
            assign following_address[bit_index]=following_row[ROW_BIT];
        end
        assign root=first_q ? FIRST_ROOT : rom_output;
        initial begin
            roots[0]=108'h6169756b00aab9991772ae9b271;
        end
        // Memory and read output have no reset; row0 static bypass is mandatory.
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid)begin
                prefetched<=roots[following_address];
                rom_output<=prefetched;
            end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin current_row<='0;first_q<=0;end
            else if(in_slot_valid)begin current_row<=following_row;first_q<=frame_start;end
        end
        // synthesis translate_off
        initial begin
            if(FRAME_T<2 || (FRAME_T&(FRAME_T-1))!=0 || ADDRESS_BITS<1 || ADDRESS_BITS>ROW_W || HEX_FILE=="")
                $fatal(1,"S_M2_COMPACT_ROOT_GEOMETRY_OR_FILE");
            for(int k=0;k<ADDRESS_BITS;k=k+1)begin
                if(int'(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W])>=ROW_W)$fatal(1,"S_M2_ROOT_ROW_BIT");
                for(int j=0;j<k;j=j+1)
                    if(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W]==ADDRESS_ROW_POSITIONS[j*ROW_W+:ROW_W])
                        $fatal(1,"S_M2_DUPLICATE_ROOT_ROW_BIT");
            end
        end
        // synthesis translate_on
    end endgenerate
endmodule

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw8_p16_f2_s3_v1_bf_outreg_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=0,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'h6d9b1be86188382873dd0ab43c770dfec04f79da10cebda80dd0db,
    parameter string HEX_FILE="EMBEDDED_SOURCE_ONLY"
) (
    input logic clk,rst_n,in_slot_valid,frame_start,
    output logic [WIDTH-1:0] root
);
    generate if(ADDRESS_BITS==0)begin : constant_root
        assign root=FIRST_ROOT;
    end else begin : gathered_root
        localparam int WORDS=1<<ADDRESS_BITS;
        (* ramstyle = "M20K" *) logic [WIDTH-1:0] roots[0:WORDS-1];
        logic [ROW_W-1:0] current_row,following_row;
        wire [ADDRESS_BITS-1:0] following_address;
        logic [WIDTH-1:0] prefetched,rom_output;
        logic first_q;
        assign following_row=frame_start ? ROW_W'(1) : current_row+ROW_W'(1);
        for(genvar bit_index=0;bit_index<ADDRESS_BITS;bit_index=bit_index+1)begin : address_bits
            localparam int ROW_BIT=int'(ADDRESS_ROW_POSITIONS[bit_index*ROW_W+:ROW_W]);
            assign following_address[bit_index]=following_row[ROW_BIT];
        end
        assign root=first_q ? FIRST_ROOT : rom_output;
        initial begin
            roots[0]=216'h6d9b1be86188382873dd0ab43c770dfec04f79da10cebda80dd0db;
        end
        // Memory and read output have no reset; row0 static bypass is mandatory.
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid)begin
                prefetched<=roots[following_address];
                rom_output<=prefetched;
            end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin current_row<='0;first_q<=0;end
            else if(in_slot_valid)begin current_row<=following_row;first_q<=frame_start;end
        end
        // synthesis translate_off
        initial begin
            if(FRAME_T<2 || (FRAME_T&(FRAME_T-1))!=0 || ADDRESS_BITS<1 || ADDRESS_BITS>ROW_W || HEX_FILE=="")
                $fatal(1,"S_M2_COMPACT_ROOT_GEOMETRY_OR_FILE");
            for(int k=0;k<ADDRESS_BITS;k=k+1)begin
                if(int'(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W])>=ROW_W)$fatal(1,"S_M2_ROOT_ROW_BIT");
                for(int j=0;j<k;j=j+1)
                    if(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W]==ADDRESS_ROW_POSITIONS[j*ROW_W+:ROW_W])
                        $fatal(1,"S_M2_DUPLICATE_ROOT_ROW_BIT");
            end
        end
        // synthesis translate_on
    end endgenerate
endmodule

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw8_p16_f2_s4_v1_bf_outreg_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=1,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=4'h3,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'h768bb821d3f0f444901103e2b434b711126e096a13be62fbcf7401,
    parameter string HEX_FILE="EMBEDDED_SOURCE_ONLY"
) (
    input logic clk,rst_n,in_slot_valid,frame_start,
    output logic [WIDTH-1:0] root
);
    generate if(ADDRESS_BITS==0)begin : constant_root
        assign root=FIRST_ROOT;
    end else begin : gathered_root
        localparam int WORDS=1<<ADDRESS_BITS;
        (* ramstyle = "M20K" *) logic [WIDTH-1:0] roots[0:WORDS-1];
        logic [ROW_W-1:0] current_row,following_row;
        wire [ADDRESS_BITS-1:0] following_address;
        logic [WIDTH-1:0] prefetched,rom_output;
        logic first_q;
        assign following_row=frame_start ? ROW_W'(1) : current_row+ROW_W'(1);
        for(genvar bit_index=0;bit_index<ADDRESS_BITS;bit_index=bit_index+1)begin : address_bits
            localparam int ROW_BIT=int'(ADDRESS_ROW_POSITIONS[bit_index*ROW_W+:ROW_W]);
            assign following_address[bit_index]=following_row[ROW_BIT];
        end
        assign root=first_q ? FIRST_ROOT : rom_output;
        initial begin
            roots[0]=216'h768bb821d3f0f444901103e2b434b711126e096a13be62fbcf7401;
            roots[1]=216'h7d3cdfe2c575bc2224810f8155d5a4b10c4cf39d496b8303459652;
        end
        // Memory and read output have no reset; row0 static bypass is mandatory.
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid)begin
                prefetched<=roots[following_address];
                rom_output<=prefetched;
            end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin current_row<='0;first_q<=0;end
            else if(in_slot_valid)begin current_row<=following_row;first_q<=frame_start;end
        end
        // synthesis translate_off
        initial begin
            if(FRAME_T<2 || (FRAME_T&(FRAME_T-1))!=0 || ADDRESS_BITS<1 || ADDRESS_BITS>ROW_W || HEX_FILE=="")
                $fatal(1,"S_M2_COMPACT_ROOT_GEOMETRY_OR_FILE");
            for(int k=0;k<ADDRESS_BITS;k=k+1)begin
                if(int'(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W])>=ROW_W)$fatal(1,"S_M2_ROOT_ROW_BIT");
                for(int j=0;j<k;j=j+1)
                    if(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W]==ADDRESS_ROW_POSITIONS[j*ROW_W+:ROW_W])
                        $fatal(1,"S_M2_DUPLICATE_ROOT_ROW_BIT");
            end
        end
        // synthesis translate_on
    end endgenerate
endmodule

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw8_p16_f2_s5_v1_bf_outreg_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=2,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=8'h32,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'h0b842e8c8b6465c1ff4ca3ba9fd3726328716520056b1dcba92d87,
    parameter string HEX_FILE="EMBEDDED_SOURCE_ONLY"
) (
    input logic clk,rst_n,in_slot_valid,frame_start,
    output logic [WIDTH-1:0] root
);
    generate if(ADDRESS_BITS==0)begin : constant_root
        assign root=FIRST_ROOT;
    end else begin : gathered_root
        localparam int WORDS=1<<ADDRESS_BITS;
        (* ramstyle = "M20K" *) logic [WIDTH-1:0] roots[0:WORDS-1];
        logic [ROW_W-1:0] current_row,following_row;
        wire [ADDRESS_BITS-1:0] following_address;
        logic [WIDTH-1:0] prefetched,rom_output;
        logic first_q;
        assign following_row=frame_start ? ROW_W'(1) : current_row+ROW_W'(1);
        for(genvar bit_index=0;bit_index<ADDRESS_BITS;bit_index=bit_index+1)begin : address_bits
            localparam int ROW_BIT=int'(ADDRESS_ROW_POSITIONS[bit_index*ROW_W+:ROW_W]);
            assign following_address[bit_index]=following_row[ROW_BIT];
        end
        assign root=first_q ? FIRST_ROOT : rom_output;
        initial begin
            roots[0]=216'h0b842e8c8b6465c1ff4ca3ba9fd3726328716520056b1dcba92d87;
            roots[1]=216'h67ff15697a37352f2349ab8eea7269564c7c15fe58a563614a74d9;
            roots[2]=216'h057a2ec1d82d8922739c07149510afd15a0e26b75ea39e5b05d8cd;
            roots[3]=216'h42be9242f8ff651ef03c05c29f755a587046c90b1b753a70c94602;
        end
        // Memory and read output have no reset; row0 static bypass is mandatory.
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid)begin
                prefetched<=roots[following_address];
                rom_output<=prefetched;
            end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin current_row<='0;first_q<=0;end
            else if(in_slot_valid)begin current_row<=following_row;first_q<=frame_start;end
        end
        // synthesis translate_off
        initial begin
            if(FRAME_T<2 || (FRAME_T&(FRAME_T-1))!=0 || ADDRESS_BITS<1 || ADDRESS_BITS>ROW_W || HEX_FILE=="")
                $fatal(1,"S_M2_COMPACT_ROOT_GEOMETRY_OR_FILE");
            for(int k=0;k<ADDRESS_BITS;k=k+1)begin
                if(int'(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W])>=ROW_W)$fatal(1,"S_M2_ROOT_ROW_BIT");
                for(int j=0;j<k;j=j+1)
                    if(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W]==ADDRESS_ROW_POSITIONS[j*ROW_W+:ROW_W])
                        $fatal(1,"S_M2_DUPLICATE_ROOT_ROW_BIT");
            end
        end
        // synthesis translate_on
    end endgenerate
endmodule

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw8_p16_f2_s6_v1_bf_outreg_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=3,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=12'h321,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'h55a761a0db2f2c97b20400514497dd4afebe0ad10bbcd2993c5a2f,
    parameter string HEX_FILE="EMBEDDED_SOURCE_ONLY"
) (
    input logic clk,rst_n,in_slot_valid,frame_start,
    output logic [WIDTH-1:0] root
);
    generate if(ADDRESS_BITS==0)begin : constant_root
        assign root=FIRST_ROOT;
    end else begin : gathered_root
        localparam int WORDS=1<<ADDRESS_BITS;
        (* ramstyle = "M20K" *) logic [WIDTH-1:0] roots[0:WORDS-1];
        logic [ROW_W-1:0] current_row,following_row;
        wire [ADDRESS_BITS-1:0] following_address;
        logic [WIDTH-1:0] prefetched,rom_output;
        logic first_q;
        assign following_row=frame_start ? ROW_W'(1) : current_row+ROW_W'(1);
        for(genvar bit_index=0;bit_index<ADDRESS_BITS;bit_index=bit_index+1)begin : address_bits
            localparam int ROW_BIT=int'(ADDRESS_ROW_POSITIONS[bit_index*ROW_W+:ROW_W]);
            assign following_address[bit_index]=following_row[ROW_BIT];
        end
        assign root=first_q ? FIRST_ROOT : rom_output;
        initial begin
            roots[0]=216'h55a761a0db2f2c97b20400514497dd4afebe0ad10bbcd2993c5a2f;
            roots[1]=216'h4d5fafa23a03d9d9e281bd35e58383ef6cd6e536952e04fb5237fa;
            roots[2]=216'h065cd9cbd74dc5691f11397316476ca35acb3122d89d64f0da2d59;
            roots[3]=216'h268929a0e92c8904cc0ab13e8b1328fe9eb82cc78b8e3641d605e2;
            roots[4]=216'h247df3ed9fdaf0376f9a39415982af664070489fcc2271e1c0d892;
            roots[5]=216'h0b4b83a0bc4ca912cdbc261d9c93c68576cd03a89cca8fc8ca458a;
            roots[6]=216'h46284bc6bb198cb4c026bcf2e9e794ed1e73cf1e404ddcb04b9ca8;
            roots[7]=216'h582eb5a8cf2fcd5d63738d15ffe64a875c238def90714d990c4be7;
        end
        // Memory and read output have no reset; row0 static bypass is mandatory.
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid)begin
                prefetched<=roots[following_address];
                rom_output<=prefetched;
            end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin current_row<='0;first_q<=0;end
            else if(in_slot_valid)begin current_row<=following_row;first_q<=frame_start;end
        end
        // synthesis translate_off
        initial begin
            if(FRAME_T<2 || (FRAME_T&(FRAME_T-1))!=0 || ADDRESS_BITS<1 || ADDRESS_BITS>ROW_W || HEX_FILE=="")
                $fatal(1,"S_M2_COMPACT_ROOT_GEOMETRY_OR_FILE");
            for(int k=0;k<ADDRESS_BITS;k=k+1)begin
                if(int'(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W])>=ROW_W)$fatal(1,"S_M2_ROOT_ROW_BIT");
                for(int j=0;j<k;j=j+1)
                    if(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W]==ADDRESS_ROW_POSITIONS[j*ROW_W+:ROW_W])
                        $fatal(1,"S_M2_DUPLICATE_ROOT_ROW_BIT");
            end
        end
        // synthesis translate_on
    end endgenerate
endmodule

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw8_p16_f2_s7_v1_bf_outreg_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=4,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=16'h3210,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'h170f042bf3dba82090958cdd92d0a1e72c429db3d91a5003df4243,
    parameter string HEX_FILE="EMBEDDED_SOURCE_ONLY"
) (
    input logic clk,rst_n,in_slot_valid,frame_start,
    output logic [WIDTH-1:0] root
);
    generate if(ADDRESS_BITS==0)begin : constant_root
        assign root=FIRST_ROOT;
    end else begin : gathered_root
        localparam int WORDS=1<<ADDRESS_BITS;
        (* ramstyle = "M20K" *) logic [WIDTH-1:0] roots[0:WORDS-1];
        logic [ROW_W-1:0] current_row,following_row;
        wire [ADDRESS_BITS-1:0] following_address;
        logic [WIDTH-1:0] prefetched,rom_output;
        logic first_q;
        assign following_row=frame_start ? ROW_W'(1) : current_row+ROW_W'(1);
        for(genvar bit_index=0;bit_index<ADDRESS_BITS;bit_index=bit_index+1)begin : address_bits
            localparam int ROW_BIT=int'(ADDRESS_ROW_POSITIONS[bit_index*ROW_W+:ROW_W]);
            assign following_address[bit_index]=following_row[ROW_BIT];
        end
        assign root=first_q ? FIRST_ROOT : rom_output;
        initial begin
            roots[0]=216'h170f042bf3dba82090958cdd92d0a1e72c429db3d91a5003df4243;
            roots[1]=216'h3dcfcc6cbe4b29e464dbade18063086a228d755b0fdf3c11beafd0;
            roots[2]=216'h201d818a0e6938211d23b179ce96471252859cc0981612ab06097d;
            roots[3]=216'h6a62facbff213417c891a59d8cd0926a71003309994960b07afc59;
            roots[4]=216'h353ebee807f861a4dce812b9fe30b80cd47a74770b2d8b2be04a14;
            roots[5]=216'h338506ca006e91072412287d691452853418c5ae0d58c90979835a;
            roots[6]=216'h6a8b37077c79383844a4b3878f45241c423bc20099621e590168a9;
            roots[7]=216'h1846ba41510aa10d49e72675899113b1466087ea4c4981e2aeb129;
            roots[8]=216'h23d27ccc723a503672ec35e01476ffaa22aa74a31b3cbab2a08b4d;
            roots[9]=216'h41e41ccc6dbbddb83e610c2383b5510706d8885f062ac098b9bdff;
            roots[10]=216'h05e2c4c97050ec63eb620019a3e7710ffcdeca2684aed93325ee16;
            roots[11]=216'h11709be8508471649761aaa474447d3e6c94a7530b0052d320408f;
            roots[12]=216'h5aff9561627734b1e75e871617c329e39cb675354b1f73cbd06c92;
            roots[13]=216'h481252e49754b997a82c89af6dc5c3ea4ce4d2e24617d999eca46c;
            roots[14]=216'h37d3af41059e747c0d911aedfed2f49f3aba3774dc4d7411ffce5d;
            roots[15]=216'h64f879403846f8728e2d1586e9871e50ca761ec65d381de99c7901;
        end
        // Memory and read output have no reset; row0 static bypass is mandatory.
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid)begin
                prefetched<=roots[following_address];
                rom_output<=prefetched;
            end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin current_row<='0;first_q<=0;end
            else if(in_slot_valid)begin current_row<=following_row;first_q<=frame_start;end
        end
        // synthesis translate_off
        initial begin
            if(FRAME_T<2 || (FRAME_T&(FRAME_T-1))!=0 || ADDRESS_BITS<1 || ADDRESS_BITS>ROW_W || HEX_FILE=="")
                $fatal(1,"S_M2_COMPACT_ROOT_GEOMETRY_OR_FILE");
            for(int k=0;k<ADDRESS_BITS;k=k+1)begin
                if(int'(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W])>=ROW_W)$fatal(1,"S_M2_ROOT_ROW_BIT");
                for(int j=0;j<k;j=j+1)
                    if(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W]==ADDRESS_ROW_POSITIONS[j*ROW_W+:ROW_W])
                        $fatal(1,"S_M2_DUPLICATE_ROOT_ROW_BIT");
            end
        end
        // synthesis translate_on
    end endgenerate
endmodule

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_gs_aw8_p16_f2_s0_v1_bf_outreg_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=4,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=16'h3210,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'h4cb0e0016bf11114c274072d79c55322d2c738e9df9f7218da3c37,
    parameter string HEX_FILE="EMBEDDED_SOURCE_ONLY"
) (
    input logic clk,rst_n,in_slot_valid,frame_start,
    output logic [WIDTH-1:0] root
);
    generate if(ADDRESS_BITS==0)begin : constant_root
        assign root=FIRST_ROOT;
    end else begin : gathered_root
        localparam int WORDS=1<<ADDRESS_BITS;
        (* ramstyle = "M20K" *) logic [WIDTH-1:0] roots[0:WORDS-1];
        logic [ROW_W-1:0] current_row,following_row;
        wire [ADDRESS_BITS-1:0] following_address;
        logic [WIDTH-1:0] prefetched,rom_output;
        logic first_q;
        assign following_row=frame_start ? ROW_W'(1) : current_row+ROW_W'(1);
        for(genvar bit_index=0;bit_index<ADDRESS_BITS;bit_index=bit_index+1)begin : address_bits
            localparam int ROW_BIT=int'(ADDRESS_ROW_POSITIONS[bit_index*ROW_W+:ROW_W]);
            assign following_address[bit_index]=following_row[ROW_BIT];
        end
        assign root=first_q ? FIRST_ROOT : rom_output;
        initial begin
            roots[0]=216'h4cb0e0016bf11114c274072d79c55322d2c738e9df9f7218da3c37;
            roots[1]=216'h40463481e145fc8c9117287b0644a64028c27937de04c322436287;
            roots[2]=216'h42ab72acfc1338375a3c1200adb6ce124a34abea16e15699c16d6a;
            roots[3]=216'h06326dea78462094159626d0e337213d0aa78c511d4b11a12a0356;
            roots[4]=216'h1c37ee4a87d69cd7b15a9c360cb2af717a4e344f8f6ef72b767b22;
            roots[5]=216'h1b823d6db0936c436bb38497803800cb86ce8a4f4d2f5e33d2e9db;
            roots[6]=216'h6908404cf29fb84fef429597c7e67f8f8c2460cfc7348851f2df1b;
            roots[7]=216'h2c2e968269a2acac16ba8822af0147fd74e5468a472b8b6ae36c1b;
            roots[8]=216'h2a69db09e33f153ff02c378275e3354ed079db0cdd6deacb3fca2f;
            roots[9]=216'h6012eb0356f0d9897bff96ff1e01930e1ae45dae11170d98ada649;
            roots[10]=216'h510f94e95b9b81cf74a49d8bd672f452e07cedf74c0f22ea65d7cb;
            roots[11]=216'h0436bdaa713a710c1712ba5f9975acc03c2e118c50000f4a580a0a;
            roots[12]=216'h70e07503634fac0099edbb8cac93504e68f49bb78811bda0aee82b;
            roots[13]=216'h1f7ed083fcf6b0f5c67f8de76d81d4c630eff16e8bf32d9b0113f5;
            roots[14]=216'h486a06281861fce6154aa7dcaf0247cff60e4d92869369ba13819e;
            roots[15]=216'h0457b7c37ad8057bc4993b10c6b6684da8f037b5882848bb4987e0;
        end
        // Memory and read output have no reset; row0 static bypass is mandatory.
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid)begin
                prefetched<=roots[following_address];
                rom_output<=prefetched;
            end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin current_row<='0;first_q<=0;end
            else if(in_slot_valid)begin current_row<=following_row;first_q<=frame_start;end
        end
        // synthesis translate_off
        initial begin
            if(FRAME_T<2 || (FRAME_T&(FRAME_T-1))!=0 || ADDRESS_BITS<1 || ADDRESS_BITS>ROW_W || HEX_FILE=="")
                $fatal(1,"S_M2_COMPACT_ROOT_GEOMETRY_OR_FILE");
            for(int k=0;k<ADDRESS_BITS;k=k+1)begin
                if(int'(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W])>=ROW_W)$fatal(1,"S_M2_ROOT_ROW_BIT");
                for(int j=0;j<k;j=j+1)
                    if(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W]==ADDRESS_ROW_POSITIONS[j*ROW_W+:ROW_W])
                        $fatal(1,"S_M2_DUPLICATE_ROOT_ROW_BIT");
            end
        end
        // synthesis translate_on
    end endgenerate
endmodule

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_gs_aw8_p16_f2_s1_v1_bf_outreg_v1 #(
    parameter int WIDTH=108,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=4,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=16'h3210,
    parameter logic [WIDTH-1:0] FIRST_ROOT=108'h661400651ce468e71a071408a54,
    parameter string HEX_FILE="EMBEDDED_SOURCE_ONLY"
) (
    input logic clk,rst_n,in_slot_valid,frame_start,
    output logic [WIDTH-1:0] root
);
    generate if(ADDRESS_BITS==0)begin : constant_root
        assign root=FIRST_ROOT;
    end else begin : gathered_root
        localparam int WORDS=1<<ADDRESS_BITS;
        (* ramstyle = "M20K" *) logic [WIDTH-1:0] roots[0:WORDS-1];
        logic [ROW_W-1:0] current_row,following_row;
        wire [ADDRESS_BITS-1:0] following_address;
        logic [WIDTH-1:0] prefetched,rom_output;
        logic first_q;
        assign following_row=frame_start ? ROW_W'(1) : current_row+ROW_W'(1);
        for(genvar bit_index=0;bit_index<ADDRESS_BITS;bit_index=bit_index+1)begin : address_bits
            localparam int ROW_BIT=int'(ADDRESS_ROW_POSITIONS[bit_index*ROW_W+:ROW_W]);
            assign following_address[bit_index]=following_row[ROW_BIT];
        end
        assign root=first_q ? FIRST_ROOT : rom_output;
        initial begin
            roots[0]=108'h661400651ce468e71a071408a54;
            roots[1]=108'h5eb68347cf5939b9e4218dcbc53;
            roots[2]=108'h065a2c6a61fed1299ccf1d0bda3;
            roots[3]=108'h76cc6b2fe111ad1961c40378972;
            roots[4]=108'h3404c707719225e9766bba7a3e4;
            roots[5]=108'h66f74ee1a2b82066f8afa1ebd46;
            roots[6]=108'h0dbd4d2e4c83344d04a2ade1062;
            roots[7]=108'h4824ede9f6c715206ec12aa4ce1;
            roots[8]=108'h1dc2ea07e19fb1e3da6facdb6b4;
            roots[9]=108'h457f43ea40e4e490a671a6d80b2;
            roots[10]=108'h0d59d3a4bf077c8616483cf1933;
            roots[11]=108'h64fa5503b94d8c6a9dbb04bae54;
            roots[12]=108'h05d4352138ebf9b9bf859970284;
            roots[13]=108'h15f900e570fd88533593a40084b;
            roots[14]=108'h7f9d770b4a6fe5e59a1b154c4f4;
            roots[15]=108'h58b4ba4a2996b884ea5e8135a82;
        end
        // Memory and read output have no reset; row0 static bypass is mandatory.
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid)begin
                prefetched<=roots[following_address];
                rom_output<=prefetched;
            end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin current_row<='0;first_q<=0;end
            else if(in_slot_valid)begin current_row<=following_row;first_q<=frame_start;end
        end
        // synthesis translate_off
        initial begin
            if(FRAME_T<2 || (FRAME_T&(FRAME_T-1))!=0 || ADDRESS_BITS<1 || ADDRESS_BITS>ROW_W || HEX_FILE=="")
                $fatal(1,"S_M2_COMPACT_ROOT_GEOMETRY_OR_FILE");
            for(int k=0;k<ADDRESS_BITS;k=k+1)begin
                if(int'(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W])>=ROW_W)$fatal(1,"S_M2_ROOT_ROW_BIT");
                for(int j=0;j<k;j=j+1)
                    if(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W]==ADDRESS_ROW_POSITIONS[j*ROW_W+:ROW_W])
                        $fatal(1,"S_M2_DUPLICATE_ROOT_ROW_BIT");
            end
        end
        // synthesis translate_on
    end endgenerate
endmodule

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_gs_aw8_p16_f2_s2_v1_bf_outreg_v1 #(
    parameter int WIDTH=54,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=4,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=16'h3210,
    parameter logic [WIDTH-1:0] FIRST_ROOT=54'h1a1e0141ec0b6f,
    parameter string HEX_FILE="EMBEDDED_SOURCE_ONLY"
) (
    input logic clk,rst_n,in_slot_valid,frame_start,
    output logic [WIDTH-1:0] root
);
    generate if(ADDRESS_BITS==0)begin : constant_root
        assign root=FIRST_ROOT;
    end else begin : gathered_root
        localparam int WORDS=1<<ADDRESS_BITS;
        (* ramstyle = "M20K" *) logic [WIDTH-1:0] roots[0:WORDS-1];
        logic [ROW_W-1:0] current_row,following_row;
        wire [ADDRESS_BITS-1:0] following_address;
        logic [WIDTH-1:0] prefetched,rom_output;
        logic first_q;
        assign following_row=frame_start ? ROW_W'(1) : current_row+ROW_W'(1);
        for(genvar bit_index=0;bit_index<ADDRESS_BITS;bit_index=bit_index+1)begin : address_bits
            localparam int ROW_BIT=int'(ADDRESS_ROW_POSITIONS[bit_index*ROW_W+:ROW_W]);
            assign following_address[bit_index]=following_row[ROW_BIT];
        end
        assign root=first_q ? FIRST_ROOT : rom_output;
        initial begin
            roots[0]=54'h1a1e0141ec0b6f;
            roots[1]=54'h1d2eb051c41f89;
            roots[2]=54'h1736dea954d3c9;
            roots[3]=54'h19c5cff89358b3;
            roots[4]=54'h1c5fa4fbd62e8b;
            roots[5]=54'h1c85b581bd18c9;
            roots[6]=54'h1e4b2923aa1754;
            roots[7]=54'h07e139a02d8c36;
            roots[8]=54'h0d1b91a0c20756;
            roots[9]=54'h0a488ad1a3b96e;
            roots[10]=54'h108d4042cd54db;
            roots[11]=54'h15bc5940ed5395;
            roots[12]=54'h06f93743a5de8d;
            roots[13]=54'h0e32b0207e0168;
            roots[14]=54'h11e35c0a48ce6d;
            roots[15]=54'h02c693d3549c48;
        end
        // Memory and read output have no reset; row0 static bypass is mandatory.
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid)begin
                prefetched<=roots[following_address];
                rom_output<=prefetched;
            end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin current_row<='0;first_q<=0;end
            else if(in_slot_valid)begin current_row<=following_row;first_q<=frame_start;end
        end
        // synthesis translate_off
        initial begin
            if(FRAME_T<2 || (FRAME_T&(FRAME_T-1))!=0 || ADDRESS_BITS<1 || ADDRESS_BITS>ROW_W || HEX_FILE=="")
                $fatal(1,"S_M2_COMPACT_ROOT_GEOMETRY_OR_FILE");
            for(int k=0;k<ADDRESS_BITS;k=k+1)begin
                if(int'(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W])>=ROW_W)$fatal(1,"S_M2_ROOT_ROW_BIT");
                for(int j=0;j<k;j=j+1)
                    if(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W]==ADDRESS_ROW_POSITIONS[j*ROW_W+:ROW_W])
                        $fatal(1,"S_M2_DUPLICATE_ROOT_ROW_BIT");
            end
        end
        // synthesis translate_on
    end endgenerate
endmodule

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_gs_aw8_p16_f2_s3_v1_bf_outreg_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=4,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=16'h3210,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h0181902,
    parameter string HEX_FILE="EMBEDDED_SOURCE_ONLY"
) (
    input logic clk,rst_n,in_slot_valid,frame_start,
    output logic [WIDTH-1:0] root
);
    generate if(ADDRESS_BITS==0)begin : constant_root
        assign root=FIRST_ROOT;
    end else begin : gathered_root
        localparam int WORDS=1<<ADDRESS_BITS;
        (* ramstyle = "M20K" *) logic [WIDTH-1:0] roots[0:WORDS-1];
        logic [ROW_W-1:0] current_row,following_row;
        wire [ADDRESS_BITS-1:0] following_address;
        logic [WIDTH-1:0] prefetched,rom_output;
        logic first_q;
        assign following_row=frame_start ? ROW_W'(1) : current_row+ROW_W'(1);
        for(genvar bit_index=0;bit_index<ADDRESS_BITS;bit_index=bit_index+1)begin : address_bits
            localparam int ROW_BIT=int'(ADDRESS_ROW_POSITIONS[bit_index*ROW_W+:ROW_W]);
            assign following_address[bit_index]=following_row[ROW_BIT];
        end
        assign root=first_q ? FIRST_ROOT : rom_output;
        initial begin
            roots[0]=27'h0181902;
            roots[1]=27'h350a292;
            roots[2]=27'h3bdb6ff;
            roots[3]=27'h309eaa4;
            roots[4]=27'h12fa77b;
            roots[5]=27'h2ce318c;
            roots[6]=27'h2d48fa1;
            roots[7]=27'h0bc69af;
            roots[8]=27'h04da240;
            roots[9]=27'h38d03c4;
            roots[10]=27'h378dfdf;
            roots[11]=27'h3c3d4be;
            roots[12]=27'h1a67778;
            roots[13]=27'h249da59;
            roots[14]=27'h18a33a2;
            roots[15]=27'h0328c00;
        end
        // Memory and read output have no reset; row0 static bypass is mandatory.
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid)begin
                prefetched<=roots[following_address];
                rom_output<=prefetched;
            end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin current_row<='0;first_q<=0;end
            else if(in_slot_valid)begin current_row<=following_row;first_q<=frame_start;end
        end
        // synthesis translate_off
        initial begin
            if(FRAME_T<2 || (FRAME_T&(FRAME_T-1))!=0 || ADDRESS_BITS<1 || ADDRESS_BITS>ROW_W || HEX_FILE=="")
                $fatal(1,"S_M2_COMPACT_ROOT_GEOMETRY_OR_FILE");
            for(int k=0;k<ADDRESS_BITS;k=k+1)begin
                if(int'(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W])>=ROW_W)$fatal(1,"S_M2_ROOT_ROW_BIT");
                for(int j=0;j<k;j=j+1)
                    if(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W]==ADDRESS_ROW_POSITIONS[j*ROW_W+:ROW_W])
                        $fatal(1,"S_M2_DUPLICATE_ROOT_ROW_BIT");
            end
        end
        // synthesis translate_on
    end endgenerate
endmodule

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_gs_aw8_p16_f2_s4_v1_bf_outreg_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=3,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=12'h321,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h0952722,
    parameter string HEX_FILE="EMBEDDED_SOURCE_ONLY"
) (
    input logic clk,rst_n,in_slot_valid,frame_start,
    output logic [WIDTH-1:0] root
);
    generate if(ADDRESS_BITS==0)begin : constant_root
        assign root=FIRST_ROOT;
    end else begin : gathered_root
        localparam int WORDS=1<<ADDRESS_BITS;
        (* ramstyle = "M20K" *) logic [WIDTH-1:0] roots[0:WORDS-1];
        logic [ROW_W-1:0] current_row,following_row;
        wire [ADDRESS_BITS-1:0] following_address;
        logic [WIDTH-1:0] prefetched,rom_output;
        logic first_q;
        assign following_row=frame_start ? ROW_W'(1) : current_row+ROW_W'(1);
        for(genvar bit_index=0;bit_index<ADDRESS_BITS;bit_index=bit_index+1)begin : address_bits
            localparam int ROW_BIT=int'(ADDRESS_ROW_POSITIONS[bit_index*ROW_W+:ROW_W]);
            assign following_address[bit_index]=following_row[ROW_BIT];
        end
        assign root=first_q ? FIRST_ROOT : rom_output;
        initial begin
            roots[0]=27'h0952722;
            roots[1]=27'h1e99df3;
            roots[2]=27'h3b11847;
            roots[3]=27'h356bc3a;
            roots[4]=27'h07b00a1;
            roots[5]=27'h2c41899;
            roots[6]=27'h1e8284c;
            roots[7]=27'h3f42f26;
        end
        // Memory and read output have no reset; row0 static bypass is mandatory.
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid)begin
                prefetched<=roots[following_address];
                rom_output<=prefetched;
            end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin current_row<='0;first_q<=0;end
            else if(in_slot_valid)begin current_row<=following_row;first_q<=frame_start;end
        end
        // synthesis translate_off
        initial begin
            if(FRAME_T<2 || (FRAME_T&(FRAME_T-1))!=0 || ADDRESS_BITS<1 || ADDRESS_BITS>ROW_W || HEX_FILE=="")
                $fatal(1,"S_M2_COMPACT_ROOT_GEOMETRY_OR_FILE");
            for(int k=0;k<ADDRESS_BITS;k=k+1)begin
                if(int'(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W])>=ROW_W)$fatal(1,"S_M2_ROOT_ROW_BIT");
                for(int j=0;j<k;j=j+1)
                    if(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W]==ADDRESS_ROW_POSITIONS[j*ROW_W+:ROW_W])
                        $fatal(1,"S_M2_DUPLICATE_ROOT_ROW_BIT");
            end
        end
        // synthesis translate_on
    end endgenerate
endmodule

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_gs_aw8_p16_f2_s5_v1_bf_outreg_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=2,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=8'h32,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h0f6b456,
    parameter string HEX_FILE="EMBEDDED_SOURCE_ONLY"
) (
    input logic clk,rst_n,in_slot_valid,frame_start,
    output logic [WIDTH-1:0] root
);
    generate if(ADDRESS_BITS==0)begin : constant_root
        assign root=FIRST_ROOT;
    end else begin : gathered_root
        localparam int WORDS=1<<ADDRESS_BITS;
        (* ramstyle = "M20K" *) logic [WIDTH-1:0] roots[0:WORDS-1];
        logic [ROW_W-1:0] current_row,following_row;
        wire [ADDRESS_BITS-1:0] following_address;
        logic [WIDTH-1:0] prefetched,rom_output;
        logic first_q;
        assign following_row=frame_start ? ROW_W'(1) : current_row+ROW_W'(1);
        for(genvar bit_index=0;bit_index<ADDRESS_BITS;bit_index=bit_index+1)begin : address_bits
            localparam int ROW_BIT=int'(ADDRESS_ROW_POSITIONS[bit_index*ROW_W+:ROW_W]);
            assign following_address[bit_index]=following_row[ROW_BIT];
        end
        assign root=first_q ? FIRST_ROOT : rom_output;
        initial begin
            roots[0]=27'h0f6b456;
            roots[1]=27'h141d553;
            roots[2]=27'h0cfd11c;
            roots[3]=27'h1184d90;
        end
        // Memory and read output have no reset; row0 static bypass is mandatory.
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid)begin
                prefetched<=roots[following_address];
                rom_output<=prefetched;
            end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin current_row<='0;first_q<=0;end
            else if(in_slot_valid)begin current_row<=following_row;first_q<=frame_start;end
        end
        // synthesis translate_off
        initial begin
            if(FRAME_T<2 || (FRAME_T&(FRAME_T-1))!=0 || ADDRESS_BITS<1 || ADDRESS_BITS>ROW_W || HEX_FILE=="")
                $fatal(1,"S_M2_COMPACT_ROOT_GEOMETRY_OR_FILE");
            for(int k=0;k<ADDRESS_BITS;k=k+1)begin
                if(int'(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W])>=ROW_W)$fatal(1,"S_M2_ROOT_ROW_BIT");
                for(int j=0;j<k;j=j+1)
                    if(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W]==ADDRESS_ROW_POSITIONS[j*ROW_W+:ROW_W])
                        $fatal(1,"S_M2_DUPLICATE_ROOT_ROW_BIT");
            end
        end
        // synthesis translate_on
    end endgenerate
endmodule

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_gs_aw8_p16_f2_s6_v1_bf_outreg_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=1,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=4'h3,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h257f47a,
    parameter string HEX_FILE="EMBEDDED_SOURCE_ONLY"
) (
    input logic clk,rst_n,in_slot_valid,frame_start,
    output logic [WIDTH-1:0] root
);
    generate if(ADDRESS_BITS==0)begin : constant_root
        assign root=FIRST_ROOT;
    end else begin : gathered_root
        localparam int WORDS=1<<ADDRESS_BITS;
        (* ramstyle = "M20K" *) logic [WIDTH-1:0] roots[0:WORDS-1];
        logic [ROW_W-1:0] current_row,following_row;
        wire [ADDRESS_BITS-1:0] following_address;
        logic [WIDTH-1:0] prefetched,rom_output;
        logic first_q;
        assign following_row=frame_start ? ROW_W'(1) : current_row+ROW_W'(1);
        for(genvar bit_index=0;bit_index<ADDRESS_BITS;bit_index=bit_index+1)begin : address_bits
            localparam int ROW_BIT=int'(ADDRESS_ROW_POSITIONS[bit_index*ROW_W+:ROW_W]);
            assign following_address[bit_index]=following_row[ROW_BIT];
        end
        assign root=first_q ? FIRST_ROOT : rom_output;
        initial begin
            roots[0]=27'h257f47a;
            roots[1]=27'h3828ddb;
        end
        // Memory and read output have no reset; row0 static bypass is mandatory.
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid)begin
                prefetched<=roots[following_address];
                rom_output<=prefetched;
            end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin current_row<='0;first_q<=0;end
            else if(in_slot_valid)begin current_row<=following_row;first_q<=frame_start;end
        end
        // synthesis translate_off
        initial begin
            if(FRAME_T<2 || (FRAME_T&(FRAME_T-1))!=0 || ADDRESS_BITS<1 || ADDRESS_BITS>ROW_W || HEX_FILE=="")
                $fatal(1,"S_M2_COMPACT_ROOT_GEOMETRY_OR_FILE");
            for(int k=0;k<ADDRESS_BITS;k=k+1)begin
                if(int'(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W])>=ROW_W)$fatal(1,"S_M2_ROOT_ROW_BIT");
                for(int j=0;j<k;j=j+1)
                    if(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W]==ADDRESS_ROW_POSITIONS[j*ROW_W+:ROW_W])
                        $fatal(1,"S_M2_DUPLICATE_ROOT_ROW_BIT");
            end
        end
        // synthesis translate_on
    end endgenerate
endmodule

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_gs_aw8_p16_f2_s7_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=0,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h3c6bdf8,
    parameter string HEX_FILE="EMBEDDED_SOURCE_ONLY"
) (
    input logic clk,rst_n,in_slot_valid,frame_start,
    output logic [WIDTH-1:0] root
);
    generate if(ADDRESS_BITS==0)begin : constant_root
        assign root=FIRST_ROOT;
    end else begin : gathered_root
        localparam int WORDS=1<<ADDRESS_BITS;
        (* ramstyle = "M20K" *) logic [WIDTH-1:0] roots[0:WORDS-1];
        logic [ROW_W-1:0] current_row,following_row;
        wire [ADDRESS_BITS-1:0] following_address;
        logic [WIDTH-1:0] prefetched;
        assign following_row=frame_start ? ROW_W'(1) : current_row+ROW_W'(1);
        for(genvar bit_index=0;bit_index<ADDRESS_BITS;bit_index=bit_index+1)begin : address_bits
            localparam int ROW_BIT=int'(ADDRESS_ROW_POSITIONS[bit_index*ROW_W+:ROW_W]);
            assign following_address[bit_index]=following_row[ROW_BIT];
        end
        assign root=frame_start ? FIRST_ROOT : prefetched;
        initial begin
            roots[0]=27'h3c6bdf8;
        end
        // Memory and read output have no reset; row0 static bypass is mandatory.
        always_ff @(posedge clk)
            if(rst_n && in_slot_valid)prefetched<=roots[following_address];
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)current_row<='0;
            else if(in_slot_valid)current_row<=following_row;
        end
        // synthesis translate_off
        initial begin
            if(FRAME_T<2 || (FRAME_T&(FRAME_T-1))!=0 || ADDRESS_BITS<1 || ADDRESS_BITS>ROW_W || HEX_FILE=="")
                $fatal(1,"S_M2_COMPACT_ROOT_GEOMETRY_OR_FILE");
            for(int k=0;k<ADDRESS_BITS;k=k+1)begin
                if(int'(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W])>=ROW_W)$fatal(1,"S_M2_ROOT_ROW_BIT");
                for(int j=0;j<k;j=j+1)
                    if(ADDRESS_ROW_POSITIONS[k*ROW_W+:ROW_W]==ADDRESS_ROW_POSITIONS[j*ROW_W+:ROW_W])
                        $fatal(1,"S_M2_DUPLICATE_ROOT_ROW_BIT");
            end
        end
        // synthesis translate_on
    end endgenerate
endmodule

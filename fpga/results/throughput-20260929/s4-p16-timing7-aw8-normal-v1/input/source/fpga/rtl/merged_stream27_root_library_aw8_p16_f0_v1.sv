// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw8_p16_f0_s0_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=0,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h3c66667,
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
            roots[0]=27'h3c66667;
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

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw8_p16_f0_s1_v1 #(
    parameter int WIDTH=54,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=0,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=54'h1a0db89cdae329,
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
            roots[0]=54'h1a0db89cdae329;
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

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw8_p16_f0_s2_v1 #(
    parameter int WIDTH=108,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=0,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=108'hc43b83028e63061ef341cc45cdb,
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
            roots[0]=108'hc43b83028e63061ef341cc45cdb;
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

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw8_p16_f0_s3_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=0,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'h5b98f4f3c816be3b25a544373729dcea3923101c4705a1d0a90a62,
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
            roots[0]=216'h5b98f4f3c816be3b25a544373729dcea3923101c4705a1d0a90a62;
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

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw8_p16_f0_s4_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=1,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=4'h3,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'h29df5595ab5e86e7e2684805acf6eb6b0ed74077163638f61c9e3c,
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
            roots[0]=216'h29df5595ab5e86e7e2684805acf6eb6b0ed74077163638f61c9e3c;
            roots[1]=216'h5b110e6f47972938bd9d081005d301e9a5203198401ecce4005fe8;
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

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw8_p16_f0_s5_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=2,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=8'h32,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'ha5f28b4cb7bb42b037120f57d97aaacb84d98b778f0ce219ea6bf6,
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
            roots[0]=216'ha5f28b4cb7bb42b037120f57d97aaacb84d98b778f0ce219ea6bf6;
            roots[1]=216'h6f08f6b8d0c731dff449296b80115bd68820a6e9c5a9e455b58b79;
            roots[2]=216'hbbe70d2f4109b047119fc41d473716ba40333a544f4591441633c9;
            roots[3]=216'h673dc817e7ad6e2feff313bd4019d3c50eb93e238d9fdd69d2fd1a;
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

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw8_p16_f0_s6_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=3,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=12'h321,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'h696adb4947ebadcde981af860e87a5216d4715e2a575a2fc6eba09,
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
            roots[0]=216'h696adb4947ebadcde981af860e87a5216d4715e2a575a2fc6eba09;
            roots[1]=216'h08c01b208799014825561aacf982e171ff49f3b24557c0394113ba;
            roots[2]=216'h5dd745905b34f2500486d29ea6785b95850b8d50a805f484c65ffc;
            roots[3]=216'hb8d89182d6ec2056d7a13a24ba9b8503db5338c92766dcdb10187b;
            roots[4]=216'hb1614ff58ed21ce3e83194f6c9bb475832c8f0fa42817b5928b5ff;
            roots[5]=216'haf79d4c92733a0f910fd84f2b8c1ea2b56d8ac7816876905ccedfb;
            roots[6]=216'h3fa4d3ae21ed1a1af65a47c050e4f109c830e40c31213304bed8b3;
            roots[7]=216'hc6f197b6f580de2525ff89fbc8b1953a192276bc1dacceeaca7043;
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

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw8_p16_f0_s7_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=4,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=16'h3210,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'hbd1ee7d88628bafb1a15c6691d9927d8f27cb2ad20bc5989bf8dd0,
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
            roots[0]=216'hbd1ee7d88628bafb1a15c6691d9927d8f27cb2ad20bc5989bf8dd0;
            roots[1]=216'h343aeb4498163823cc5b15c6e3648d818af7ae5beb30bbca6ac573;
            roots[2]=216'h23c86321ef836164f446815f6278ac4ed38a13101586d7b4365ec8;
            roots[3]=216'hb5f5b468854e71302c6b2a160cb24084c157be33046b836150dc77;
            roots[4]=216'h105ae9498e32ec11994f9a8d71f7ae79851f8ddb116a2c9b5eea12;
            roots[5]=216'h17fd0785256cd03bae87dca550522d150909264288e9ef036af8df;
            roots[6]=216'h311d4b907958b9394952069905634066010dfd6650b2fbce2adaa5;
            roots[7]=216'h5da4088a2a35188483ec939e160be82a9c350279a8256125a57fe3;
            roots[8]=216'h8e5cbcb7aeae2273f21bc68789bc0925d50d1a5f4a2eeb6358d7db;
            roots[9]=216'hbcedeac49528dd90134b6075c004f6de45375007997a2854897b9f;
            roots[10]=216'h6399432b4f5055c3d0a5173796901fd1a54833e6c207f15df6b661;
            roots[11]=216'h74b9e7e98702a155901c008aeec13adc64ddf3046fb89471a609d3;
            roots[12]=216'h3528f3d3c2957c62784fa98d314c436a5833ae30acb9687b4a3439;
            roots[13]=216'h00362cb4df1fd84434e2846c497660c09742e8e604fdce79885402;
            roots[14]=216'h09bd6af1165839ff8c6dd221e6d4db543905141d9dff3d7a734001;
            roots[15]=216'h7e9f6ca21ebab5ca82315af39146035453559530e92ec06141bf0e;
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

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_gs_aw8_p16_f0_s0_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=4,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=16'h3210,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'h9fc81e64689fd474d59f33e55d81218ddaaabee7edc28aa24b049c,
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
            roots[0]=216'h9fc81e64689fd474d59f33e55d81218ddaaabee7edc28aa24b049c;
            roots[1]=216'h7998000a00614915d7c5bd255e523bc3289039c98fd34f9df214aa;
            roots[2]=216'h96f57ff68118c89a2e34b0f9fb6bf276d56de58f0841c05e3e4e9c;
            roots[3]=216'h5eb97902a34bcab8a39f81e4ad574e59db5ec3d88a7ad51496b863;
            roots[4]=216'h933ec5c123b5cd6419f85a291cfc6ea22ae537f25ef1faca9a30c2;
            roots[5]=216'h09293417fc07588f9833630172f9990d30ae17addb615f632335e8;
            roots[6]=216'h36d08c4c42ebdcb15ff1bc490df0714802c7f65ae8d5ae505890ab;
            roots[7]=216'h5ce504d3e88a5505cb4203b6d173af0ecc5606f282a2a3c9cd1a1c;
            roots[8]=216'h135003c4ed4f76b5fb0d84beab3a0c3d434dbe0a1dab95db52dfbd;
            roots[9]=216'h02a4ab90a6822104053449fcd01bacdf56f35b57510d4e9cb715a5;
            roots[10]=216'h5aa0e4548b08850db37bd29757d0eb55f97228bca7b5266d8017c5;
            roots[11]=216'h5c22bdf04ae9b8e0e44aa68c33f92e51c58733589ee39a35bd28b7;
            roots[12]=216'h9de47156ca3e5470839ad1fbda173d3e6cf7e9cae0f5632890525e;
            roots[13]=216'h4134272e3c942c0bd9e09e9d898c5413b4dd85dd2e20f94d21bce8;
            roots[14]=216'h7aa751c367a22130a3493f93f3c9c723977e19d2e8cfd39c9e28a7;
            roots[15]=216'h900e4628a1d342269aa69ac13883b2dc501272f580f3ae985708c3;
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

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_gs_aw8_p16_f0_s1_v1 #(
    parameter int WIDTH=108,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=4,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=16'h3210,
    parameter logic [WIDTH-1:0] FIRST_ROOT=108'hb4086ec7d6d008414fe50087344,
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
            roots[0]=108'hb4086ec7d6d008414fe50087344;
            roots[1]=108'h6eb1f7ca299890db1288d7562f5;
            roots[2]=108'h387f5e68284d355bc25dc42d964;
            roots[3]=108'h3024e9c06f6686be37e8bc77b1d;
            roots[4]=108'hbe1a8eb1377819fb198c8c4315b;
            roots[5]=108'h0e6240cdbc4b856ea710d4aea56;
            roots[6]=108'h9e126cd1e0be786e25bd0b4f582;
            roots[7]=108'ha2e94057bf42598e1e0c09c53e8;
            roots[8]=108'h53b68b164942fec5227c8793b75;
            roots[9]=108'h65fcf0c54c9198798e6e87d7e14;
            roots[10]=108'h22c2b3467fdbd1149962b5145d5;
            roots[11]=108'h2f3400a4fd05c508e55fa12353f;
            roots[12]=108'h92a60d2ebed5570f0ce0df9ff28;
            roots[13]=108'h9fdd88f6541fe88c189c4cf4702;
            roots[14]=108'h68f3e32a90b3f9f7028b2f4a927;
            roots[15]=108'h3a28bf06452e8891d43ba6d6f4b;
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

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_gs_aw8_p16_f0_s2_v1 #(
    parameter int WIDTH=54,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=4,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=16'h3210,
    parameter logic [WIDTH-1:0] FIRST_ROOT=54'h0230a5330611c1,
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
            roots[0]=54'h0230a5330611c1;
            roots[1]=54'h28216001e0201b;
            roots[2]=54'h1ad83b99561d7a;
            roots[3]=54'h2368173c8c0454;
            roots[4]=54'h137deca860c798;
            roots[5]=54'h0ff15c75b1dcc2;
            roots[6]=54'h2b98b582b4a2e1;
            roots[7]=54'h114e61c4574dd9;
            roots[8]=54'h005e71aac7b84c;
            roots[9]=54'h1d4a400280176f;
            roots[10]=54'h2deb22d59214bd;
            roots[11]=54'h0453a4458ac377;
            roots[12]=54'h18908989106ba7;
            roots[13]=54'h2a541350df91dd;
            roots[14]=54'h16ce9118ea9a3f;
            roots[15]=54'h22aca05c5e63be;
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

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_gs_aw8_p16_f0_s3_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=4,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=16'h3210,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h367778e,
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
            roots[0]=27'h367778e;
            roots[1]=27'h26e1a37;
            roots[2]=27'h3ce84c7;
            roots[3]=27'h5beffa4;
            roots[4]=27'h4bf0b2f;
            roots[5]=27'h1bf39a0;
            roots[6]=27'h63c2665;
            roots[7]=27'h23fa019;
            roots[8]=27'h4f10555;
            roots[9]=27'h0d52860;
            roots[10]=27'h0703b31;
            roots[11]=27'h1bfa532;
            roots[12]=27'h2ca4a7a;
            roots[13]=27'h2e2fe25;
            roots[14]=27'h37938e3;
            roots[15]=27'h02361c5;
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

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_gs_aw8_p16_f0_s4_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=3,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=12'h321,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h363385a,
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
            roots[0]=27'h363385a;
            roots[1]=27'h14dfa52;
            roots[2]=27'h1c9b4b7;
            roots[3]=27'h1fc8c8f;
            roots[4]=27'h1518ae5;
            roots[5]=27'h1b3bf90;
            roots[6]=27'h55f4bc7;
            roots[7]=27'h596f59f;
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

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_gs_aw8_p16_f0_s5_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=2,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=8'h32,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h01e23e9,
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
            roots[0]=27'h01e23e9;
            roots[1]=27'h59c6740;
            roots[2]=27'h202197e;
            roots[3]=27'h17ba326;
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

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_gs_aw8_p16_f0_s6_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=1,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=4'h3,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h2fe48ee,
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
            roots[0]=27'h2fe48ee;
            roots[1]=27'h1651cd8;
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

// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_gs_aw8_p16_f0_s7_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=0,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h35a9fbf,
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
            roots[0]=27'h35a9fbf;
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

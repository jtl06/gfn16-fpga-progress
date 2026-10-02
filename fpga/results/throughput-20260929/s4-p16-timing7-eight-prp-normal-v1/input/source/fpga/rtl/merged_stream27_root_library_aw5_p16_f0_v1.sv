// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw5_p16_f0_s0_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=2,
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
module merged_stream27_root_ct_aw5_p16_f0_s1_v1 #(
    parameter int WIDTH=54,
    parameter int FRAME_T=2,
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
module merged_stream27_root_ct_aw5_p16_f0_s2_v1 #(
    parameter int WIDTH=108,
    parameter int FRAME_T=2,
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
module merged_stream27_root_ct_aw5_p16_f0_s3_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=2,
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
module merged_stream27_root_ct_aw5_p16_f0_s4_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=2,
    parameter int ADDRESS_BITS=1,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
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
module merged_stream27_root_gs_aw5_p16_f0_s0_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=2,
    parameter int ADDRESS_BITS=1,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'h47f40338f09994df9cd04bf0b2fb7dff48f3a131d370d1bb67778e,
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
            roots[0]=216'h47f40338f09994df9cd04bf0b2fb7dff48f3a131d370d1bb67778e;
            roots[1]=216'h046c38ade4e38d717f12aca4a7a37f4a641c0ecc46a94304f10555;
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
module merged_stream27_root_gs_aw5_p16_f0_s1_v1 #(
    parameter int WIDTH=108,
    parameter int FRAME_T=2,
    parameter int ADDRESS_BITS=1,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=108'h3f9191e726d2dca6fd29363385a,
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
            roots[0]=108'h3f9191e726d2dca6fd29363385a;
            roots[1]=108'hb2deb3f57d2f1cd9dfc81518ae5;
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
module merged_stream27_root_gs_aw5_p16_f0_s2_v1 #(
    parameter int WIDTH=54,
    parameter int FRAME_T=2,
    parameter int ADDRESS_BITS=1,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=54'h2ce33a001e23e9,
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
            roots[0]=54'h2ce33a001e23e9;
            roots[1]=54'h0bdd193202197e;
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
module merged_stream27_root_gs_aw5_p16_f0_s3_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=2,
    parameter int ADDRESS_BITS=1,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
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
module merged_stream27_root_gs_aw5_p16_f0_s4_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=2,
    parameter int ADDRESS_BITS=0,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h1d4fdf4,
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
            roots[0]=27'h1d4fdf4;
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

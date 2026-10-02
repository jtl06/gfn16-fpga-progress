// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw8_p16_f1_s0_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=0,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h29f81f5,
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
            roots[0]=27'h29f81f5;
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
module merged_stream27_root_ct_aw8_p16_f1_s1_v1 #(
    parameter int WIDTH=54,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=0,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=54'h0d635d0c1e2886,
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
            roots[0]=54'h0d635d0c1e2886;
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
module merged_stream27_root_ct_aw8_p16_f1_s2_v1 #(
    parameter int WIDTH=108,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=0,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=108'h4a5e286e948088de21f184be001,
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
            roots[0]=108'h4a5e286e948088de21f184be001;
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
module merged_stream27_root_ct_aw8_p16_f1_s3_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=0,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'h0d48f849038a8589705388adc562da55ecdae3ed15fca6c813a1e0,
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
            roots[0]=216'h0d48f849038a8589705388adc562da55ecdae3ed15fca6c813a1e0;
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
module merged_stream27_root_ct_aw8_p16_f1_s4_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=1,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=4'h3,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'h2ff9fa00677ce8a9e9f5c18c88f5f52736df75f69980beda0c8e38,
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
            roots[0]=216'h2ff9fa00677ce8a9e9f5c18c88f5f52736df75f69980beda0c8e38;
            roots[1]=216'h538ffc6b0010c1ff6983bf548f15971a3ae705d2c0bccac3a1fee2;
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
module merged_stream27_root_ct_aw8_p16_f1_s5_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=2,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=8'h32,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'h48b2a40ab5c5c46251200c2b8855b0b056b91be49ef903c9d1fe28,
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
            roots[0]=216'h48b2a40ab5c5c46251200c2b8855b0b056b91be49ef903c9d1fe28;
            roots[1]=216'h5a3b96e25b2ddd48499738215073ffe9e6c41cad184a4c3b853be0;
            roots[2]=216'h4807052bffc55cd743493b590ae7eedff08d024d1c6a31ac183a7c;
            roots[3]=216'h4d1458066fd5720fb286284b7f96049efce0aba118ed01b3b86ddd;
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
module merged_stream27_root_ct_aw8_p16_f1_s6_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=3,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=12'h321,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'h082189e09441b5c401341a39ea41a5f90cc4100050e9166b1922d0,
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
            roots[0]=216'h082189e09441b5c401341a39ea41a5f90cc4100050e9166b1922d0;
            roots[1]=216'h801fcfe6747fa52cc3cc15a2ce22154eb4162f0a5a18a79aaba553;
            roots[2]=216'h1b005d8ebe44e976f25d0a245ed2a3b3b6ff265b5cf932db5e0b57;
            roots[3]=216'h42da2102e35760e99196105c1b903ae86651f3ee97d6ddbbf3637c;
            roots[4]=216'h1e8ba8a61f489458b6edbedf25e5e9723c8ed205ce3e1b99b17b80;
            roots[5]=216'h1ea3730d7d15ccfe8d9b3f48cff695435a50911498faed5b05b40d;
            roots[6]=216'h2dea8da565e250e59e8c1989bf42403c4214b3da19509d23b2bdaa;
            roots[7]=216'h434069a4c3b359733de98fce4936b84b3ca356c498b6af407eefa4;
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
module merged_stream27_root_ct_aw8_p16_f1_s7_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=4,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=16'h3210,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'h768ab0ac8e44104b0d7e928901209f98849a85b712e35c286161ba,
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
            roots[0]=216'h768ab0ac8e44104b0d7e928901209f98849a85b712e35c286161ba;
            roots[1]=216'h587e10c0fec0d5cfe4d18026b4b7050ed208c73a50969ff3269256;
            roots[2]=216'h74632e66220728d9daab066e57c53b06605dd7ff5deab338d65606;
            roots[3]=216'h6aa39ee891f6f063be76bfcb6ca15bcde252f14f5d0eb7da077162;
            roots[4]=216'h540f2d068db689974b9fc11b30e69c4678a9547d43a735a0cab105;
            roots[5]=216'h12da2e4a2ff749f8465113d61ab36b2660921822c4cde8798395a5;
            roots[6]=216'h6405d5846cdc5606cde1bd677a47ef16e6d18e45088a381154d8e7;
            roots[7]=216'h73630e84201eb91c147f9523db07d6b3726f9df08d292ed011705d;
            roots[8]=216'h138cb82f645a8861536f8eb35d61170e7a8101345930a81bd1b4c6;
            roots[9]=216'h2613a14680385c9d27de9c7adaf464d528dcaac7def9e39b252c18;
            roots[10]=216'h61c399a1b18b9997ed84b0c14fb3d4b718d72c92c4b2750419b035;
            roots[11]=216'h71a23ac08260b4f703f2216da527dd103aa01be2948497506a9f22;
            roots[12]=216'h06588a6d798f1d4a9bda8862d1976504926c216bd8a3b2d86ae012;
            roots[13]=216'h2519cae705b30168f7ab0b2f9a93a046ac1a4f1a8fd9d2a00939ff;
            roots[14]=216'h0bf6eec8354fdd7c07da9e59aca108cfb240d57dc2da8caafdfe9f;
            roots[15]=216'h441f7d70316dd04fcc25348a3847a9584406e9e55497500a1bdddd;
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
module merged_stream27_root_gs_aw8_p16_f1_s0_v1 #(
    parameter int WIDTH=216,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=4,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=16'h3210,
    parameter logic [WIDTH-1:0] FIRST_ROOT=216'h40844486345802022c3604b53df1aeb8fae019edc09d2469ff0416,
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
            roots[0]=216'h40844486345802022c3604b53df1aeb8fae019edc09d2469ff0416;
            roots[1]=216'h24402c4f12b9b18e550539b9828474ca6e49fc1310956053c0488b;
            roots[2]=216'h82d8c0489316b5db61cba4fdcab6da0cb053842ad2f49a0af731aa;
            roots[3]=216'h76a3fde42e269937bd2906d7db8733a5d062b213060ce1d3ed3bae;
            roots[4]=216'h76ac1be63db45ccfc83b83177e44124b5e8c7e075ffb3ea092ee2b;
            roots[5]=216'h00c9f98e26c58461a6db235a475227d60c3c093e1d9ce8d911e334;
            roots[6]=216'h1f5a7d21030e3856aa711ed956d4b0a4a4b96c1113ff8f52ef62f7;
            roots[7]=216'h09c96763e7abf90dfd9839478c46699456d7564882374afb839a40;
            roots[8]=216'h81d1f489eb689d30c41f834a64859b84a279f5c098bfc29884e78d;
            roots[9]=216'h5964e34c3ae3fc6ce376828748e09310ba04990f98264760ffd155;
            roots[10]=216'h538d4b8e190bc8ebcfbb26a6cd15c53cac0bdcd7cca0117b892e8f;
            roots[11]=216'h6aa9df8eac6534bd57060d1dcc501c99e63c5a3093e492f97f8699;
            roots[12]=216'h4311d3e1f8a4196a1d623721910046926ed620c50fdc1228cae30a;
            roots[13]=216'h69353f618aa6695450021827cd1772350a9b12aad4bbf1b87ce68e;
            roots[14]=216'h1f2db56834b00dfe718c09d789883b296c200d979f027e615c0f7b;
            roots[15]=216'h77d3c8e70e51f0daf492bd033bf5eedfdee2794107e377e86baa7c;
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
module merged_stream27_root_gs_aw8_p16_f1_s1_v1 #(
    parameter int WIDTH=108,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=4,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=16'h3210,
    parameter logic [WIDTH-1:0] FIRST_ROOT=108'h64636dc4e610b9778995a05fcb4,
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
            roots[0]=108'h64636dc4e610b9778995a05fcb4;
            roots[1]=108'h74220ba424a864c952778c3da63;
            roots[2]=108'h50ec81a9530ba56343b6ab0ab94;
            roots[3]=108'h0da84ae3d7b175e6984caffe1e0;
            roots[4]=108'h056e60488b932c605d4732ae469;
            roots[5]=108'h23497e840289596eddd78d55e54;
            roots[6]=108'h0641b46dba48994c16ee32ba2bc;
            roots[7]=108'h4dd0902960f238f25bf512b46e3;
            roots[8]=108'h6347c909337355b39514a092ef9;
            roots[9]=108'h059390a49491296c1823c028bce;
            roots[10]=108'h6fb74284c86d1c383763b47fd15;
            roots[11]=108'h183e954203669811b34a2ce2626;
            roots[12]=108'h58ba63e719e1a541700c01f0182;
            roots[13]=108'h2e8b55c373ac39e3a1ec31558a7;
            roots[14]=108'h4f8c2ba25ff665fd77ca3def3b2;
            roots[15]=108'h20dba6280b74d087e00034d037b;
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
module merged_stream27_root_gs_aw8_p16_f1_s2_v1 #(
    parameter int WIDTH=54,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=4,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=16'h3210,
    parameter logic [WIDTH-1:0] FIRST_ROOT=54'h14205529b75d41,
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
            roots[0]=54'h14205529b75d41;
            roots[1]=54'h0cda4040009af5;
            roots[2]=54'h04ea8be91db083;
            roots[3]=54'h033c9121025fcb;
            roots[4]=54'h09007551dfc7d8;
            roots[5]=54'h03537a9a71796f;
            roots[6]=54'h0f5fb668289009;
            roots[7]=54'h003e2c2892b9cc;
            roots[8]=54'h1c49a4514e234a;
            roots[9]=54'h04ef57d18f6cd3;
            roots[10]=54'h087c6a6a200b0e;
            roots[11]=54'h04d6210916b67a;
            roots[12]=54'h0b947481da6ae1;
            roots[13]=54'h1aea3be35b5dc1;
            roots[14]=54'h09dc837947a7d6;
            roots[15]=54'h12700ec840df88;
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
module merged_stream27_root_gs_aw8_p16_f1_s3_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=4,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=16'h3210,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h183801e,
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
            roots[0]=27'h183801e;
            roots[1]=27'h15ffbd1;
            roots[2]=27'h0212cfa;
            roots[3]=27'h02ab710;
            roots[4]=27'h15472e4;
            roots[5]=27'h083e8b6;
            roots[6]=27'h40866a9;
            roots[7]=27'h07e011f;
            roots[8]=27'h2a03031;
            roots[9]=27'h40620c7;
            roots[10]=27'h2cc2c16;
            roots[11]=27'h0073772;
            roots[12]=27'h1256c66;
            roots[13]=27'h0a22827;
            roots[14]=27'h0efe826;
            roots[15]=27'h21371c9;
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
module merged_stream27_root_gs_aw8_p16_f1_s4_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=3,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=12'h321,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h3b5b83f,
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
            roots[0]=27'h3b5b83f;
            roots[1]=27'h1df1d60;
            roots[2]=27'h10d1f5a;
            roots[3]=27'h39523ab;
            roots[4]=27'h2b2d50b;
            roots[5]=27'h0b4704d;
            roots[6]=27'h1606b28;
            roots[7]=27'h40c5e21;
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
module merged_stream27_root_gs_aw8_p16_f1_s5_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=2,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=8'h32,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h1cd0ebe,
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
            roots[0]=27'h1cd0ebe;
            roots[1]=27'h07adfdf;
            roots[2]=27'h263bc1e;
            roots[3]=27'h3d42000;
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
module merged_stream27_root_gs_aw8_p16_f1_s6_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=1,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=4'h3,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h2739460,
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
            roots[0]=27'h2739460;
            roots[1]=27'h001d77b;
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
module merged_stream27_root_gs_aw8_p16_f1_s7_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=16,
    parameter int ADDRESS_BITS=0,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h122ca2c,
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
            roots[0]=27'h122ca2c;
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

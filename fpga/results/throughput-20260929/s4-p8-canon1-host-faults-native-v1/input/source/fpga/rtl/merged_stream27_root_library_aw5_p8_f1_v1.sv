// S-M2 source-only root service. One packed ROM read per accepted physical row.
// Root addresses gather only contributing row bits, not row modulo ROM depth.
// Canceled occupied rows advance. Only rst_n/frame_start re-establish cadence.
module merged_stream27_root_ct_aw5_p8_f1_s0_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=4,
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
module merged_stream27_root_ct_aw5_p8_f1_s1_v1 #(
    parameter int WIDTH=54,
    parameter int FRAME_T=4,
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
module merged_stream27_root_ct_aw5_p8_f1_s2_v1 #(
    parameter int WIDTH=108,
    parameter int FRAME_T=4,
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
module merged_stream27_root_ct_aw5_p8_f1_s3_v1 #(
    parameter int WIDTH=108,
    parameter int FRAME_T=4,
    parameter int ADDRESS_BITS=1,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=2'h1,
    parameter logic [WIDTH-1:0] FIRST_ROOT=108'h2da55ecdae3ed15fca6c813a1e0,
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
            roots[0]=108'h2da55ecdae3ed15fca6c813a1e0;
            roots[1]=108'h0d48f849038a8589705388adc56;
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
module merged_stream27_root_ct_aw5_p8_f1_s4_v1 #(
    parameter int WIDTH=108,
    parameter int FRAME_T=4,
    parameter int ADDRESS_BITS=2,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=4'h4,
    parameter logic [WIDTH-1:0] FIRST_ROOT=108'h5f52736df75f69980beda0c8e38,
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
            roots[0]=108'h5f52736df75f69980beda0c8e38;
            roots[1]=108'h2ff9fa00677ce8a9e9f5c18c88f;
            roots[2]=108'h5971a3ae705d2c0bccac3a1fee2;
            roots[3]=108'h538ffc6b0010c1ff6983bf548f1;
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
module merged_stream27_root_gs_aw5_p8_f1_s0_v1 #(
    parameter int WIDTH=108,
    parameter int FRAME_T=4,
    parameter int ADDRESS_BITS=2,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=4'h4,
    parameter logic [WIDTH-1:0] FIRST_ROOT=108'h0556e20084b3e8affde8983801e,
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
            roots[0]=108'h0556e20084b3e8affde8983801e;
            roots[1]=108'h0fc023f0219aa441f45b15472e4;
            roots[2]=108'h00e6ee4b30b05a031063aa03031;
            roots[3]=108'h426e3923bfa0985114139256c66;
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
module merged_stream27_root_gs_aw5_p8_f1_s1_v1 #(
    parameter int WIDTH=54,
    parameter int FRAME_T=4,
    parameter int ADDRESS_BITS=2,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=4'h4,
    parameter logic [WIDTH-1:0] FIRST_ROOT=54'h0ef8eb03b5b83f,
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
            roots[0]=54'h0ef8eb03b5b83f;
            roots[1]=54'h1ca91d590d1f5a;
            roots[2]=54'h05a3826ab2d50b;
            roots[3]=54'h2062f109606b28;
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
module merged_stream27_root_gs_aw5_p8_f1_s2_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=4,
    parameter int ADDRESS_BITS=2,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=4'h4,
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
module merged_stream27_root_gs_aw5_p8_f1_s3_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=4,
    parameter int ADDRESS_BITS=1,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=2'h1,
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
module merged_stream27_root_gs_aw5_p8_f1_s4_v1 #(
    parameter int WIDTH=27,
    parameter int FRAME_T=4,
    parameter int ADDRESS_BITS=0,
    parameter int ROW_W=(FRAME_T>1 ? $clog2(FRAME_T) : 1),
    parameter int MAP_W=(ADDRESS_BITS>0 ? ADDRESS_BITS*ROW_W : 1),
    parameter logic [MAP_W-1:0] ADDRESS_ROW_POSITIONS=1'h0,
    parameter logic [WIDTH-1:0] FIRST_ROOT=27'h0d6515e,
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
            roots[0]=27'h0d6515e;
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

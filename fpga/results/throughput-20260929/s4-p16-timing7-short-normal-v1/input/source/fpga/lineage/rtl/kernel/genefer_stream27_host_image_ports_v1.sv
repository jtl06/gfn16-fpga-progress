// S4 shadow host image: N signed32 words in P natural-block banks.
// Extra shadow storage is 32*N bits. Copying a canonical image takes N scalar
// commit edges; the caller accounts for that cost outside warm square timing.
// Accepted reads use the actual synchronous RAM output on E0 after NBA.
// Commit > row read > scalar host, and scalar load wins over scalar read.
module genefer_stream27_host_image_ports_v1 #(
    parameter int AW=5,P=16,
    parameter int ROW_W=AW-$clog2(P)
) (
    input logic clk,rst_n,host_access,load_we,read_en,
    input logic [AW-1:0] host_addr,
    input logic signed [31:0] write_data,
    input logic row_read_req,
    input logic [ROW_W-1:0] row_read_address,
    input logic commit_we,
    input logic [AW-1:0] commit_address,
    input logic [31:0] commit_word,
    output logic read_valid,
    output logic signed [95:0] read_data,
    output logic row_read_valid,
    output logic [P*32-1:0] row_read_data
);
    localparam int LP=$clog2(P),T=1<<ROW_W;
    logic [P-1:0] ram_re,ram_we;
    logic [ROW_W-1:0] ram_ra[0:P-1],ram_wa[0:P-1];
    logic [31:0] ram_w[0:P-1],ram_q[0:P-1];
    logic [LP-1:0] scalar_bank_d;
    wire [LP-1:0] host_bank=host_addr[AW-1:ROW_W];
    wire [LP-1:0] commit_bank=commit_address[AW-1:ROW_W];
    wire commit_fire=rst_n && commit_we;
    wire row_fire=rst_n && !commit_we && row_read_req;
    wire host_fire=rst_n && !commit_we && !row_read_req && host_access;
    wire scalar_read_fire=host_fire && !load_we && read_en;
    assign read_data=$signed({{64{ram_q[scalar_bank_d][31]}},ram_q[scalar_bank_d]});
    for(genvar b=0;b<P;b=b+1)begin: natural_blocks
        assign row_read_data[b*32+:32]=ram_q[b];
        always_comb begin
            ram_re[b]=0;ram_we[b]=0;ram_ra[b]=0;ram_wa[b]=0;ram_w[b]=0;
            if(commit_fire)begin
                if(commit_bank==LP'(b))begin
                    ram_we[b]=1;ram_wa[b]=commit_address[ROW_W-1:0];ram_w[b]=commit_word;
                end
            end else if(row_fire)begin
                ram_re[b]=1;ram_ra[b]=row_read_address;
            end else if(host_fire && host_bank==LP'(b))begin
                if(load_we)begin
                    ram_we[b]=1;ram_wa[b]=host_addr[ROW_W-1:0];ram_w[b]=write_data;
                end else if(read_en)begin ram_re[b]=1;ram_ra[b]=host_addr[ROW_W-1:0];end
            end
        end
        genefer_sdp_ram32 #(.AW(ROW_W),.DEPTH(T)) image_ram (
            .clk,.rst_n,.read_en(ram_re[b]),.write_en(ram_we[b]),
            .read_addr(ram_ra[b]),.write_addr(ram_wa[b]),
            .write_data(ram_w[b]),.read_data(ram_q[b])
        );
        // synthesis translate_off
        always @(posedge clk)if(rst_n && ram_re[b] && ram_we[b])
            $fatal(1,"HOST_IMAGE_MIXED_LEAF_ACCESS");
        // synthesis translate_on
    end
    // Only eligibility and the scalar bank selector reset. RAM/payload retain.
    // No extra payload FF: bank selector and RAM read register own SAME E0.
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin read_valid<=0;row_read_valid<=0;scalar_bank_d<=0;end
        else begin
            read_valid<=scalar_read_fire;row_read_valid<=row_fire;
            if(scalar_read_fire)scalar_bank_d<=host_bank;
        end
    end
    // synthesis translate_off
    initial if(AW<5 || AW>16 || (P!=8 && P!=16) ||
               ROW_W!=AW-$clog2(P) || ROW_W<1)
        $fatal(1,"HOST_IMAGE_GEOMETRY");
    // synthesis translate_on
endmodule

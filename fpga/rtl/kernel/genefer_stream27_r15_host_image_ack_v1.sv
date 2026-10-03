// Two-context shadow transport only. The wrapper owns phase/order/publication.
// Natural address = block*(N/P)+row. Raw dense capture and scalar canonical
// copy may run on DIFFERENT contexts on the same edge. No payload reset/FF.
module genefer_stream27_r15_host_image_ack_v1 #(
    parameter int AW=5,P=16,CONTEXTS=2,OWNER_W=56,
    parameter int ROW_W=AW-$clog2(P)
) (
    input logic clk,rst_n,quarantine,
    input logic [CONTEXTS-1:0] owner_enabled,
    input logic [CONTEXTS*OWNER_W-1:0] live_owner,
    input logic host_access,load_we,read_en,host_context,
    input logic [AW-1:0] host_addr,
    input logic signed [31:0] write_data,
    input logic row_read_req,row_read_context,
    input logic [ROW_W-1:0] row_read_address,
    input logic [OWNER_W-1:0] row_read_owner,
    input logic commit_we,commit_context,
    input logic [AW-1:0] commit_address,
    input logic [31:0] commit_word,
    input logic [OWNER_W-1:0] commit_owner,
    input logic row_write_req,row_write_context,
    input logic [ROW_W-1:0] row_write_address,
    input logic [P*32-1:0] row_write_data,
    input logic [OWNER_W-1:0] row_write_owner,
    output logic read_valid,read_context,
    output logic signed [95:0] read_data,
    output logic [OWNER_W-1:0] read_owner,
    output logic row_read_valid,row_response_context,
    output logic [P*32-1:0] row_read_data,
    output logic [OWNER_W-1:0] row_response_owner,
    output logic commit_ack,row_write_ack,rejected,
    output logic host_write_ready,host_write_ack
);
    localparam int LP=$clog2(P),T=1<<ROW_W;
    wire allow_access=rst_n && !quarantine;
    wire commit_authorized=owner_enabled[commit_context] &&
        commit_owner==live_owner[commit_context*OWNER_W+:OWNER_W];
    wire capture_authorized=owner_enabled[row_write_context] &&
        row_write_owner==live_owner[row_write_context*OWNER_W+:OWNER_W];
    wire row_authorized=owner_enabled[row_read_context] &&
        row_read_owner==live_owner[row_read_context*OWNER_W+:OWNER_W];
    logic [CONTEXTS-1:0] denied;
    for(genvar c=0;c<CONTEXTS;c=c+1)begin: context_denial
        assign denied[c]=(commit_we && commit_context==1'(c) && !commit_authorized) ||
            (row_write_req && row_write_context==1'(c) && !capture_authorized) ||
            (row_read_req && row_read_context==1'(c) && !row_authorized);
    end
    wire commit_fire=allow_access && commit_we && !denied[commit_context];
    wire capture_fire=allow_access && row_write_req && !denied[row_write_context] &&
        !(commit_fire && commit_context==row_write_context);
    wire row_fire=allow_access && row_read_req && !denied[row_read_context] &&
        !(commit_fire && commit_context==row_read_context) &&
        !(capture_fire && row_write_context==row_read_context);
    wire host_fire=allow_access && host_access && !denied[host_context] &&
        !(commit_fire && commit_context==host_context) &&
        !(capture_fire && row_write_context==host_context) &&
        !(row_fire && row_read_context==host_context);
    assign host_write_ready=host_fire;
    logic host_write_ack_d;
    assign host_write_ack=allow_access && host_write_ack_d;
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)host_write_ack_d<=0;
        else host_write_ack_d<=host_fire && load_we;
    end
    wire scalar_fire=host_fire && !load_we && read_en;
    wire reject_fire=allow_access && ((|denied) ||
        (commit_fire && row_write_req && commit_context==row_write_context));
    wire [LP-1:0] host_bank=host_addr[AW-1:ROW_W];
    wire [LP-1:0] commit_bank=commit_address[AW-1:ROW_W];
    logic [LP-1:0] scalar_bank_d;
    logic read_valid_d,row_valid_d,commit_ack_d,capture_ack_d,rejected_d;
    logic [31:0] ram_q[0:CONTEXTS-1][0:P-1];
    assign read_valid=allow_access && read_valid_d;
    assign row_read_valid=allow_access && row_valid_d;
    assign commit_ack=allow_access && commit_ack_d;
    assign row_write_ack=allow_access && capture_ack_d;
    assign rejected=allow_access && rejected_d;
    assign read_data=$signed({{64{ram_q[read_context][scalar_bank_d][31]}},ram_q[read_context][scalar_bank_d]});
    for(genvar b=0;b<P;b=b+1)begin: row_outputs
        assign row_read_data[b*32+:32]=ram_q[row_response_context][b];
    end
    for(genvar c=0;c<CONTEXTS;c=c+1)begin: contexts
        for(genvar b=0;b<P;b=b+1)begin: natural_blocks
            logic ram_re,ram_we;
            logic [ROW_W-1:0] ram_ra,ram_wa;
            logic [31:0] ram_w;
            always_comb begin
                ram_re=0;ram_we=0;ram_ra=0;ram_wa=0;ram_w=0;
                if(commit_fire && commit_context==1'(c))begin
                    if(commit_bank==LP'(b))begin
                        ram_we=1;ram_wa=commit_address[ROW_W-1:0];ram_w=commit_word;
                    end
                end else if(capture_fire && row_write_context==1'(c))begin
                    ram_we=1;ram_wa=row_write_address;ram_w=row_write_data[b*32+:32];
                end else if(row_fire && row_read_context==1'(c))begin
                    ram_re=1;ram_ra=row_read_address;
                end else if(host_fire && host_context==1'(c) && host_bank==LP'(b))begin
                    if(load_we)begin ram_we=1;ram_wa=host_addr[ROW_W-1:0];ram_w=write_data;end
                    else if(read_en)begin ram_re=1;ram_ra=host_addr[ROW_W-1:0];end
                end
            end
            genefer_sdp_ram32 #(.AW(ROW_W),.DEPTH(T)) image_ram (
                .clk,.rst_n,.read_en(ram_re),.write_en(ram_we),.read_addr(ram_ra),
                .write_addr(ram_wa),.write_data(ram_w),.read_data(ram_q[c][b])
            );
            // synthesis translate_off
            always @(posedge clk)if(rst_n && ram_re && ram_we)
                $fatal(1,"SHADOW_ROW_MIXED_LEAF_ACCESS");
            // synthesis translate_on
        end
    end
    // Tags/selectors own the SAME accepted E0 as the synchronous RAM q.
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            read_valid_d<=0;row_valid_d<=0;commit_ack_d<=0;capture_ack_d<=0;rejected_d<=0;
            scalar_bank_d<=0;read_context<=0;read_owner<=0;
            row_response_context<=0;row_response_owner<=0;
        end else begin
            read_valid_d<=scalar_fire;row_valid_d<=row_fire;
            commit_ack_d<=commit_fire;capture_ack_d<=capture_fire;rejected_d<=reject_fire;
            if(scalar_fire)begin scalar_bank_d<=host_bank;read_context<=host_context;
                read_owner<=live_owner[host_context*OWNER_W+:OWNER_W];end
            if(row_fire)begin row_response_context<=row_read_context;row_response_owner<=row_read_owner;end
        end
    end
    // synthesis translate_off
    initial if(AW<5 || AW>16 || (P!=8 && P!=16) || CONTEXTS!=2 || OWNER_W<1 ||
        ROW_W!=AW-$clog2(P) || ROW_W<1)$fatal(1,"SHADOW_ROW_GEOMETRY");
    // synthesis translate_on
endmodule

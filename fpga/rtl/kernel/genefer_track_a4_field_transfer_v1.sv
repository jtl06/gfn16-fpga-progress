// r13 transfer boundary. Two explicit stages outward and two inward.
// Caller request E0 -> field RAM accepts E2 -> caller consumes response E5.
// Caller write E0 -> field RAM accepts E2; quiet after E2 is observed at E3,
// together with the destination's registered error. Reset/cancel drops tokens.
module genefer_track_a4_field_transfer_v1 #(parameter int AW=16) (
    input logic clk,rst_n,cancel,
    input logic read_en,write_en,
    input logic [AW-1:0] read_offset,write_offset,
    input logic [15:0] read_mask,write_mask,
    input logic [1535:0] write_words,
    output logic [2:0] read_valid,
    output logic [47:0] read_masks,
    output logic [3*AW-1:0] read_offsets,
    output logic [1535:0] read_words,
    output logic busy,quiet,error,
    output logic field_read_en,field_write_en,
    output logic [AW-1:0] field_read_offset,field_write_offset,
    output logic [15:0] field_read_mask,field_write_mask,
    output logic [1535:0] field_write_words,
    input logic [2:0] field_read_valid,
    input logic [47:0] field_read_masks,
    input logic [3*AW-1:0] field_read_offsets,
    input logic [1535:0] field_read_words,
    input logic field_error
);
    logic [1:0] request_read,request_write,response_valid;
    logic [AW-1:0] source_read_offset,source_write_offset,destination_read_offset,destination_write_offset;
    logic [15:0] source_read_mask,source_write_mask,destination_read_mask,destination_write_mask;
    logic [1535:0] source_write_words,destination_write_words,response_source_words,response_destination_words;
    logic [47:0] response_source_masks,response_destination_masks;
    logic [3*AW-1:0] response_source_offsets,response_destination_offsets;
    logic read_due;
    logic [AW-1:0] due_offset;
    logic [15:0] due_mask;
    logic protocol_fault;
    always_comb begin
        protocol_fault=field_read_valid!={3{read_due}};
        for(int f=0;f<3;f=f+1)
            if(field_read_valid[f] && (field_read_masks[f*16+:16]!=due_mask ||
                field_read_offsets[f*AW+:AW]!=due_offset))protocol_fault=1;
    end
    wire allow_transfer=rst_n && !cancel && !error && !field_error && !protocol_fault;
    assign field_read_en=request_read[1] && allow_transfer;
    assign field_write_en=request_write[1] && allow_transfer;
    assign field_read_offset=destination_read_offset;
    assign field_write_offset=destination_write_offset;
    assign field_read_mask=destination_read_mask;
    assign field_write_mask=destination_write_mask;
    assign field_write_words=destination_write_words;
    assign read_valid={3{response_valid[1] && allow_transfer}};
    assign read_masks=response_destination_masks;
    assign read_offsets=response_destination_offsets;
    assign read_words=response_destination_words;
    assign busy=read_en || write_en || (|request_read) || (|request_write) ||
        read_due || (|response_valid) || (|field_read_valid);
    assign quiet=!busy && allow_transfer;
    // Physical field-local destination stages: no combinational reduction or
    // cross-field arithmetic on the destination side of this chip-crossing hop.
    for(genvar f=0;f<3;f=f+1)begin: field_local
        always_ff @(posedge clk)if(allow_transfer)begin
            if(write_en)source_write_words[f*512+:512]<=write_words[f*512+:512];
            if(request_write[0])destination_write_words[f*512+:512]<=source_write_words[f*512+:512];
            if(&field_read_valid)response_source_words[f*512+:512]<=field_read_words[f*512+:512];
            if(response_valid[0])response_destination_words[f*512+:512]<=response_source_words[f*512+:512];
        end
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            request_read<=0;request_write<=0;response_valid<=0;read_due<=0;error<=0;
            source_read_offset<=0;source_write_offset<=0;destination_read_offset<=0;destination_write_offset<=0;
            source_read_mask<=0;source_write_mask<=0;destination_read_mask<=0;destination_write_mask<=0;
            due_offset<=0;due_mask<=0;response_source_masks<=0;response_destination_masks<=0;
            response_source_offsets<=0;response_destination_offsets<=0;
        end else if(cancel)begin
            request_read<=0;request_write<=0;response_valid<=0;read_due<=0;error<=0;
        end else if(field_error || protocol_fault || error)begin
            request_read<=0;request_write<=0;response_valid<=0;read_due<=0;error<=1;
        end else begin
            request_read<={request_read[0],read_en};request_write<={request_write[0],write_en};
            response_valid<={response_valid[0],&field_read_valid};read_due<=field_read_en;
            if(read_en)begin source_read_offset<=read_offset;source_read_mask<=read_mask;end
            if(write_en)begin source_write_offset<=write_offset;source_write_mask<=write_mask;end
            if(request_read[0])begin destination_read_offset<=source_read_offset;destination_read_mask<=source_read_mask;end
            if(request_write[0])begin destination_write_offset<=source_write_offset;destination_write_mask<=source_write_mask;end
            if(field_read_en)begin due_offset<=field_read_offset;due_mask<=field_read_mask;end
            if(&field_read_valid)begin response_source_masks<=field_read_masks;response_source_offsets<=field_read_offsets;end
            if(response_valid[0])begin response_destination_masks<=response_source_masks;response_destination_offsets<=response_source_offsets;end
        end
    end
endmodule

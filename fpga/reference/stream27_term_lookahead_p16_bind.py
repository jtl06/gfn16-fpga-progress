"""Private payload-only lookahead on an exact copied P16 timing field.

No original protocol authority/product/tag statement is changed. A raw
cycle+1 lookup feeds a data-only register, never an acceptance override.
"""
import copy,re,hashlib
from . import stream27_p16_timing_flags as donor
ROOT=donor.ROOT
SELF='reference/stream27_term_lookahead_p16_bind.py'
def need(ok,why):
    if not ok:raise ValueError(why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def once(text,old,new):
    need(text.count(old)==1,'TERM_LOOKAHEAD_ANCHOR:'+old[:80]);return text.replace(old,new,1)

def bind(bundle,enabled=1):
    need(type(enabled) is int and enabled in (0,1),'TERM_LOOKAHEAD_FLAG')
    b=copy.deepcopy(bundle)
    if not enabled:return b
    need(b['parameters']['P']==16 and b['parameters']['CONTEXTS']==1 and b['parameters'].get('TERM_SELECT_TOKEN')==1,'TERM_LOOKAHEAD_PARENT')
    oldtop=b['top'];parent=b['files'][oldtop+'.sv'];oldprotocol='genefer_stream27_epoch_protocol_v5'
    oldterm=re.findall(r' (genefer_stream27_term_context_\w+) #\(',parent)[0]
    protocol=b['files'][oldprotocol+'.sv'];term=b['files'][oldterm+'.sv']
    newprotocol=oldprotocol+'_payload_lookahead_v1';newterm=oldterm+'_payload_lookahead_v1';top=oldtop+'_payload_lookahead_v1'
    protocol=once(protocol,'module '+oldprotocol+' #','module '+newprotocol+' #')
    protocol=once(protocol,'output logic out_error,fault_pending','output logic out_error,fault_pending,\n    output logic [EPOCH_W-1:0] pointwise_payload_epoch_next,\n    output logic [$clog2(ROWS)-1:0] pointwise_payload_row_next')
    look='''    // Pure future payload lookup: never feeds accept/pending/commit authority.
    logic [31:0] payload_age_next[0:1];
    always_comb begin
        pointwise_payload_epoch_next='0;pointwise_payload_row_next='0;
        for(int i=0;i<2;i=i+1)begin
            payload_age_next[i]=(cycle_count+32'd1)-pw_first[i];
            if(valid[i] && payload_age_next[i]<32'(ROWS))begin
                pointwise_payload_epoch_next=epoch[i];
                pointwise_payload_row_next=ROW_W'(payload_age_next[i]);
            end
        end
    end
    // synthesis translate_off
    initial if(POINTWISE_FIRST<=1 || SINK_FIRST<POINTWISE_FIRST+ROWS)
        $fatal(1,"TERM_LOOKAHEAD_NONOVERLAP_GEOMETRY");
    // synthesis translate_on
'''
    protocol=once(protocol,'    // Validation consumes',look+'    // Validation consumes')
    term=once(term,'module '+oldterm+' #','module '+newterm+' #')
    term=once(term,'    input logic [LANES*27-1:0] next_coeff,next_seed_R_roots,','    input logic [LANES*27-1:0] next_coeff,next_seed_R_roots,\n    input logic [15:0] payload_epoch,\n    input logic [AW-$clog2(LANES)-1:0] payload_row,')
    term=once(term,'    wire reseed=next_row[ROW_W-1-:LANE_W]!=pointwise_row[ROW_W-1-:LANE_W];','    wire [ROW_W-1:0] payload_target=payload_row+ROW_W\'(4);\n    wire reseed=payload_target[ROW_W-1-:LANE_W]!=payload_row[ROW_W-1-:LANE_W];')
    term=once(term,'wire bypass_data=data_select_slot && product_owner==pointwise_owner && product_row==pointwise_row;','wire bypass_data=data_select_slot && product_owner=={payload_epoch,pointwise_owner[7:0]} && product_row==payload_row;')
    term=once(term,'current_term=context_data[pw_bank][pw_context];','current_term=context_data[payload_epoch[0]][payload_row[1:0]];')
    text=once(parent,'module '+oldtop+' #','module '+top+' #')
    text=once(text,oldprotocol+' #(',newprotocol+' #(')
    text=once(text,oldterm+' #(',newterm+' #(')
    text=once(text,'.pointwise_epoch(protocol_pw_epoch),.sink_epoch(protocol_sink_epoch),','.pointwise_epoch(protocol_pw_epoch),.sink_epoch(protocol_sink_epoch),\n  .pointwise_payload_epoch_next(protocol_payload_epoch_next),.pointwise_payload_row_next(protocol_payload_row_next),')
    declarations=''' wire [15:0] protocol_payload_epoch_next;
 wire [ROW_W-1:0] protocol_payload_row_next;
 logic [15:0] term_payload_epoch;logic [ROW_W-1:0] term_payload_row;
 logic [26:0] term_payload_coeff;
 wire [ROW_W-1:0] term_payload_target_next=protocol_payload_row_next+ROW_W'(4);
'''
    text=once(text,' wire [ROW_W-1:0] pw_row=protocol_pw_row;',declarations+' wire [ROW_W-1:0] pw_row=protocol_pw_row;')
    coeffs=re.findall(r'  assign term_next_coeff\[(\d+)\+:27\]=B_table\[protocol_pw_epoch\[0\]\]\[([^;]+)\];',text)
    need(len(coeffs)==16 and len({c[1] for c in coeffs})==1,'TERM_LOOKAHEAD_SHARED_COEFFICIENT')
    index=coeffs[0][1].replace('term_target','term_payload_target_next')
    for offset,_ in coeffs:
        old=f'  assign term_next_coeff[{offset}+:27]=B_table[protocol_pw_epoch[0]][{coeffs[0][1]}];'
        text=once(text,old,f'  assign term_next_coeff[{offset}+:27]=term_payload_coeff;')
    text=once(text,'.pw_slot(fwd_slot),.pw_start(fwd_start),.pw_row,','.pw_slot(fwd_slot),.pw_start(fwd_start),.pw_row(term_payload_row),')
    text=once(text,'.pointwise_row(pw_row),.next_coeff(term_next_coeff),','.pointwise_row(pw_row),.payload_epoch(term_payload_epoch),.payload_row(term_payload_row),.next_coeff(term_next_coeff),')
    registers=f''' // The coefficient and selection row are prepared for the NEXT sampling edge.
 // Data captures are not filtered by pending/accept authority. Real same-edge
 // B-table writes are forwarded exactly, including bit-reversed table layout.
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin term_payload_epoch<=0;term_payload_row<=0;end
  else begin term_payload_epoch<=protocol_payload_epoch_next;term_payload_row<=protocol_payload_row_next;end
 end
 always_ff @(posedge clk)if(rst_n)begin
  term_payload_coeff<=B_table[protocol_payload_epoch_next[0]][{index}];
  if(!stop && small_slot && small_capture && small_owner[8]==protocol_payload_epoch_next[0])
   term_payload_coeff<=small_data[27*int'(term_payload_target_next[ROW_W-1-:4])+:27];
 end
 // synthesis translate_off
 always @(negedge clk)if(rst_n && fwd_slot && !stop)begin
  if(term_payload_epoch!=protocol_pw_epoch || term_payload_row!=pw_row)
   $fatal(1,"TERM_LOOKAHEAD_CURRENT_ISSUE_METADATA");
  if(term_payload_coeff!=B_table[protocol_pw_epoch[0]][{coeffs[0][1]}])
   $fatal(1,"TERM_LOOKAHEAD_CURRENT_B_COEFFICIENT");
 end
 // synthesis translate_on
'''
    text=once(text,' always_ff @(posedge clk or negedge rst_n)begin\n  if(!rst_n)begin\n   input_remaining',registers+' always_ff @(posedge clk or negedge rst_n)begin\n  if(!rst_n)begin\n   input_remaining')
    b['files'].update({top+'.sv':text,newprotocol+'.sv':protocol,newterm+'.sv':term})
    b['top']=top
    b['source_dependencies']=list(dict.fromkeys(b['source_dependencies']+[SELF]))
    b['source_sha256']={name:sha((ROOT/name).read_bytes()) for name in b['source_dependencies']}
    b['rtl_sources']=[name for name in b['files'] if name.endswith('.sv')]
    b['generated_sha256']={name:sha(value.encode()) for name,value in b['files'].items()}
    b['term_lookahead']=dict(parent_top=oldtop,parent_term=oldterm,new_term=newterm,parent_protocol=oldprotocol,new_protocol=newprotocol,
        parent_root_sha256=sha(parent.encode()),product_capture_edges=4,initiation_interval=1,recurrence_distance=4,
        public_schedule_unchanged=True,authority_and_issue_tag_statements_unchanged=True,same_edge_B_write_forwarding=True,
        physical_gain_measured=False,promotion_allowed=False)
    return b

def prepare(n=256,field=1):
    return bind(donor.prepare_field(n,16,field,mode='warm',allow_full_constants=n==65536,
        boundary_inputreg=1,quarantine_replicas=1,final_gs_inputreg=1,term_select_token=1))

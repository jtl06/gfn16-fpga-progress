"""Real two-context shared field: four lookup banks and carried full owners.

CONTEXTS1 returns the frozen/shared flag bundle unchanged. CONTEXTS2 carries
{context,epoch16,generation8} through the main transform path and adds the
lookup bank to correction/term owners. Arithmetic/root definitions and normal
edge calendars are unchanged. Host/CRT/carry/finalization is separate work.
"""
import hashlib
from . import stream27_shared_field_flags as parent

ROOT=parent.ROOT
SELF='reference/stream27_shared_field_contexts.py'
PROTOCOL='rtl/kernel/genefer_stream27_epoch_protocol_contexts_v1.sv'
PROTOCOL_PIN='44f90cfc'


def need(ok,label):
    if not ok:raise ValueError(label)


def once(text,before,after):
    need(text.count(before)==1,'S4_CONTEXT_SOURCE_ANCHOR:'+before[:80])
    return text.replace(before,after,1)


def term_source(name,text):
    new=name+'_contexts_v1'
    text=once(text,'module '+name+' #','module '+new+' #')
    text=text.replace('[23:0]','[26:0]').replace('TAG_W=24+ROW_W','TAG_W=27+ROW_W')
    text=text.replace('[0:1]','[0:3]')
    text=once(text,'wire pw_bank=pointwise_owner[8],prod_bank=product_owner[8],seed_bank=seed_owner[8];',
        'wire [1:0] pw_bank=pointwise_owner[26:25],prod_bank=product_owner[26:25],seed_bank=seed_owner[26:25];')
    text=once(text,"context_valid[0]<='0;context_valid[1]<='0;",
        "for(int bank=0;bank<4;bank=bank+1)context_valid[bank]<='0;")
    return new,text


def prepare(n=32,p=8,field=0,*,mode='warm',contexts=1,allow_full_constants=False,
            corr_serial_bfs=0,mont_factored=0):
    need(type(contexts) is int and contexts in (1,2),'S4_CONTEXTS1_2')
    if contexts==1:
        return parent.prepare(n,p,field,mode=mode,contexts=1,allow_full_constants=allow_full_constants,
                              corr_serial_bfs=corr_serial_bfs,mont_factored=mont_factored)
    need(mode in ('warm','warm_signed'),'S4_CONTEXT_WARM_ONLY')
    need(hashlib.sha256((ROOT/PROTOCOL).read_bytes()).hexdigest().startswith(PROTOCOL_PIN),
         'S4_CONTEXT_PROTOCOL_DRIFT')
    b=parent.prepare(n,p,field,mode=mode,contexts=1,allow_full_constants=allow_full_constants,
        corr_serial_bfs=corr_serial_bfs,comm_stage_shared_mlab=1,mont_factored=mont_factored)
    files=b['files'];oldtop=b['top'];s=files.pop(oldtop+'.sv');top=oldtop+'_contexts2_v1'
    s=once(s,'module '+oldtop+' #','module '+top+' #')
    s=once(s,'CONTEXTS=1','CONTEXTS=2')
    s=once(s,'CONTEXTS!=1','CONTEXTS!=2')
    s=once(s,'input logic clk,rst_n,in_slot_valid,frame_start,context_enabled,',
        'input logic clk,rst_n,in_slot_valid,frame_start,context_in,correction_context,\n input logic [1:0] context_enabled,')
    s=once(s,'input logic [7:0] generation_in,live_generation,',
        'input logic [7:0] generation_in,input logic [15:0] live_generation,')
    s=once(s,'output logic [1:0] owner_count,output logic frame_accept,correction_accept,',
        'output logic [2:0] owner_count,output logic frame_accept,correction_accept,\n output logic out_context,commit_context,\n output logic [1:0] correction_bank,pointwise_bank,sink_bank,')
    s=once(s,'logic [7:0] active_generation;','logic [7:0] active_generation;logic active_context;')
    s=once(s,'logic [23:0] high_owner,small_first_owner,seed_owner;',
        'logic [26:0] high_owner,small_first_owner,seed_owner;')
    s=once(s,'logic [15:0] table_epoch[0:1];logic [7:0] table_generation[0:1];',
        'logic [15:0] table_epoch[0:3];logic [7:0] table_generation[0:3];logic table_context[0:3];')
    s=once(s,'logic [1:0] tables_ready;','logic [3:0] tables_ready;')
    s=once(s,'A_table[0:1][0:LANES-1],B_table[0:1][0:LANES-1]',
        'A_table[0:3][0:LANES-1],B_table[0:3][0:LANES-1]')
    s=once(s,'wire [7:0] digit_generation=frame_start ? generation_in : active_generation;',
        'wire [24:0] digit_generation=frame_start ? {context_in,epoch_in,generation_in} : {active_context,active_epoch,active_generation};')
    s=once(s,'wire [23:0] boundary_owner=accepted_correction ? {correction_epoch,correction_generation} : high_owner;',
        'wire [26:0] boundary_owner=accepted_correction ? {correction_bank,correction_context,correction_epoch,correction_generation} : high_owner;')
    s=s.replace('[ROW_W+8:0]','[ROW_W+25:0]').replace('.PAYLOAD_W(ROW_W+9)', '.PAYLOAD_W(ROW_W+26)')
    s=s.replace('[ROW_W+8:ROW_W+1]','[ROW_W+25:ROW_W+1]')
    s=s.replace('logic [23:0] boundary_tag','logic [26:0] boundary_tag')
    s=s.replace('.PAYLOAD_W(24)','.PAYLOAD_W(27)').replace('.GEN_W(24)','.GEN_W(27)')
    s=s.replace('wire [23:0] small_twist_owner,small_owner;','wire [26:0] small_twist_owner,small_owner;')
    s=s.replace('wire [23:0] term_owner,term_cache_owner;','wire [26:0] term_owner,term_cache_owner;')
    s=s.replace('wire [7:0] fwd_generation,addA_generation,addB_generation,square_generation,inv_generation;',
        'wire [24:0] fwd_generation,addA_generation,addB_generation,square_generation,inv_generation;')
    s=s.replace('logic addA_bank;','logic [1:0] addA_bank;')
    s=once(s,'(generation_in!=active_generation || epoch_in!=active_epoch)',
        '(context_in!=active_context || generation_in!=active_generation || epoch_in!=active_epoch)')
    s=s.replace('protocol_pw_epoch[0]','pointwise_bank').replace('small_owner[8]','small_owner[26:25]')
    s=s.replace('seed_owner[8]','seed_owner[26:25]').replace('term_cache_owner[8]','term_cache_owner[26:25]')
    # Main arithmetic transports full25 owners, correction arithmetic full27.
    s=s.replace('genefer_stream27_add_param_v1 #(.LANES(LANES),',
                'genefer_stream27_add_param_v1 #(.GEN_W(25),.LANES(LANES),')
    s=once(s,'.pointwise_owner({protocol_pw_epoch,fwd_generation}),',
        '.pointwise_owner({pointwise_bank,fwd_generation}),')
    s=once(s,'term_owner=={table_epoch[addA_bank],addA_generation};',
        'term_owner=={addA_bank,table_context[addA_bank],table_epoch[addA_bank],addA_generation[7:0]};')
    s=once(s,'assign generation_out=inv_generation;assign out_epoch=protocol_sink_epoch;',
        'assign generation_out=inv_generation[7:0];assign out_context=inv_generation[24];assign out_epoch=inv_generation[23:8];')
    s=once(s,'table_generation[pointwise_bank]!=fwd_generation)',
        'table_generation[pointwise_bank]!=fwd_generation[7:0] || table_context[pointwise_bank]!=fwd_generation[24])')
    s=once(s,'genefer_stream27_epoch_protocol_v5 #(.ROWS(ROWS),',
        'genefer_stream27_epoch_protocol_contexts_v1 #(.CONTEXTS(2),.BANKS(4),.ROWS(ROWS),')
    s=once(s,'.frame_begin(raw_begin),.frame_epoch(epoch_in),',
        '.frame_begin(raw_begin),.frame_context(context_in),.frame_epoch(epoch_in),')
    s=once(s,'.correction_valid,.correction_epoch,.correction_generation,',
        '.correction_valid,.correction_context,.correction_epoch,.correction_generation,')
    s=once(s,'.cache_ready(term_cache_ready),.cache_epoch(',
        '.cache_ready(term_cache_ready),.cache_context(term_cache_owner[24]),.cache_epoch(')
    s=once(s,'.pointwise_slot(fwd_slot),.pointwise_frame_start(fwd_start),.pointwise_generation(fwd_generation),',
        '.pointwise_slot(fwd_slot),.pointwise_frame_start(fwd_start),.pointwise_context(fwd_generation[24]),\n  .pointwise_epoch_in(fwd_generation[23:8]),.pointwise_generation(fwd_generation[7:0]),')
    s=once(s,'.sink_slot(out_slot_valid),.sink_frame_start(out_frame_start),.sink_generation(generation_out),',
        '.sink_slot(out_slot_valid),.sink_frame_start(out_frame_start),.sink_context(out_context),.sink_epoch_in(out_epoch),.sink_generation(generation_out),')
    s=once(s,'.pointwise_row(protocol_pw_row),.sink_row(protocol_sink_row),.owner_count,',
        '.pointwise_row(protocol_pw_row),.sink_row(protocol_sink_row),.correction_bank,.pointwise_bank,.sink_bank,.owner_count,')
    s=once(s,'active_base<=base_in;active_generation<=generation_in;active_epoch<=epoch_in;',
        'active_base<=base_in;active_generation<=generation_in;active_epoch<=epoch_in;active_context<=context_in;')
    s=once(s,'tables_ready[epoch_in[0]]<=0;','')
    s=once(s,'high_owner<={correction_epoch,correction_generation};',
        'high_owner<={correction_bank,correction_context,correction_epoch,correction_generation};tables_ready[correction_bank]<=0;')
    s=once(s,'table_generation[small_owner[26:25]]<=small_owner[7:0];',
        'table_generation[small_owner[26:25]]<=small_owner[7:0];table_context[small_owner[26:25]]<=small_owner[24];')
    s=once(s,'table_generation[term_cache_owner[26:25]]==term_cache_owner[7:0])',
        'table_generation[term_cache_owner[26:25]]==term_cache_owner[7:0] && table_context[term_cache_owner[26:25]]==term_cache_owner[24])')
    s=once(s,'commit_generation<=generation_out;commit_epoch<=protocol_sink_epoch;',
        'commit_generation<=generation_out;commit_epoch<=out_epoch;commit_context<=out_context;')
    # Clone only the term-state bank/tag storage and square metadata width.
    termname=next(name[:-3] for name in files if name.startswith('genefer_stream27_term_context_param_'))
    newterm,term=term_source(termname,files.pop(termname+'.sv'));files[newterm+'.sv']=term
    s=s.replace(termname+' #',newterm+' #')
    square=next(name[:-3] for name in files if name.startswith('genefer_stream27_square_'))
    newsquare=square+'_contexts_v1';squaretext=files.pop(square+'.sv')
    squaretext=once(squaretext,'module '+square+' (','module '+newsquare+' #(parameter int GEN_W=8) (')
    # P8 lane_valid is also [7:0]: only generation metadata widens.
    squaretext=squaretext.replace('[7:0] generation','[GEN_W-1:0] generation')
    files[newsquare+'.sv']=squaretext
    s=once(s,square+' pointwise_square (',newsquare+' #(.GEN_W(25)) pointwise_square (')
    for direction,signal in (('ct','fwd_generation'),('gs','inv_generation')):
        module=next(name[:-3] for name in files if name.startswith('genefer_stream28_merged_'+direction+'_'))
        instance='forward_transform' if direction=='ct' else 'inverse_transform'
        s=once(s,module+' '+instance+' (',module+' #(.GEN_W(25)) '+instance+' (')
        begin=s.index(module+' #(.GEN_W(25)) '+instance+' (');end=s.index(');',begin)
        part=s[begin:end]
        part=once(part,'.context_enabled,',f'.context_enabled(context_enabled[{signal}[24]]),')
        part=once(part,'.live_generation,',f'.live_generation({{{signal}[24:8],({signal}[24] ? live_generation[15:8] : live_generation[7:0])}}),')
        s=s[:begin]+part+s[end:]
    files[top+'.sv']=s;files[PROTOCOL.rsplit('/',1)[1]]=(ROOT/PROTOCOL).read_text()
    b['top']=top;b['parameters']=dict(b['parameters'],CONTEXTS=2)
    b['geometry']=dict(b['geometry'],contexts=2,lease_banks=4,main_owner_bits=25,term_owner_bits=27)
    b['source_dependencies']=list(dict.fromkeys(b['source_dependencies']+[SELF,PROTOCOL]))
    b['source_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in b['source_dependencies']}
    b['rtl_sources']=[name for name in files if name.endswith('.sv')]
    b['generated_sha256']={name:hashlib.sha256(text.encode()).hexdigest() for name,text in files.items()}
    b['scope']='Real shared two-context field and four lookup-selected correction/term banks; carried full frame owner. Source only until native. No CRT/carry feedback/host/finalization/wholeclock/interleave promotion inference.'
    return b

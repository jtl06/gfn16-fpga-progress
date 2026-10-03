"""Isolated, zero-cycle term data-selector/quarantine decoupling.

The new multiplier sideband ignores only external quarantine, never its own
error or any lane-valid bit. ONLY current_term payload selection consumes it.
Qualified bypass remains the owner/calendar/consumer/state/cache authority.
When the term producer is live, both selector predicates are identical; when
stopped, neither term payload nor a new product is sampled. No root/calendar,
recurrence depth, II, public fault timing or accepted-origin tail changes.
"""
import copy
import hashlib
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_term_select_bind.py'
LEAF='rtl/kernel/genefer_stream27_mul_select_token_v1.sv'
MULT_PARENT='genefer_stream27_mul_param_v1'
MULT_NEW='genefer_stream27_mul_select_token_v1'
DATA_DECL='    wire bypass_data=data_select_slot && product_owner==pointwise_owner && product_row==pointwise_row;\n'
TERM_ASSERT='''    // synthesis translate_off
    always @(negedge clk)if(rst_n && !stop && bypass_data!=bypass)
        $fatal(1,"TERM_SELECT_LIVE_BYPASS_EQUIVALENCE");
    // synthesis translate_on
'''
MUL_ASSERT='''    always @(negedge clk)if(rst_n && !quarantine && data_select_slot!=out_slot_valid)
        $fatal(1,"TERM_SELECT_LIVE_TOKEN_EQUIVALENCE");
'''


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def once(text,old,new):
    need(text.count(old)==1,'TERM_SELECT_SOURCE_ANCHOR '+old[:100])
    return text.replace(old,new,1)


def reverse_leaf(text):
    """Restore exact parent mul definition; parent add module is untouched."""
    text=text[text.index('module '+MULT_NEW+' #'):]
    text=once(text,'module '+MULT_NEW+' #','module '+MULT_PARENT+' #')
    text=once(text,'    output logic [LANES*27-1:0] result,\n    output logic data_select_slot\n',
                   '    output logic [LANES*27-1:0] result\n')
    text=once(text,'    assign data_select_slot=slot_pipe[3] && (&lane_valid) && !out_error;\n','')
    return once(text,MUL_ASSERT,'')


def select_term(name,parent):
    new=name+'_select_token_v1'
    text=once(parent,'module '+name+' #','module '+new+' #')
    text=once(text,'    wire product_slot,product_error,product_pending;\n',
                   '    wire product_slot,product_error,product_pending,data_select_slot;\n')
    anchor='    wire bypass=product_slot && product_owner==pointwise_owner && product_row==pointwise_row;\n'
    text=once(text,anchor,anchor+DATA_DECL)
    text=once(text,"        if(bypass)begin current_term=product_data;consumer_missing=1'b0;end\n",
                   "        if(bypass_data)current_term=product_data;\n        if(bypass)consumer_missing=1'b0;\n")
    text=once(text,MULT_PARENT+' #(.LANES(LANES),.P(P),.Q(Q),.GEN_W(TAG_W)) products (',
                   MULT_NEW+' #(.LANES(LANES),.P(P),.Q(Q),.GEN_W(TAG_W)) products (')
    text=once(text,'.fault_pending(product_pending),.generation_out(product_tag),.result(product_data));',
                   '.fault_pending(product_pending),.generation_out(product_tag),.result(product_data),\n        .data_select_slot(data_select_slot));')
    text=once(text,'endmodule\n',TERM_ASSERT+'endmodule\n')
    need(reverse_term(new,text)==(name,parent),'TERM_SELECT_EXACT_REVERSE_TERM')
    return new,text


def reverse_term(name,text):
    need(name.endswith('_select_token_v1'),'TERM_SELECT_REVERSE_NAME')
    old=name[:-len('_select_token_v1')]
    text=once(text,'module '+name+' #','module '+old+' #')
    text=once(text,'    wire product_slot,product_error,product_pending,data_select_slot;\n',
                   '    wire product_slot,product_error,product_pending;\n')
    text=once(text,DATA_DECL,'')
    text=once(text,"        if(bypass_data)current_term=product_data;\n        if(bypass)consumer_missing=1'b0;\n",
                   "        if(bypass)begin current_term=product_data;consumer_missing=1'b0;end\n")
    text=once(text,MULT_NEW+' #(.LANES(LANES),.P(P),.Q(Q),.GEN_W(TAG_W)) products (',
                   MULT_PARENT+' #(.LANES(LANES),.P(P),.Q(Q),.GEN_W(TAG_W)) products (')
    text=once(text,'.fault_pending(product_pending),.generation_out(product_tag),.result(product_data),\n        .data_select_slot(data_select_slot));',
                   '.fault_pending(product_pending),.generation_out(product_tag),.result(product_data));')
    return old,once(text,TERM_ASSERT,'')


def reverse_root(text,parent_top,new_top,parent_term,new_term,contexts):
    text=once(text,'module '+new_top+' #','module '+parent_top+' #')
    text=once(text,',CONTEXTS='+str(contexts)+',TERM_SELECT_TOKEN=1',',CONTEXTS='+str(contexts))
    text=once(text,' || TERM_SELECT_TOKEN!=1','')
    return once(text,new_term+' #(',parent_term+' #(')


def bind(bundle,*,enabled=1):
    need(type(enabled) is int and enabled in (0,1),'TERM_SELECT_FLAG')
    result=copy.deepcopy(bundle)
    if enabled==0:return result
    need(bundle['mode'] in ('warm','warm_signed') and bundle['parameters']['P'] in (8,16),
         'TERM_SELECT_WARM_P8_P16')
    need('TERM_SELECT_TOKEN' not in bundle['parameters'],'TERM_SELECT_ALREADY_BOUND')
    oldtop=bundle['top'];parent=bundle['files'][oldtop+'.sv'];contexts=bundle['parameters']['CONTEXTS']
    matches=re.findall(r' (genefer_stream27_term_context_param_v[12](?:_contexts_v1)?) #\(',parent)
    need(len(matches)==1,'TERM_SELECT_EXACT_TERM_INSTANCE')
    oldterm=matches[0];term=bundle['files'][oldterm+'.sv'];newterm,newtext=select_term(oldterm,term)
    leaf=(ROOT/LEAF).read_text();arith=bundle['files']['genefer_stream27_row_arithmetic_param_v1.sv']
    start=arith.index('module '+MULT_PARENT+' #');end=arith.index('endmodule\n',start)+len('endmodule\n')
    need(reverse_leaf(leaf)==arith[start:end],'TERM_SELECT_EXACT_MULT_PARENT')
    top=oldtop+'_term_select_token_v1'
    text=once(parent,'module '+oldtop+' #','module '+top+' #')
    text=once(text,',CONTEXTS='+str(contexts),',CONTEXTS='+str(contexts)+',TERM_SELECT_TOKEN=1')
    text=once(text,'CONTEXTS!='+str(contexts),'CONTEXTS!='+str(contexts)+' || TERM_SELECT_TOKEN!=1')
    text=once(text,oldterm+' #(',newterm+' #(')
    need(reverse_root(text,oldtop,top,oldterm,newterm,contexts)==parent,'TERM_SELECT_EXACT_REVERSE_ROOT')
    result['files'].pop(oldtop+'.sv');result['files'].pop(oldterm+'.sv')
    result['files'].update({top+'.sv':text,newterm+'.sv':newtext,Path(LEAF).name:leaf})
    result['top']=top;result['parameters']=dict(result['parameters'],TERM_SELECT_TOKEN=1)
    result['source_dependencies']=list(dict.fromkeys(result['source_dependencies']+[SELF,LEAF]))
    result['source_sha256']={name:sha((ROOT/name).read_bytes()) for name in result['source_dependencies']}
    result['rtl_sources']=[name for name in result['files'] if name.endswith('.sv')]
    result['generated_sha256']={name:sha(value.encode()) for name,value in result['files'].items()}
    result['term_select']=dict(schema='s4-term-data-select-token-v1',parent_top=oldtop,parent_term=oldterm,
        parent_root_sha256=sha(parent.encode()),parent_term_sha256=sha(term.encode()),
        new_top=top,new_term=newterm,selector='slot_pipe[3] && (&lane_valid) && !out_error',
        selector_is_authority=False,reverse_to_parent_exact=True,qualified_controls_unchanged=True,
        geometry_unchanged=True,product_capture_edges=4,initiation_interval=1,
        physical_gain_measured=False,whole_clock_claim=False,promotion_allowed=False)
    result['scope']='Isolated term payload-only selector decoupling, zero-cycle; native and physical benefit require separate gates.'
    return result

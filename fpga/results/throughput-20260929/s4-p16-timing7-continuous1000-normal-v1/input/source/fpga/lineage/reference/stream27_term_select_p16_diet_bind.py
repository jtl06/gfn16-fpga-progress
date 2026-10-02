"""Exact copied P16 diet seam for the native-qualified term data selector.

Accepts ordinary factored field IDs or the private whole-diet IDs. Only the
qualified selector leaf's identifiers change: the canonical multiplier name
becomes the donor's actual factored multiplier. No old Montgomery definition
is restored. Every transformed term/mul/root reverses to actual donor bytes.
"""
import copy
import re
from pathlib import Path
from . import stream27_term_select_bind as frozen

ROOT=frozen.ROOT
SELF='reference/stream27_term_select_p16_diet_bind.py'
FACTORED='genefer_stream27_montgomery_factored_v1'
need,sha,once=frozen.need,frozen.sha,frozen.once


def identifier(text,old,new):return re.sub(r'\b'+re.escape(old)+r'\b',new,text)


def reverse_term(newname,text,oldmul,newmul):
    normalized=identifier(text,newmul,frozen.MULT_NEW)
    oldname,restored=frozen.reverse_term(newname,normalized)
    return oldname,identifier(restored,frozen.MULT_PARENT,oldmul)


def bind(bundle,*,enabled=1):
    need(type(enabled) is int and enabled in (0,1),'P16_DIET_TERM_SELECT_FLAG')
    result=copy.deepcopy(bundle)
    if enabled==0:return result
    need(bundle['mode'] in ('warm','warm_signed') and bundle['parameters']['P']==16
         and bundle['parameters']['CONTEXTS']==1 and bundle['parameters'].get('MONT_FACTORED')==1,
         'P16_DIET_TERM_SELECT_FACTORED_C1')
    need('TERM_SELECT_TOKEN' not in bundle['parameters'],'P16_DIET_TERM_SELECT_ALREADY_BOUND')
    oldtop=bundle['top'];parent=bundle['files'][oldtop+'.sv']
    terms=re.findall(r' (genefer_stream27_term_context_param_v[12](?:_p16_diet_v1)?) #\(',parent)
    need(len(terms)==1,'P16_DIET_TERM_SELECT_ACTUAL_TERM_INSTANCE')
    oldterm=terms[0];term=bundle['files'][oldterm+'.sv']
    calls=re.findall(r' (genefer_stream27_mul_param_v1(?:_p16_diet_v1)?) #\(.LANES\(LANES\),.P\(P\),.Q\(Q\),.GEN_W\(TAG_W\)\) products \(',term)
    need(len(calls)==1,'P16_DIET_TERM_SELECT_ACTUAL_MULT_INSTANCE')
    oldmul=calls[0];newmul='genefer_stream27_mul_select_token_v1_p16_diet_v1'
    candidates=[text for text in bundle['files'].values() if 'module '+oldmul+' #' in text]
    need(len(candidates)==1,'P16_DIET_TERM_SELECT_ACTUAL_MULT_DEFINITION')
    arith=candidates[0];start=arith.index('module '+oldmul+' #');end=arith.index('endmodule\n',start)+len('endmodule\n')
    mul=arith[start:end];need(FACTORED+' #(' in mul,'P16_DIET_TERM_SELECT_NO_OLD_MONT')
    leaf=(ROOT/frozen.LEAF).read_text()
    leaf=identifier(identifier(leaf,frozen.MULT_NEW,newmul),'genefer_montgomery_mul27_sparse_pipe',FACTORED)
    reversed_leaf=frozen.reverse_leaf(identifier(identifier(leaf,newmul,frozen.MULT_NEW),FACTORED,'genefer_montgomery_mul27_sparse_pipe'))
    reversed_leaf=identifier(identifier(reversed_leaf,frozen.MULT_PARENT,oldmul),'genefer_montgomery_mul27_sparse_pipe',FACTORED)
    need(reversed_leaf==mul,'P16_DIET_TERM_SELECT_EXACT_FACTORED_MULT_REVERSE')
    newterm,selected=frozen.select_term(oldterm,identifier(term,oldmul,frozen.MULT_PARENT))
    selected=identifier(selected,frozen.MULT_NEW,newmul)
    need(reverse_term(newterm,selected,oldmul,newmul)==(oldterm,term),'P16_DIET_TERM_SELECT_EXACT_TERM_REVERSE')
    top=oldtop+'_term_select_token_v1'
    text=once(parent,'module '+oldtop+' #','module '+top+' #')
    text=once(text,',CONTEXTS=1',',CONTEXTS=1,TERM_SELECT_TOKEN=1')
    text=once(text,'CONTEXTS!=1','CONTEXTS!=1 || TERM_SELECT_TOKEN!=1')
    text=once(text,oldterm+' #(',newterm+' #(')
    need(frozen.reverse_root(text,oldtop,top,oldterm,newterm,1)==parent,'P16_DIET_TERM_SELECT_EXACT_ROOT_REVERSE')
    result['files'].pop(oldtop+'.sv');result['files'].pop(oldterm+'.sv')
    result['files'].update({top+'.sv':text,newterm+'.sv':selected,newmul+'.sv':leaf})
    result['top']=top;result['parameters']=dict(result['parameters'],TERM_SELECT_TOKEN=1)
    result['source_dependencies']=list(dict.fromkeys(result['source_dependencies']+[SELF,frozen.SELF,frozen.LEAF]))
    result['source_sha256']={name:sha((ROOT/name).read_bytes()) for name in result['source_dependencies']}
    result['rtl_sources']=[name for name in result['files'] if name.endswith('.sv')]
    result['generated_sha256']={name:sha(value.encode()) for name,value in result['files'].items()}
    result['term_select']=dict(schema='s4-p16-diet-term-data-select-token-v1',parent_top=oldtop,parent_term=oldterm,
        parent_mul=oldmul,new_top=top,new_term=newterm,new_mul=newmul,actual_multiplier=FACTORED,
        parent_root_sha256=sha(parent.encode()),parent_term_sha256=sha(term.encode()),parent_mul_sha256=sha(mul.encode()),
        qualified_leaf_sha256=sha((ROOT/frozen.LEAF).read_bytes()),
        identifier_only_leaf_substitution=True,reverse_to_actual_parent_exact=True,
        geometry_unchanged=True,product_capture_edges=4,initiation_interval=1,
        public_fault_and_qualified_controls_unchanged=True,physical_gain_measured=False,whole_clock_claim=False,promotion_allowed=False)
    result['scope']='Private P16 diet payload-only selector seam; actual factored multiplier retained, own composed gates required.'
    return result

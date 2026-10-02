"""Private explicit MLAB term-payload proposal on exact storage2 captures.

Default off is byte exact. Only reset-free numeric term payload moves: A/B,
full27 owner/row/valid control, eligible write and E4 bypass remain literal.
No shared-generator edits, inferred mapping credit or added read latency.
"""
import copy
import hashlib
from pathlib import Path
from . import stream27_context_storage_banks_native as captured

ROOT=captured.ROOT
SELF='reference/stream27_context_term_mlab_bind.py'
RAM='genefer_stream27_term_payload_mlab_v1'
TERM='genefer_stream27_term_context_param_v1_contexts_v1_storage2_v1'
NEW=TERM+'_mlab_payload_v1'


def sha(text):return hashlib.sha256(text.encode()).hexdigest()


def term(text):
    # Verify the precise parent emitted by frozen storage2, not a generic ABI.
    _,_,bundle=captured.capture('aw8')
    expected=captured.binder.bind(bundle,enabled=1)['files'][TERM+'.sv']
    captured.need(text==expected,'MLAB_TERM_FROZEN_FF_PARENT')
    once=captured.binder.parent.once
    text=once(text,'module '+TERM+' #','module '+NEW+' #')
    text=once(text,'    logic [LANES*27-1:0] context_data[0:1][0:3];',
        '    wire [LANES*27-1:0] payload_read;')
    text=once(text,'        current_term=context_data[pw_bank][pw_context];',
        '        current_term=payload_read;')
    text=once(text,'                    context_data[prod_bank][product_row[1:0]]<=product_data;\n','')
    text=once(text,'    // Selection is independent of resulting fault/accept authority.',
        '''    // Identical eligible numeric write; no reset or pending-fault gate.
    wire payload_write=!stop && product_slot && bank_owner[prod_bank]==product_owner;
    for(genvar lane=0;lane<LANES;lane=lane+1)begin : payload_lane
        genefer_stream27_term_payload_mlab_v1 memory (
            .clk,.write_enable(payload_write),
            .write_address({prod_bank,product_row[1:0]}),.read_address({pw_bank,pw_context}),
            .write_data(product_data[lane*27+:27]),.read_data(payload_read[lane*27+:27]));
    end
    // Selection is independent of resulting fault/accept authority.''')
    return text


def bind(bundle,*,enabled=0):
    captured.need(type(enabled) is int and enabled in (0,1),'MLAB_BOOL_FLAG')
    result=copy.deepcopy(bundle)
    if not enabled:return result
    geometry=result['geometry']
    captured.need(geometry.get('n') in (256,65536) and geometry.get('p')==16 and
        geometry.get('contexts')==2 and result.get('storage_contract',{}).get('clean_parent'), 'MLAB_CLOSED_STORAGE2_ONLY')
    stage='aw8' if geometry['n']==256 else 'full'
    _,_,parent=captured.capture(stage)
    exact=captured.binder.bind(parent,enabled=1)
    captured.need(result['files']==exact['files'] and result['top']==exact['top'],'MLAB_EXACT_CAPTURE_MAP')
    files=result['files'];files[NEW+'.sv']=term(files.pop(TERM+'.sv'))
    renamed={}
    for filename in list(files):
        if filename.startswith('genefer_stream27_shared_warm_') and filename.endswith('_storage2_v1.sv'):
            old=filename[:-3];new=old+'_term_mlab_v1';renamed[old]=new
            text=files.pop(filename)
            text=captured.binder.parent.once(text,'module '+old+' #','module '+new+' #')
            files[new+'.sv']=captured.binder.parent.once(text,TERM+' #',NEW+' #')
    captured.need(len(renamed)==3,'MLAB_THREE_FIELD_IDENTIFIERS')
    for filename,text in list(files.items()):
        for old,new in renamed.items():text=captured.binder.parent.re_identifier(text,old,new)
        files[filename]=text
    old=result['top'];new=old+'_term_mlab_v1'
    files[new+'.sv']=captured.binder.parent.once(files.pop(old+'.sv'),'module '+old+' #','module '+new+' #')
    files[RAM+'.sv']=(ROOT/'rtl/kernel'/ (RAM+'.sv')).read_text()
    result.update(top=new,rtl_sources=list(files),generated_sha256={name:sha(text) for name,text in files.items()})
    result['term_mlab']=dict(enabled=1,parent_top=old,physical_rows_per_lane=8,word_bits=27,logical_owners=4,
        physical_contexts=2,reset_free_payload=True,extra_read_registers=0,no_rw_check=False,
        eligible_write='!stop && product_slot && bank_owner[prod_bank]==product_owner',
        default_adopted=False,measured_mapping=None,native_qualified=False,
        scope='Private source proposal; FF parent is actual storage2, no area/clock/whole qualification inherited')
    return result

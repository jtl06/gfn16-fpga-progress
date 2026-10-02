"""Additive P8 registered-fault warm field, AW8..16; source draft only.

Legal arithmetic/calendar is identical to full_v1. A current fault may advance
one occupied edge, then registered stop applies. Terminal owner/live checks are
immediate intrinsic qualification, not fault fanout. No frozen source edits.
"""
from pathlib import Path
import hashlib
import re

from .stream27_field_square_warm_full_v1_compile import prepare as parent_bundle
from .stream27_field_square_warm_v3_compile import replace_once


def registered_arithmetic(source):
    """GEN_W wrapper derivative; pending flags are diagnostics, not enables."""
    source=source.replace('genefer_stream27_mul8_v3','genefer_stream27_mul8_v4_registered')
    source=source.replace('genefer_stream27_add8_v3','genefer_stream27_add8_v4_registered')
    source=source.replace('!quarantine && !fault_pending','!quarantine && !out_error')
    if '&& !fault_pending' in source:raise ValueError('REGISTERED_ARITH_PENDING_ENABLE')
    return '// r17 derivative: one origin edge may advance, next edge stops.\n'+source


def registered_transform(source):
    match=re.search(r'module (genefer_stream27_(?:dif|dit)_aw\d+_p8_f0)',source)
    if not match:raise ValueError('REGISTERED_TRANSFORM_MODULE')
    old=match.group(1);new=old+'_registered_v1'
    source=replace_once(source,'module '+old+' #','module '+new+' #')
    source=source.replace('genefer_stream27_mdc_commutator_slots_v2',
                          'genefer_stream27_mdc_commutator_slots_v3_registered')
    if source.count('wire accept=row_slot && !stop && !local_fault && !cadence_bad;')<1:
        raise ValueError('REGISTERED_TRANSFORM_ACCEPT')
    source=source.replace('wire accept=row_slot && !stop && !local_fault && !cadence_bad;',
                          'wire accept=row_slot && !stop && !local_fault;')
    source=source.replace('// Recheck current generation and fault_pending at the external commit edge.',
        '// Recheck current generation/owner at commit; pending faults register before quarantine.')
    return old,new,source


def registered_term_roots(source):
    old=re.search(r'module (\w+) \(',source).group(1);new=old.replace('_v1','_v2')
    source=replace_once(source,'module '+old+' (','module '+new+' (')
    source=replace_once(source," wire [1:0] following_context=seed_row+2'd1;",
        " wire [1:0] following_context=seed_row+2'd1;\n"
        " wire [4:0] read_address=seed_slot ? {3'b0,following_context} : following_address;")
    source=replace_once(source,"   if(rst_n && seed_slot)prefetched<=roots[{3'b0,following_context}];\n"
        '   else if(rst_n && pw_slot)prefetched<=roots[following_address];',
        '   if(rst_n && (seed_slot || pw_slot))prefetched<=roots[read_address];')
    return old,new,source


def prepare(n=65536,*,allow_full_constants=False):
    parent=parent_bundle(n,allow_full_constants=allow_full_constants)
    old_top=parent['top'];top=old_top[:-2]+'v2_registered'
    source=parent['files'][old_top+'.sv'];files={};renames={}
    for name,text in parent['files'].items():
        if name==old_top+'.sv':continue
        if name.startswith(('genefer_stream27_dif_aw','genefer_stream27_dit_aw')):
            old,new,text=registered_transform(text);renames[old]=new;files[new+'.sv']=text
        elif name=='genefer_stream27_row_arithmetic_v3.sv':
            files['genefer_stream27_row_arithmetic_v4_registered.sv']=registered_arithmetic(text)
        elif name.startswith('genefer_stream27_term_roots_'):
            old,new,text=registered_term_roots(text);renames[old]=new;files[new+'.sv']=text
        else:files[name]=text
    source=replace_once(source,'module '+old_top+' (',
        'module '+top+' #(parameter int unsigned CONTEXTS=1) (')
    for old,new in renames.items():source=source.replace(old,new)
    source=source.replace('genefer_stream27_epoch_protocol_v4','genefer_stream27_epoch_protocol_v5')
    source=source.replace('genefer_stream27_term_context_v1','genefer_stream27_term_context_v2')
    for version in ('v2','v3'):
        source=source.replace('genefer_stream27_mul8_'+version,'genefer_stream27_mul8_v4_registered')
        source=source.replace('genefer_stream27_add8_'+version,'genefer_stream27_add8_v4_registered')
    # The only global work authority is state from the preceding edge. Never
    # OR current child diagnostics directly into a work/row-counter cone.
    source=replace_once(source,'logic busy,quarantine,controller_error;',
                        'logic quarantine,controller_error;')
    source=replace_once(source,'logic [15:0] active_epoch,protocol_pw_epoch,protocol_sink_epoch;',
                        'logic [15:0] protocol_pw_epoch,protocol_sink_epoch;')
    source=replace_once(source,'logic epoch_error,epoch_pending,epoch_correction_accept,protocol_pw_accept,protocol_commit;',
        'logic epoch_error,epoch_pending,epoch_frame_accept,epoch_correction_accept,protocol_commit;')
    source=re.sub(r'  logic \[\d+:0\] protocol_pw_row,protocol_sink_row;\n','',source,count=1)
    source=replace_once(source,'wire raw_frame_begin=rst_n && in_slot_valid && frame_start && !stop && !digit_admission_bad;',
                        'wire raw_frame_begin=rst_n && in_slot_valid && frame_start && !stop;')
    source=replace_once(source,'wire accepted_correction=rst_n && correction_valid && epoch_correction_accept && !stop && !admission_bad;',
                        'wire accepted_correction=rst_n && correction_valid && epoch_correction_accept && !stop;')
    source=replace_once(source,'wire accepted=rst_n && in_slot_valid && !stop && !admission_bad && !epoch_pending;',
                        'wire accepted=rst_n && in_slot_valid && !stop && (!frame_start || epoch_frame_accept);')
    source=replace_once(source,'wire boundary_slot=(accepted_correction || c1_pending) && !stop && !admission_bad;',
                        'wire boundary_slot=(accepted_correction || c1_pending) && !stop;')
    source=replace_once(source,'assign out_error=controller_error || (|child_error) || epoch_error;',
                        'assign out_error=controller_error;')
    source=replace_once(source,'logic term_slot,term_start,square_slot,square_start;',
                        'logic term_slot,square_slot,square_start;')
    source=source.replace('small_slot,small_start;','small_slot;').replace('.out_frame_start(small_start)',
                        '.out_frame_start()').replace('.term_slot,.term_start,','.term_slot,.term_start(),')
    source=replace_once(source,'else if(fwd_slot && !stop && !join_bad)begin',
                        'else if(fwd_slot && !stop)begin')
    source=replace_once(source,'.in_slot_valid(fwd_slot && !join_bad)',
                        '.in_slot_valid(fwd_slot)')
    # An arithmetic join is itself an ownership-qualified interface. Reject a
    # misowned term immediately, without fanning a general fault into enables.
    source=replace_once(source,'  genefer_stream27_add8_v4_registered add_B (',
        '  wire term_join_valid=term_slot && term_output_row==addA_row &&\n'
        '      term_generation=={table_epoch[addA_bank],addA_generation};\n'
        '  genefer_stream27_add8_v4_registered add_B (')
    source=replace_once(source,'.in_slot_valid(addA_slot),.frame_start(addA_start)',
                        '.in_slot_valid(addA_slot && term_join_valid),.frame_start(addA_start)')
    source=replace_once(source,'.context_enabled,.live_generation,.correction_accept(epoch_correction_accept),',
                        '.context_enabled,.live_generation,.frame_accept(epoch_frame_accept),.correction_accept(epoch_correction_accept),')
    source=replace_once(source,'.pointwise_accept(protocol_pw_accept),.commit_enable(protocol_commit),',
                        '.pointwise_accept(),.commit_enable(protocol_commit),')
    source=replace_once(source,'.pointwise_row(protocol_pw_row),.sink_row(protocol_sink_row),.owner_count,',
                        '.pointwise_row(),.sink_row(),.owner_count,')
    source=replace_once(source,'busy<=0;quarantine<=0;controller_error<=0;',
                        'quarantine<=0;controller_error<=0;')
    source=replace_once(source,'if(!stop && (admission_bad || join_bad || (|child_pending)))controller_error<=1;',
        'if(!stop && (admission_bad || join_bad || (|child_pending) || epoch_pending ||\n'
        '                    (|child_error) || epoch_error))controller_error<=1;')
    source=replace_once(source,'if(!stop && !fault_pending)begin','if(!stop)begin')
    source=replace_once(source,'busy<=1;active_base<=base_in;active_generation<=generation_in;active_epoch<=epoch_in;',
                        'active_base<=base_in;active_generation<=generation_in;')
    source=re.sub(r'          if\(sink_row==\d+\x27d\d+\)busy<=0;\n','',source,count=1)
    source=replace_once(source,'if(term_cache_ready)tables_ready[term_cache_owner[8]]<=1;',
        'if(term_cache_ready && table_epoch[term_cache_owner[8]]==term_cache_owner[23:8] &&\n'
        '           table_generation[term_cache_owner[8]]==term_cache_owner[7:0])tables_ready[term_cache_owner[8]]<=1;')
    # sink_row was only the old busy/done state, protocol now owns retirement.
    source=source.replace(',sink_row;', ';').replace(';sink_row<=0;',';')
    source=re.sub(r'          sink_row<=sink_row\+\d+\x27d1;\n','',source,count=1)
    source=source.replace('endmodule\n','''  // synthesis translate_off
  initial if(CONTEXTS!=1)$fatal(1,"FULL_WARM_CONTEXTS1_ONLY");
  // synthesis translate_on
endmodule
''')
    files[top+'.sv']=source
    added=['reference/stream27_field_square_warm_full_v2_compile.py',
           'reference/stream27_registered_fault_contract_v1.py',
           'rtl/kernel/genefer_stream27_epoch_protocol_v5.sv',
           'rtl/kernel/genefer_stream27_term_context_v2.sv',
           'rtl/kernel/genefer_stream27_mdc_commutator_slots_v3_registered.sv',
           'tests/test_stream27_field_square_warm_full_v2_compile.py',
           'tests/test_stream27_registered_fault_contract_v1.py']
    deps=list(dict.fromkeys(parent['source_dependencies']+added));root=Path(__file__).resolve().parents[1]
    old_rtl={'rtl/kernel/genefer_stream27_row_arithmetic_v2.sv',
             'rtl/kernel/genefer_stream27_mdc_commutator_slots_v2.sv',
             'rtl/kernel/genefer_stream27_epoch_protocol_v4.sv',
             'rtl/kernel/genefer_stream27_term_context_v1.sv'}
    rtl_sources=[p for p in parent['rtl_sources'] if p.startswith('rtl/') and p not in old_rtl]
    rtl_sources += [p for p in added if p.endswith('.sv')]+list(files)
    return dict(files=files,source_dependencies=deps,rtl_sources=rtl_sources,top=top,n=n,aw=parent['aw'],
        source_sha256={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in deps},
        generated_sha256={p:hashlib.sha256(s.encode()).hexdigest() for p,s in files.items()},
        geometry=parent['geometry'],term_calendar=parent['term_calendar'],
        registered_fault_policy='Origin edge may advance once; registered stop inhibits next edge; terminal live/owner validation immediate.',
        CONTEXTS_supported=[1],physical_epoch_owners=2,full_N_numeric_NTT_performed=False,
        arithmetic_source_complete=True,RTL_qualified=False,native_run_performed=False,
        limits=parent['limits']+['r17 source successor needs new independent fault calendar and warning-fatal native lint/pilots.',
            'A fault invalidates the partial image; no rollback. One correct old sink word may commit on the origin edge.',
            'Frame/correction accepts are transport leases, not successful-job/profile qualification.'])

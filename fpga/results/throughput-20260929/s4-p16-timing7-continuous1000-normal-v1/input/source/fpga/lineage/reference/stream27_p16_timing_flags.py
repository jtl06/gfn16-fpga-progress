"""P16 timing successor of the exact composed-diet whole candidate.

The fitted donor is immutable. This copied-bundle route retains CORR_SERIAL2,
shared temporal MLAB control and factored field reducers. It adds explicit
timing flags and their real edge calendars; native/resource/clock evidence is
not inherited from P8 or from isolated components. TERM_SELECT_TOKEN is a
payload-selection token only, never admission/cache/commit authority.
"""
import copy
import hashlib
from . import stream27_host_chain_diet_qualification as donor
from . import stream27_shared_field_flags as fields
from . import stream27_timing_flags as timing

ROOT=timing.ROOT
SELF='reference/stream27_p16_timing_flags.py'
DIET=dict(CORR_SERIAL_BFS=2,COMM_STAGE_SHARED_MLAB=1,MONT_FACTORED=1)


def check(bundle):
    fields.need(bundle['parameters']['P']==16 and bundle['parameters']['CONTEXTS']==1
        and all(bundle['parameters'].get(key)==value for key,value in DIET.items()),
        'S4_P16_TIMING_EXACT_DIET_DONOR')


def close(bundle):
    bundle['source_dependencies']=list(dict.fromkeys(bundle['source_dependencies']+[SELF]))
    bundle['source_sha256'][SELF]=hashlib.sha256((ROOT/SELF).read_bytes()).hexdigest()
    return bundle


def bind_field(bundle, *, boundary_inputreg=0,quarantine_replicas=0,final_gs_inputreg=0,term_select_token=0):
    check(bundle)
    for name,value in dict(BOUNDARY_INPUTREG=boundary_inputreg,QUARANTINE_REPLICAS=quarantine_replicas,
                          FINAL_GS_INPUTREG=final_gs_inputreg,TERM_SELECT_TOKEN=term_select_token).items():timing.flag(value,name)
    if not(boundary_inputreg or quarantine_replicas or final_gs_inputreg or term_select_token):return bundle
    result=timing.bind_field(bundle,boundary_inputreg=boundary_inputreg,
        quarantine_replicas=quarantine_replicas,final_gs_inputreg=final_gs_inputreg)
    if term_select_token:
        from . import stream27_term_select_p16_diet_bind as term
        result=term.bind(result)
    result['scope']='P16 composed-diet field timing source; own native/physical gates required, no inherited P8 clock.'
    return close(result)


def prepare_field(n=256,p=16,f=0,*,mode='warm',contexts=1,allow_full_constants=False,
                  boundary_inputreg=0,quarantine_replicas=0,final_gs_inputreg=0,term_select_token=0):
    fields.need(n in (32,256,65536) and p==16 and contexts==1,'S4_P16_TIMING_GEOMETRY')
    bundle=fields.prepare(n,p,f,mode=mode,contexts=contexts,allow_full_constants=allow_full_constants,
        corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1)
    return bind_field(bundle,boundary_inputreg=boundary_inputreg,
        quarantine_replicas=quarantine_replicas,final_gs_inputreg=final_gs_inputreg,term_select_token=term_select_token)


def bind(bundle, *, term_select_token=0,**flags):
    check(bundle)
    timing.flag(term_select_token,'TERM_SELECT_TOKEN')
    fields.need(bundle['parameters'].get('CANONICAL_PIPE_STAGES')==1,'S4_P16_TIMING_CANONICAL_PIPE1')
    result=timing.bind(bundle,**flags)
    if not(any(flags.values()) or term_select_token):return result
    if term_select_token:
        from . import stream27_term_select_p16_diet_bind as term
        result=copy.deepcopy(result)
        names=[name for name in result['files'] if name.startswith('genefer_stream27_shared_warm_')]
        fields.need(len(names)==3,'S4_P16_TIMING_TERM_THREE_FIELDS')
        replaced_terms=set();contracts=[]
        for name in names:
            old=name[:-3];view=copy.deepcopy(result);view['top']=old;view['mode']='warm_signed'
            selected=term.bind(view)
            fields.need(selected['geometry']==result['geometry'],'S4_P16_TIMING_TERM_ZERO_EDGES')
            result['files']=selected['files'];result['source_dependencies']=selected['source_dependencies']
            # The old private term definition is common to three real fields.
            # Keep it while transforming the remaining roots, then remove it
            # only after all consumers name the new common definition.
            parent_term=selected['term_select']['parent_term']
            result['files'][parent_term+'.sv']=view['files'][parent_term+'.sv']
            replaced_terms.add(parent_term);contracts.append(selected['term_select'])
            for filename,text in list(result['files'].items()):
                result['files'][filename]=text.replace(old+' #',selected['top']+' #')
        for parent_term in replaced_terms:result['files'].pop(parent_term+'.sv')
        result['term_select_contracts']=contracts
        hosts=[name[:-3] for name in result['files'] if name.startswith('genefer_stream27_host_chain_')]
        renames={name:name+'_term_select_v1' for name in hosts}
        def rename(text):
            for old,new in renames.items():text=text.replace(old,new)
            return text
        result['files']={rename(name):rename(text) for name,text in result['files'].items()}
        result['top']=rename(result['top'])
        for top in renames.values():
            text=result['files'][top+'.sv']
            text=timing.once(text,'#(parameter ','#(parameter int TERM_SELECT_TOKEN=1,parameter ')
            text=timing.once(text,'endmodule',' // synthesis translate_off\n initial if(TERM_SELECT_TOKEN!=1)$fatal(1,"S4_P16_TIMING_TERM_SELECT_BUILD_FLAG");\n // synthesis translate_on\nendmodule')
            result['files'][top+'.sv']=text
        result['parameters']=dict(result['parameters'],TERM_SELECT_TOKEN=1)
        result['timing_roster']=dict(result.get('timing_roster',{}),TERM_SELECT_TOKEN=1)
        result=timing.close(result,[])
    # Original Montgomery leaves remain the exact donor for CRT and T5b.
    for name in donor.fitted.PRESERVED:
        fields.need(result['files'].get(name)==bundle['files'].get(name),'S4_P16_TIMING_CRT_T5B_MONT_PRESERVED')
    result['p16_timing_binding']=dict(diet_flags=DIET,
        correction_cache_latency=result['geometry']['correction_cache_latency'],
        counted_frontend_added=result['geometry'].get('boundary_frontend_added',0),
        counted_feedback_rows=result['geometry']['feedback_delay'],
        original_nonfield_montgomery_preserved=True,whole_resource_go=False,
        native_executed=False,clock_claim=False)
    result['scope']='P16 composed-diet plus source-specific timing flags; own normal/physical qualification, no P8 promotion inheritance.'
    return close(result)


def prepare(n=65536,p=16,*,paired=False,contexts=1,allow_full_constants=True,
            canonical_pipe_stages=1,corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1,**flags):
    bundle=donor.prepare(n,p,paired=paired,contexts=contexts,allow_full_constants=allow_full_constants,
        canonical_pipe_stages=canonical_pipe_stages,corr_serial_bfs=corr_serial_bfs,
        comm_stage_shared_mlab=comm_stage_shared_mlab,mont_factored=mont_factored)
    return bind(bundle,**flags)

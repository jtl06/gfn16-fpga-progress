"""Private default-OFF warm-progress watchdog correction on frozen R10 lean.

lean build; host GL assumed (unimplemented). No arithmetic, barrier, calendar
or functional selector change. Global progress still is not per-context safety.
"""
import copy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_context_lean_watchdog_bind.py'
BASE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-timing10-native-v1'
PINS={256:('aw8-normal','f1c9f7cccd8303afd0c0ccdeca81aea7f8ccdfac1dbb04aa5b497774448f66cf'),
      65536:('full-normal','bbddffeb640ae8fde76a3c469f442552d8f4581128f33011cc21e2122fd4d962')}
LABEL='lean build; host GL assumed (unimplemented)'
BEFORE=''' wire lean_progress=setup_done || child_frame_accept || child_correction_accept ||
  final_valid || final_boundary_valid || shadow_row_valid || canon_read_valid ||
  shadow_commit_ack || canon_done || (|child_warm_done);
'''
AFTER=''' // Count actual completed warm squares, never BUSY or a predicted timer.
 logic [63:0] lean_completed_seen;
 wire lean_square_progress=child_completed!=lean_completed_seen;
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)lean_completed_seen<=0;
  else lean_completed_seen<=child_completed;
 end
 wire lean_progress=setup_done || child_frame_accept || child_correction_accept ||
  final_valid || final_boundary_valid || shadow_row_valid || canon_read_valid ||
  shadow_commit_ack || canon_done || (|child_warm_done) || lean_square_progress;
'''


def need(ok,label):
    if not ok:raise ValueError('LEAN_WARM_WATCHDOG_'+label)


def sha(raw):
    return hashlib.sha256(raw if isinstance(raw,bytes) else raw.encode()).hexdigest()


def capture(n):
    need(type(n) is int and n in PINS,'SUPPORTED_FROZEN_CAPTURE')
    stage,pin=PINS[n]
    raw=(BASE/stage/'production-bundle.json').read_bytes()
    need(sha(raw)==pin,'EXACT_FROZEN_R10_LEAN')
    return json.loads(raw)


def bind(bundle,*,enabled=0):
    need(type(enabled) is int and enabled in (0,1),'BOOLEAN_FLAG')
    out=copy.deepcopy(bundle)
    if not enabled:return out
    n=out['geometry']['n']
    parent=capture(n)
    need(out==parent and out['parameters']['LEAN_PRODUCTION']==1 and len(out['files'])==58,'EXACT_LEAN_ONLY_NO_MIXTURE')
    old=out['top'];new=old+'_warmprogress_v1';original=out['files'].pop(old+'.sv')
    need(original.count(BEFORE)==1 and original.count('module '+old+' #')==1,'UNIQUE_PROGRESS_ROOT')
    text=original.replace(BEFORE,AFTER,1).replace('module '+old+' #','module '+new+' #',1)
    need(text.replace(AFTER,BEFORE,1).replace('module '+new+' #','module '+old+' #',1)==original,'LITERAL_REVERSE')
    # New observation never drives counters, recurrence, masks or publication.
    for begin,end in (('  // Cold-only transaction:',' wire cold_first_correction='),
                      ('   // Hold the scratch lease','   if(shadow_commit_ack && canonical_owned)begin')):
        block=original[original.index(begin):original.index(end)]
        need(block in text,'ONE_SHOT_AND_PUBLICATION_LITERAL')
    out['files'][new+'.sv']=text
    out['top']=new;out['rtl_sources']=list(out['files'])
    out['generated_sha256']={name:sha(body) for name,body in out['files'].items()}
    out['source_dependencies']=list(dict.fromkeys(out['source_dependencies']+[SELF]))
    out['source_sha256']=dict(out['source_sha256'],**{SELF:sha((ROOT/SELF).read_bytes())})
    need(out['geometry']==parent['geometry'] and out['parameters']==parent['parameters'] and
         all(out['files'][name]==body for name,body in parent['files'].items() if name!=old+'.sv'),
         '57_OTHER_FILES_GEOMETRY_PARAMETERS_LITERAL')
    out['lean_watchdog_warm_progress']=dict(enabled=True,default_off_exact=True,label=LABEL,
        parent_bundle_sha256=PINS[n][1],parent_top=old,parent_root_sha256=sha(original),
        root_edits=[[BEFORE,AFTER],['module '+old+' #','module '+new+' #']],
        new_register_bits_declared=64,actual_mapped_cost_unmeasured=True,
        observed='actual child_completed counter change; one edge observation, not per-context watchdog',
        threshold_sticky_error_reset_existing_progress_unchanged=True,
        arithmetic_calendar_profile_one_shot_barrier_publication_literal=True,
        host_gl_implemented=False,rollback_implemented=False,protection_inherited=False,
        native_qualified=False,clock_area_or_promotion_claim=False)
    return out


def prepare(n=256,*,enabled=0):
    return bind(capture(n),enabled=enabled)


def watchdog_trace(n,interval,squares,stall=False):
    """Bounded pure counter/watchdog transition model, not RTL evidence."""
    limit=64*n+4096
    age=seen=completed=0;error=False;fired=None
    for edge in range(interval*squares+limit+2 if stall else interval*squares+2):
        progress=completed!=seen
        next_seen=completed
        if edge==0 or progress:age=0
        elif age==limit-1:error=True
        else:age+=1
        seen=next_seen
        if not stall and edge and edge%interval==0:completed+=1
        if error and fired is None:fired=edge
    return dict(error=error,first_error_edge=fired,completed=completed,limit=limit)

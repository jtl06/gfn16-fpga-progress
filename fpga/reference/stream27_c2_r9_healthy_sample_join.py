"""R9 own protected source/calendar join; no ancestor native/clock credit.

The generic R10 model supplies ONLY scalar event arithmetic. Its source flags,
lean outputs, native results and clocks are never used. The R6 helper supplies
ONLY pinned receipt/log parsers. Every executed native join is exact R9.
"""
import json
from pathlib import Path
from . import stream27_context_storage_combo_registerederror_bind as own
from . import stream27_context_timing10_model as arithmetic
from . import stream27_c2_r6_healthy_sample_join as parsers

ROOT=own.ROOT
SELF='reference/stream27_c2_r9_healthy_sample_join.py'
BINDER_PIN='3a507134f0a68fa393653ca1f8c7ac6e7fe7288d1f5ad0e7e36dc9657cf2a865'
MODEL='reference/stream27_context_registered_error_model.py'
MODEL_PIN='46266666b8bfe55abe8b00d31df7e21d6cc3cf7a036d614cedf5358c97613513'
ARITHMETIC='reference/stream27_context_timing10_model.py'
ARITHMETIC_PIN='dfd2e6af673e11d6ef40ce2a9b3e87970b93f1b129762559d6803483ef9567c6'
PARSERS='reference/stream27_c2_r6_healthy_sample_join.py'
PARSERS_PIN='0bb14b63ac9ffda43be8ea7ef1ad6f4f1236ec2534bad5886ced42b5e6e36b55'
CAPTURE='results/throughput-20260929/trackS-c2-storage-combo-registerederror-native-v1/full-normal/production-bundle.json'
CAPTURE_PIN='01220c6efc522973786786eb5c65076d3bf396a9c290aa65464e3086e34d8bc9'
INDEX='results/throughput-20260929/trackS-c2-storage-combo-registerederror-ownlong-v1/numerical-index-v1.json'
JOBS={2:('s4-p16-c2-combo-r9-full-normal-q1-v1','normal-full-c2-two-bases-context-alone-and-joint.log','R84_C2_FULL_PASS '),
      100:('s4-p16-c2-combo-r9-own100-serial-q1-v1','normal-full-c2-combo-r9-own100-percontext.log','R84_C2_THREAD100_PASS '),
      1000:('s4-p16-c2-combo-r9-continuous1000-q1-v1','normal-full-c2-combo-r9-continuous1000-percontext.log','R84_C2_THREAD100_PASS ')}
WRAP_ID='s4-p16-c2-combo-r9-full-wrap-normal-q1-v1'
WRAP_LOG='oneshot-full-wrap-three-aliases.log'


def need(ok,label):
    if not ok:raise ValueError('R9_HEALTHY_JOIN_'+label)


def source():
    for name,pin in ((own.SELF,BINDER_PIN),(MODEL,MODEL_PIN),(ARITHMETIC,ARITHMETIC_PIN)):
        need(own.sha((ROOT/name).read_bytes())==pin,'FROZEN_RECIPE:'+name)
    raw=(ROOT/CAPTURE).read_bytes();need(own.sha(raw)==CAPTURE_PIN,'OWN_CAPTURE')
    b=json.loads(raw)
    need(len(b['files'])==55 and 'LEAN_PRODUCTION' not in b['parameters'] and
         b['parameters']['ERROR_AGGREGATION_REGISTERED']==1,'OWN_PROTECTED55')
    need({name:own.sha(text) for name,text in b['files'].items()}==b['generated_sha256'],'ALL55_CAPTURE_HASHES')
    host=b['files'][b['top']+'.sv']
    for anchor in ('CONTEXT_OFFSET=4229,SECOND_CORRECTION=8232;',
                   'if(child_correction_accept)begin second_correction_sent<=1;',
                   'else phase[c]<=RAW_READY;', 'phase[phase[0]!=RAW_READY]<=CANON_LOAD;',
                   "if(canonical_load && row_address_d==ROW_W'(ROWS-1))phase[canonical_owner]<=CANON_WAIT;",
                   'context_canonical_cycles[canonical_owner]<=canon_cycles;phase[canonical_owner]<=COPY;',
                   "if(copy_committed==(AW+1)'(N-1))begin",own.PUB_PROPOSAL,own.PUB_DRAIN):
        need(host.count(anchor)==1,'OWN_SOURCE_CALENDAR:'+anchor[:80])
    need(host.count('second_correction_sent<=0;second_correction_pending<=0;')==2 and
         host.count('publish_pending<=0;publish_context<=0;publish_owner<=0;')==2,
         'OWN_RESET_NEWJOB_ONE_SHOT_PUBLICATION_CLEAR')
    need('assign safety_error=local_error || child_error_barrier || canon_error;' in host,
         'REGISTERED_SOURCE_PUBLIC_SAFETY_MASK')
    g=b['geometry']
    need((g['n'],g['p'],g['rows'],g['warm_interval'],g['first_digit'],g['carry_done'],
          g['correction_cache_latency'])==(65536,16,4096,8459,8458,12557,78),'OWN_GEOMETRY')
    canon=b['files']['genefer_stream27_canonical_image_directbound_v1.sv']
    need('three edges/digit, 9N normal / 10N special.' in canon and
         'READ_WORD:state<=VALUE_WORD;' in canon and 'SPECIAL_WRITE:begin' in canon,
         'OWN_ORDINARY_SPECIAL_CANONICAL_SERVICE')
    need(b['context_registered_error']['publication_fence_edges_per_job']==1 and
         b['context_registered_error']['healthy_warm_and_cold_calendar_delta']==0,
         'OWN_PUBLICATION_DELTA_ONLY')
    return b


def event_calendar(count,*,special=(False,False)):
    return arithmetic.event_calendar(source()['geometry'],count,special=special)


def source_ledger():
    b=source();g=b['geometry']
    calendars={str(k):arithmetic.event_calendar(g,k) for k in (2,100,1000,1911814)}
    need(calendars['2']['publication_edges']==[680686,1340150] and
         calendars['100']['publication_edges']==[1509668,2169132] and
         calendars['1000']['publication_edges']==[9122768,9782232] and
         calendars['1911814']['pair_completion_cycles']==16173357858,'OWN_EXPECTED_COUNTS')
    return dict(schema='r9-own-source-healthy-ledger-v1',status='SOURCE_MODEL_ONLY_NOT_NATIVE_JOIN',
        producer=dict(path=SELF,sha256=own.sha((ROOT/SELF).read_bytes())),
        production=dict(top=b['top'],sv_count=55,bundle_sha256=CAPTURE_PIN,
            root_sha256=b['generated_sha256'][b['top']+'.sv'],binder_sha256=BINDER_PIN),
        calendars=calendars,sample=calendars['1911814'],selected_period_ns=None,
        projected_pair_seconds=None,projected_amortized_seconds=None,promotion_allowed=False,
        conditions=['Healthy protected source, legal profiles/owners, timely feed, no faults or host gaps.',
            'Cold ordinary equal-K1911814 pair, same base604832956; distinct finite bases are separate numeric evidence.',
            'Both profiles/finalcanonical/copy included; external load/readback/transport excluded.',
            'Special minus-one adds65536 edges per affected job, once; no measured full-sample PRP.'],
        arithmetic_reuse=dict(path=ARITHMETIC,sha256=ARITHMETIC_PIN,functions_only=['event_calendar'],
            no_timing10_source_native_lean_clock_credit=True))


def validate_footer(footer,count,g):
    e=arithmetic.event_calendar(g,count)
    need(footer['interval']==e['interval'] and footer['warm_edges']==e['warm_edges'] and
         footer['done_edges']==e['publication_edges'] and
         footer['joint_cycles']==e['pair_completion_cycles']+g['n'] and
         footer['setup_edges']==[99,199] and footer['bases']==[604832956,999999937] and
         footer['signed96'] is True and footer['independent_reference'] is True,'ACTUAL_NATIVE_CALENDAR')
    need(footer['launches']==[[first+i*g['warm_interval'] for i in range(count)] for first in e['first_edges']],
         'EVERY_OWN_LAUNCH')
    if count==2:
        need(footer['context_alone_bit_identical'] is True and footer['squares']==8 and
             footer['reads']==393216 and footer['peer_live_reads']==65536,'OWN_SAME_C2_ALONE_JOINT')
    else:
        need(footer['count_per_context']==count and footer['squares']==2*count and
             footer['descriptors']==2*(count-1) and footer['reads']==262144 and
             footer['peer_live_reads']==65536 and footer['initial_resets']==1 and
             footer['initial_load_words']==131072,'OWN_CONTINUOUS_NO_RELOAD')
    return e


def close(*,index_sha256):
    """Only run after the numerical owner freezes its exact actual index."""
    need(type(index_sha256) is str and len(index_sha256)==64,'EXPLICIT_OWN_INDEX_PIN')
    need(own.sha((ROOT/PARSERS).read_bytes())==PARSERS_PIN,'PINNED_PARSERS_ONLY')
    b=source();raw=(ROOT/INDEX).read_bytes();need(own.sha(raw)==index_sha256,'IMMUTABLE_OWN_INDEX')
    index=json.loads(raw)
    need(index['production']['all55_generated_sha256']==b['generated_sha256'] and
         index['production']['captured_bundle']['sha256']==CAPTURE_PIN,'INDEX_ALL55_SOURCE_JOIN')
    refs=[];actual={}
    for count,(identity,name,prefix) in JOBS.items():
        ref,report,manifest,native=parsers.native_join(identity,b,index)
        footer=parsers.read_footer(native,report,name,prefix)
        e=validate_footer(footer,count,b['geometry'])
        ref['log_sha256']=report['artifacts'][name];refs.append(ref)
        actual[str(count)]=dict(calendar=e,joint_cycles=footer['joint_cycles'],
            joint_squares=2*count,native_total_squares=footer['squares'],native_total_reads=footer['reads'])
    ref,report,manifest,native=parsers.native_join(WRAP_ID,b,index)
    validate_footer(parsers.read_footer(native,report,WRAP_LOG,'R84_C2_FULL_PASS '),2,b['geometry'])
    need('R9_FULL_WRAP_PASS aliases=3 cold_accepts=2 cache_events_per_field=4 reads=393216 masks=1/2/3 '
         'independent_reference=1 real_datapath_edges=1 simulation_only=1\n' in (native/WRAP_LOG).read_text(),
         'OWN_FULL_WRAP_ONE_ACCEPT_EACH_HOST_TIMESTAMP_ALIASES_ONLY')
    ref['log_sha256']=report['artifacts'][WRAP_LOG];refs.append(ref)
    out=source_ledger()
    out.update(status='OWN_SOURCE_NATIVE_CALENDAR_JOIN_PASS_CLOCK_NULL',
        numerical_index=dict(path=INDEX,sha256=index_sha256),native_calendars=actual,native_references=refs,
        accepted_second_cold_edge=8436,healthy_peer_lease_argument=dict(first_peer=4433,
            correction=8436,next_ctx0_feedback=8663,first_auto_boundaries=[12761,16990],
            no_legal_cold_auto_collision=True),mandatory_own_full_accelerated_host_wrap_native_pass=True,
        parser_reuse=dict(path=PARSERS,sha256=PARSERS_PIN,
            functions_only=['native_join','read_footer'],no_ancestor_source_native_clock_review_credit=True),
        limits=['No real billions of protocol timesteps or measured full-sample PRP.',
            'Cache test is eventual duplicate-abort, not first matching-token age protection.',
            'Reset-at-wrap and independent bank oracle are not inferred from timestamp aliases.',
            'Targeted error/publication fixture, scoped faults/context, own clock/review/advisor stay separate.'])
    return out


if __name__=='__main__':print(json.dumps(source_ledger(),indent=2))

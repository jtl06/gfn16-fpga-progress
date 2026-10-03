"""Own R7 source/calendar/native join; no ancestor execution or clock credit.

The pinned R6 helper supplies only arithmetic and receipt-parser functions.
Its source()/close(), producer, index and native identities are never used.
Every production/native join below is to the immutable R7 graph and index.
"""
import json

from . import stream27_context_storage_combo_faultlocal_bind as own
from . import stream27_c2_r6_healthy_sample_join as mechanics

ROOT = own.ROOT
BINDER_PIN = '847dc928e3c84e565d8971fbd05e65ff2e3d50627e0d8b8347ff2ae025918d06'
SELF = 'reference/stream27_c2_r7_healthy_sample_join.py'
MECHANICS = 'reference/stream27_c2_r6_healthy_sample_join.py'
MECHANICS_PIN = '0bb14b63ac9ffda43be8ea7ef1ad6f4f1236ec2534bad5886ced42b5e6e36b55'
CAPTURE = 'results/throughput-20260929/trackS-c2-storage-combo-faultlocal-native-v1/full-normal/production-bundle.json'
CAPTURE_PIN = 'e2671f87b4f6173dbfebd5eb30ddfbe0113cb78fe692d4b594d2492e60c343e7'
INDEX = 'results/throughput-20260929/trackS-c2-storage-combo-faultlocal-ownlong-v1/numerical-index-v1.json'
INDEX_PIN = '647550c4f9b67fcfa55a0e4e2b6fb6fcd7e6ae2abf7538d88af7f567f75916c0'
JOBS = {
    2: ('s4-p16-c2-combo-r7-full-normal-q1-v1', 'normal-full-c2-two-bases-context-alone-and-joint.log', 'R84_C2_FULL_PASS '),
    100: ('s4-p16-c2-combo-r7-own100-serial-q1-v1', 'normal-full-c2-combo-r7-own100-percontext.log', 'R84_C2_THREAD100_PASS '),
    1000: ('s4-p16-c2-combo-r7-continuous1000-q1-v1', 'normal-full-c2-combo-r7-continuous1000-percontext.log', 'R84_C2_THREAD100_PASS '),
}
WRAP_ID = 's4-p16-c2-combo-r7-full-wrap-normal-q1-v1'
WRAP_LOG = 'oneshot-full-wrap-three-aliases.log'
event_calendar = mechanics.event_calendar
validate_footer = mechanics.validate_footer


def need(ok, label):
    if not ok:
        raise ValueError('R7_HEALTHY_SAMPLE_' + label)


def source():
    need(own.sha((ROOT/own.SELF).read_bytes()) == BINDER_PIN, 'FROZEN_OWN_BINDER')
    bundle = own.prepare(65536, enabled=1)
    raw = (ROOT/CAPTURE).read_bytes()
    need(own.sha(raw) == CAPTURE_PIN, 'FROZEN_OWN_CAPTURE')
    capture = json.loads(raw)
    need(capture['files'] == bundle['files'] and capture['parameters'] == bundle['parameters'] and
         capture['geometry'] == bundle['geometry'], 'ALL55_OWN_SOURCE_CAPTURE')
    host = bundle['files'][bundle['top']+'.sv']
    for anchor in ('CONTEXT_OFFSET=4229,SECOND_CORRECTION=8232;',
                   'if(child_correction_accept)begin second_correction_sent<=1;',
                   'else phase[c]<=RAW_READY;', 'phase[phase[0]!=RAW_READY]<=CANON_LOAD;',
                   "if(canonical_load && row_address_d==ROW_W'(ROWS-1))phase[canonical_owner]<=CANON_WAIT;",
                   'context_canonical_cycles[canonical_owner]<=canon_cycles;phase[canonical_owner]<=COPY;',
                   "if(copy_committed==(AW+1)'(N-1))begin",
                   'published[canonical_owner]<=1;done_q[canonical_owner]<=1;phase[canonical_owner]<=IDLE;canonical_owned<=0;'):
        need(host.count(anchor) == 1, 'OWN_ACCEPTED_PUBLICATION_ANCHOR:'+anchor)
    need(host.count('second_correction_sent<=0;second_correction_pending<=0;') == 2,
         'OWN_RESET_NEWJOB_ONE_SHOT_CLEAR')
    g = bundle['geometry']
    need((g['n'],g['p'],g['rows'],g['warm_interval'],g['first_digit'],g['carry_done'],
          g['correction_cache_latency']) == (65536,16,4096,8459,8458,12557,78), 'OWN_GEOMETRY')
    image = bundle['files']['genefer_stream27_canonical_image_loadlocal_v1.sv']
    need('three edges/digit, 9N normal / 10N special.' in image and
         'READ_WORD:state<=VALUE_WORD;' in image and 'SPECIAL_WRITE:begin' in image,
         'OWN_ORDINARY_SPECIAL_CANONICAL_SERVICE')
    need(bundle['context_storage_combo_faultlocal']['calendar_delta'] == 0 and
         bundle['context_storage_combo_oneshot']['model']['fixed_accepted_edges'] == [8436],
         'OWN_ACCEPTED_ONE_SHOT_AND_COMPARE_DELTA')
    return bundle


def close():
    need(own.sha((ROOT/MECHANICS).read_bytes()) == MECHANICS_PIN, 'PINNED_PARSER_ARITHMETIC_ONLY')
    bundle = source()
    raw = (ROOT/INDEX).read_bytes()
    need(own.sha(raw) == INDEX_PIN, 'IMMUTABLE_OWN_INDEX')
    index = json.loads(raw)
    need(index['production']['all55_generated_sha256'] == bundle['generated_sha256'] and
         index['production']['captured_bundle']['sha256'] == CAPTURE_PIN, 'INDEX_ALL55_CAPTURE_JOIN')
    refs = []
    measured = {}
    for count,(identity,name,prefix) in JOBS.items():
        ref,report,manifest,native = mechanics.native_join(identity,bundle,index)
        footer = mechanics.read_footer(native,report,name,prefix)
        value = validate_footer(footer,count)
        ref['log_sha256'] = report['artifacts'][name]
        refs.append(ref)
        measured[str(count)] = dict(warm_edges=value['warm_edges'],publication_edges=value['publication_edges'],
            joint_cycles=footer['joint_cycles'],launches_per_context=count,joint_squares=2*count,
            native_total_squares=footer['squares'],native_total_reads=footer['reads'],real_native=True)
    ref,report,manifest,native = mechanics.native_join(WRAP_ID,bundle,index)
    meta = manifest['faultlocal_full_wrap']
    need(meta['production_source_unchanged'] and meta['monitor_only_stateless_observer'] and
         meta['forced_value'] == 'host cycles64 only' and meta['protocol_arithmetic_payload_owner_time_unchanged'] and
         not meta['billions_of_edges_simulated'], 'OWN_FULL_WRAP_NO_PROTOCOL_TIME_FORCE')
    validate_footer(mechanics.read_footer(native,report,WRAP_LOG,'R84_C2_FULL_PASS '),2)
    need('R7_FULL_WRAP_PASS aliases=3 cold_accepts=2 cache_events_per_field=4 reads=393216 masks=1/2/3 '
         'independent_reference=1 real_datapath_edges=1 simulation_only=1\n' in (native/WRAP_LOG).read_text(),
         'OWN_FULL_NATIVE_ONE_COLD_ACCEPT_EACH_THREE_ALIASES')
    ref['log_sha256'] = report['artifacts'][WRAP_LOG]
    refs.append(ref)
    sample = event_calendar(1911814)
    need(sample['pair_completion_cycles'] == 16173357856 and
         sample['warm_edges'] == [16172038929,16172043158] and
         sample['publication_edges'] == [16172698393,16173357856], 'OWN_SAMPLE_EVENT_CALENDAR')
    aliases = own.oneshot.prove_wraps(8232)['old_alias_edges'][1:]
    need(aliases == [4294975732,8589943028,12884910324], 'THREE_SUPPRESSED_ALIASES_IN_SAMPLE')
    return dict(schema='r7-own-source-healthy-sample-join-v1',status='OWN_SOURCE_CYCLE_NATIVE_JOIN_PASS_CLOCK_NULL',
        producer=dict(path=SELF,sha256=own.sha((ROOT/SELF).read_bytes())),
        mechanics_reuse=dict(path=MECHANICS,sha256=MECHANICS_PIN,
            functions_only=['event_calendar','validate_footer','native_join','read_footer'],
            no_ancestor_source_execution_clock_or_review_inherited=True),
        numerical_index=dict(path=INDEX,sha256=INDEX_PIN),
        production=dict(top=bundle['top'],root_sha256=bundle['generated_sha256'][bundle['top']+'.sv'],
            bundle_sha256=CAPTURE_PIN,sv_count=55,source_own_all55_join=True),
        native_calendars=measured,native_references=refs,sample=sample,
        accepted_second_cold_edge=8436,suppressed_old_alias_edges=aliases,
        reset_newjob_clear_source_proven=True,mandatory_full_geometry_accelerated_wrap_native_pass=True,
        selected_period_ns=None,projected_pair_seconds=None,projected_amortized_seconds=None,promotion_allowed=False,
        conditions=['Healthy legal profiles/full owners, timely descriptor feed with no host gaps or faults.',
            'Equal-length ordinary pair; each special image adds65536 service edges once.',
            'Both cold profiles, canonical and copy included; external load/readback/gaps/transport excluded.'],
        scope_limits=['Scalar full-sample calendar, not measured full-sample PRP/board/runtime/individual latency.',
            'Own full wrap forces only host timestamp, not billions of protocol/arithmetic edges.',
            'R6 AW8 reset/newjob wrap receipt is unchanged-host component scope only; no whole R7 native inheritance.',
            'Forced cold/auto collision retains global abort; accepted one-shot wording covers noncolliding healthy traces.',
            'Cache eventual duplicate-ready abort is not first matching-token age detection.',
            'Own full-contract COUNT2 reset is not epoch-wrap reset; own1000 proves finite epoch/ordinal traversal.',
            'Own physical audit/review/advisor are separate; no clock or old C2 sample qualification inherited.'])


if __name__ == '__main__':
    print(json.dumps(close(),indent=2))

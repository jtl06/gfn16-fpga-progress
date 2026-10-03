"""R6 own-source publication ledger with the second-cold alias closed.

This is a scalar source proof. Native quick/full/wrap/long and a new routed
clock remain separate gates; no old C2 numerical or physical PASS is inherited.
"""
import json

from . import stream27_context_storage_combo_oneshot_bind as oneshot
from . import stream27_c2_storage2_record_ledger_v1 as calendar

ROOT = oneshot.ROOT
BINDER_PIN = '586117feeb61f81e6049d8bba942e843048b2d792f90ba612ebffd76da401810'
BASE = ROOT/'results/throughput-20260929/trackS-c2-storage-combo-oneshot-native-v1/full-normal'
ID = 's4-p16-c2-combo-r6-full-normal-q1-v1'
EVIDENCE = ROOT/'queue/evidence'/ID
LOG_NAME = 'normal-full-c2-two-bases-context-alone-and-joint.log'


def need(ok, label):
    if not ok:
        raise ValueError('C2_ONESHOT_LEDGER_' + label)


def source():
    need(oneshot.sha((ROOT/oneshot.SELF).read_bytes()) == BINDER_PIN, 'OWN_FROZEN_BINDER')
    parent = oneshot.prepare(65536)
    bundle = oneshot.prepare(65536, enabled=1)
    host = bundle['files'][bundle['top']+'.sv']
    need(oneshot.reverse_host(host, top=bundle['top'], parent_top=parent['top']) ==
         parent['files'][parent['top']+'.sv'], 'OWN_HOST_TRANSITION_DELTA_ONLY')
    need(bundle['geometry'] == parent['geometry'] and bundle['two_context_schedule'] ==
         parent['two_context_schedule'], 'NO_ACCEPTED_CALENDAR_CHANGE')
    g = bundle['geometry']
    need((g['n'], g['p'], g['rows'], g['warm_interval'], g['first_digit'], g['carry_done'],
          g['correction_cache_latency']) == (65536,16,4096,8459,8458,12557,78), 'OWN_FULL_GEOMETRY')
    need(host.count('CONTEXT_OFFSET=4229,SECOND_CORRECTION=8232;') == 1,
         'OWN_COLD_OFFSET_NOT_ANCESTOR8233')
    need(len(bundle['files']) == 55 and all(bundle['files'][name] == text
         for name,text in parent['files'].items() if name != parent['top']+'.sv'), 'ALL54_DOWNSTREAM_EXACT')
    proof = bundle['context_storage_combo_oneshot']['model']
    need(proof['fixed_accepted_edges'] == [8436] and proof['missed_accept_retained'] and
         host.count('if(child_correction_accept)begin second_correction_sent<=1;') == 1 and
         host.count('second_correction_sent<=0;second_correction_pending<=0;') == 2,
         'ACCEPT_ONLY_ONESHOT_CLEAR_RESET_NEWJOB')
    return bundle


def ledger(counts=(2,2), *, enabled=(True,True), special=(False,False)):
    source()
    value = calendar.ledger(counts, enabled=enabled, special=special)
    value.update(candidate=ID, evidence_scope='OWN_R6_SCALAR_SOURCE_ONLY',
        inherited_native_or_clock=False, accepted_cold_calendar_delta=0,
        mandatory_accelerated_wrap_native_pending=True, promotion_allowed=False)
    return value


def sample(period_ns=None):
    source()
    value = calendar.sample(period_ns)
    old_aliases = oneshot.prove_wraps(8232)['old_alias_edges']
    relevant = [edge for edge in old_aliases if edge <= value['pair_completion_cycles']]
    need(value['pair_completion_cycles'] == 16173357856 and len(relevant) == 4,
         'FULL_CHAIN_CROSSES_THREE_ALIAS_EDGES')
    value.update(candidate=ID, evidence_scope='OWN_R6_SCALAR_SOURCE_ONLY',
        old_source_alias_edges_in_horizon=relevant, fixed_cold_accept_edges=[8436],
        old_C2_projection_not_inherited=True, audited_period_used=False,
        mandatory_accelerated_wrap_native_pending=True, own_full_long_clock_review_pending=True,
        promotion_allowed=False,
        scope='R6 equal-length pair scalar calendar; one accepted second cold correction per job. '
              'Includes both cold profiles and final canonical/copy services. Native wrap/full/long '
              'and a new source-own routed audit/review/advisor remain required. '
              'No inherited period, measured full-sample PRP, individual latency or board claim.')
    return value


def check_native():
    """Own R6 full receipt join only; refuses absent/unadmitted evidence."""
    bundle = source()
    captured = json.loads((BASE/'production-bundle.json').read_bytes())
    need(captured['files'] == bundle['files'] and captured['parameters'] == bundle['parameters'] and
         captured['geometry'] == bundle['geometry'], 'OWN_CAPTURE_NOT_ANCESTOR')
    gate = json.loads((EVIDENCE/'gate-receipt.json').read_bytes())
    need(gate.get('id') == ID and gate.get('status') == 'PASS_expected_contracts', 'OWN_FULL_GATE')
    native = EVIDENCE/'attempt-0/collected/output/native'
    report_raw = (native/'report.json').read_bytes()
    report = json.loads(report_raw)
    need(oneshot.sha(report_raw) == gate['report_sha256'], 'OWN_GATE_REPORT_JOIN')
    approved_raw = (native/'approved-manifest.json').read_bytes()
    approved = json.loads(approved_raw)
    need(oneshot.sha(approved_raw) == gate['manifest_sha256'] == report['manifest_sha256'] and
         approved['sources'] == report['sources'], 'OWN_APPROVED_SOURCE_JOIN')
    need(all(report['sources'].get('rtl/'+name) == pin
         for name,pin in bundle['generated_sha256'].items()), 'ALL55_OWN_NATIVE_RTL_JOIN')
    need(approved['build']['parameters'] == dict(bundle['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),
         'OWN_COMPILED_PARAMETERS')
    raw = (native/LOG_NAME).read_bytes()
    need(oneshot.sha(raw) == report['artifacts'][LOG_NAME] and raw.startswith(b'R84_C2_FULL_PASS '),
         'OWN_GATE_BOUND_FOOTER')
    footer = json.loads(raw.removeprefix(b'R84_C2_FULL_PASS '))
    expected = calendar.ledger()
    need(footer['interval'] == 8459 and footer['warm_edges'] == expected['warm_edges'] and
         footer['done_edges'] == expected['publication_edges'] and
         footer['joint_cycles'] == expected['pair_completion_cycles']+65536 and
         footer['launches'] == [[204,8663],[4433,12892]] and
         footer['signed96'] and footer['context_alone_bit_identical'] and footer['independent_reference'],
         'OWN_NATIVE_ACCEPT_AND_PUBLICATION_EDGES')
    expected.update(candidate=ID, evidence_scope='OWN_R6_ADMITTED_NATIVE_FULL55',
                    gate_id=ID, inherited_native_or_clock=False, promotion_allowed=False)
    return expected

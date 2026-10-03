"""Publication ledger for the frozen combined C2, not inherited qualification.

The scalar calendar is reused only after an exact host/canonical source proof.
Own combined native admission and footer/source joins are checked separately.
No local full-N arithmetic, clock search, promotion or board claim is made.
"""
import hashlib
import json
from pathlib import Path

from . import stream27_c2_storage2_record_ledger_v1 as calendar

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-native-v1/full-normal'
BUNDLE_PIN = '02549331f1751a55e94409bb897c89a64df33834680901010dc15ff6e57629e9'
MANIFEST_PIN = 'fb3a56a95f0616c3a8b6799088ca37a1c477cc1fa274e3c7821fc75c60c8c437'
ID = 's4-p16-c2-combo-full-normal-q1-v1'
EVIDENCE = ROOT / 'queue/evidence' / ID
LOG_NAME = 'normal-full-c2-two-bases-context-alone-and-joint.log'
ROSTER = ['storage2', 'packed_delays', 'root_weight_retime', 'term_payload_lookahead']


def need(ok, label):
    if not ok:
        raise ValueError('C2_COMBO_LEDGER_' + label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source():
    """Bind this candidate's source, without importing its parent's native PASS."""
    raw = (BASE / 'production-bundle.json').read_bytes()
    manifest_raw = (BASE / 'manifest.json').read_bytes()
    need(sha(raw) == BUNDLE_PIN and sha(manifest_raw) == MANIFEST_PIN, 'OWN_CAPTURE_PIN')
    bundle, manifest = json.loads(raw), json.loads(manifest_raw)
    parent = calendar.source()  # Pure pinned source check, NOT check_native().
    need(len(bundle['files']) == 53 and bundle['context_storage_combo']['roster'] == ROSTER,
         'REQUESTED_COMPOSITION_ONLY')
    need(bundle['geometry'] == parent['geometry'] and bundle['parameters'] == parent['parameters'],
         'ZERO_PUBLIC_CALENDAR_PARAMETERS')
    need(bundle['context_storage_combo']['zero_public_edges'] is True and
         bundle['context_storage_combo']['qualified_product_slot_bypass_cache_state_unchanged'] is True,
         'PUBLIC_AUTHORITY_CONTRACT')
    need(all(sha(text.encode()) == bundle['generated_sha256'][name] == manifest['sources']['rtl/' + name]
             for name, text in bundle['files'].items()), 'OWN_ALL_PRODUCTION_SOURCE_JOIN')
    host = bundle['files'][bundle['top'] + '.sv']
    parent_host = parent['files'][parent['top'] + '.sv']
    need(host.replace('module ' + bundle['top'] + ' #', 'module ' + parent['top'] + ' #', 1)
         == parent_host, 'HOST_FRAMING_AND_PUBLICATION_LITERAL_PARENT')
    # Every numeric/publication unit downstream of the changed fields is exact.
    unchanged = [name for name in parent['files'] if any(key in name for key in
        ('warm_contexts_', 'blockcarry_', 'canonical_image_', 'host_image_', 'descriptor_fifo_',
         'genefer_crt3_', 'genefer_div_recip_', 'genefer_sdp_ram32'))]
    need(len(unchanged) >= 10 and all(bundle['files'].get(name) == parent['files'][name]
                                    for name in unchanged), 'FINAL_SERVICE_AND_CARRY_EXACT')
    expected = dict(bundle['parameters'], EPOCH_SEED0=65534, EPOCH_SEED1=42)
    need(manifest['build']['parameters'] == expected and
         manifest['context_storage_combo']['donor_PASS_clock_pilot_not_inherited'] is True,
         'OWN_COMPILED_EPOCH_OVERRIDES_AND_SCOPE')
    return bundle


def ledger(counts=(2, 2), *, enabled=(True, True), special=(False, False)):
    """Source-proved equal calendar, not a claim of equal numerical evidence."""
    source()
    value = calendar.ledger(counts, enabled=enabled, special=special)
    value.update(candidate=ID, evidence_scope='SOURCE_CALENDAR_ONLY',
                 parent_native_PASS_inherited=False, promotion_allowed=False)
    return value


def sample(period_ns=None):
    source()
    value = calendar.sample(period_ns)
    value.update(candidate=ID, evidence_scope='SOURCE_CALENDAR_ONLY',
                 parent_native_PASS_inherited=False,
                 scope='Own combined cold equal-length pair through both internal ordinary publications. '
                       'Exact host/canonical source calendar; own native/full long, routed clock and '
                       'independent promotion review required. External loads/readback/gaps excluded.')
    return value


def footer_events(value):
    """Scalar footer consistency only; callers still need own admitted gate."""
    need(type(value) is dict and value.get('aw') == 16 and value.get('p') == 16 and
         value.get('contexts') == 2 and value.get('bases') == [604832956, 999999937],
         'OWN_TWO_BASE_FULL_GEOMETRY')
    need(value.get('squares') == 8 and value.get('reads') == 393216 and
         all(value.get(key) is True for key in ('signed96', 'context_alone_bit_identical',
                                              'independent_reference')), 'OWN_NORMAL_SCOPE')
    expected = calendar.ledger()
    need(value.get('interval') == 8459 and value.get('pair_launch_cycles') == 8459 and
         value.get('launches') == [[204, 8663], [4433, 12892]] and
         value.get('warm_edges') == expected['warm_edges'] and
         value.get('done_edges') == expected['publication_edges'], 'OWN_MEASURED_LAUNCH_AND_PUBLICATION')
    need(value.get('joint_cycles') == expected['pair_completion_cycles'] + calendar.N and
         value.get('setup_edges') == [99, 199] and value.get('single_first') == [104, 104] and
         value.get('peer_live_reads') == 65536, 'OWN_SETUP_JOINT_AND_PEER_READS')
    need(type(value.get('single_cycles')) is list and len(value['single_cycles']) == 2,
         'OWN_SOLO_CYCLES_PAIR')
    for c in (0, 1):
        single = calendar.ledger(enabled=(c == 0, c == 1))
        need(value['single_cycles'][c] == single['publication_edges'][c] + calendar.N,
             'OWN_SOLO_PUBLICATION')
    expected.update(candidate=ID, evidence_scope='SCALAR_FOOTER_ONLY_NOT_DEPENDENCY_ADMISSION',
                    parent_native_PASS_inherited=False, promotion_allowed=False)
    return expected


def check_native():
    """Consume the existing own typed gate; no native rerun or archive replay."""
    bundle = source()
    gate = json.loads((EVIDENCE / 'gate-receipt.json').read_bytes())
    need(gate.get('id') == ID and gate.get('status') == 'PASS_expected_contracts', 'OWN_ADMITTED_FULL_GATE')
    native = EVIDENCE / 'attempt-0/collected/output/native'
    report_raw = (native / 'report.json').read_bytes()
    report = json.loads(report_raw)
    need(sha(report_raw) == gate['report_sha256'], 'OWN_REPORT_BOUND_TO_GATE')
    approved_raw = (native / 'approved-manifest.json').read_bytes()
    approved = json.loads(approved_raw)
    need(sha(approved_raw) == gate['manifest_sha256'] == report['manifest_sha256'] and
         approved['sources'] == report['sources'], 'OWN_APPROVED_SOURCE_JOIN')
    need(all(report['sources'].get('rtl/' + name) == pin
             for name, pin in bundle['generated_sha256'].items()), 'OWN_NATIVE_FULL53_SOURCE_JOIN')
    need(approved['build']['parameters'] == dict(bundle['parameters'], EPOCH_SEED0=65534, EPOCH_SEED1=42),
         'OWN_NATIVE_COMPILED_PARAMETERS')
    raw = (native / LOG_NAME).read_bytes()
    need(sha(raw) == report['artifacts'][LOG_NAME] and
         raw.startswith(b'R84_C2_FULL_PASS ') and raw.endswith(b'\n'), 'OWN_GATE_BOUND_FOOTER')
    result = footer_events(json.loads(raw.removeprefix(b'R84_C2_FULL_PASS ')))
    result.update(evidence_scope='OWN_ADMITTED_NATIVE_CALENDAR_AND_FULL53_SOURCE_JOIN',
                  gate_id=ID, report_sha256=gate['report_sha256'], log_sha256=sha(raw))
    return result

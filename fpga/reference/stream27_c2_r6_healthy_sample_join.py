"""Join immutable R6 source, own finite calendars and accepted one-shot proof.

No simulation, vendor command or seconds calculation is performed. The old
calendar producer is used only as an arithmetic implementation, never as an
ancestor native/clock gate. R6's own 55 compiled files qualify this join.
"""
import hashlib
import json

from . import stream27_c2_storage_combo_oneshot_record_ledger_v1 as own

ROOT = own.ROOT
PRODUCER = 'reference/stream27_c2_storage_combo_oneshot_record_ledger_v1.py'
PRODUCER_PIN = '924b93e04e3aefa1a321cb56d1736d8d24f55d1c70f9b2ae4409a0830f16d2de'
ARITHMETIC = 'reference/stream27_c2_storage2_record_ledger_v1.py'
ARITHMETIC_PIN = 'aaa5ae73046d6b5802a02714a6111df0b648ca3ca9f23e2c46c7e013be437e09'
INDEX = 'results/throughput-20260929/trackS-c2-storage-combo-oneshot-ownlong-v1/numerical-index-v1.json'
INDEX_PIN = '5c0b82ee24ff5887716046ca5d31049a75ab66411570304fd81d189efc962a03'
JOBS = {
    2: ('s4-p16-c2-combo-r6-full-normal-q1-v1',
        'normal-full-c2-two-bases-context-alone-and-joint.log', 'R84_C2_FULL_PASS '),
    100: ('s4-p16-c2-combo-r6-own100-serial-q1-v1',
          'normal-full-c2-combo-r6-own100-percontext.log', 'R84_C2_THREAD100_PASS '),
    1000: ('s4-p16-c2-combo-r6-continuous1000-q1-v1',
           'normal-full-c2-combo-r6-continuous1000-percontext.log', 'R84_C2_THREAD100_PASS '),
}
WRAP_ID = 's4-p16-c2-combo-r6-full-wrap-normal-q1-v1'
WRAP_LOG = 'oneshot-full-wrap-three-aliases.log'
AW8_WRAP_ID = 's4-p16-c2-combo-r6-aw8-wrap-normal-q1-v3'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def need(ok, label):
    if not ok:
        raise ValueError('R6_HEALTHY_SAMPLE_' + label)


def event_calendar(count, *, special=(False, False)):
    """Own equal-count healthy pair, no host feed stalls/ordinary by default."""
    need(type(count) is int and 1 <= count <= 0xffffffff, 'FULL32_COUNT')
    need(len(special) == 2 and all(type(v) is bool for v in special), 'SPECIAL_MASK')
    first = [204, 4433]
    warm = [edge+(count-1)*8459+12558 for edge in first]
    release = -1
    allocation = [None, None]
    publication = [None, None]
    remaining = {0, 1}
    order = []
    while remaining:
        edge, context = min((max(warm[c]+2, release+1), c) for c in remaining)
        allocation[context] = edge
        publication[context] = edge+4096+10*65536+6+(65536 if special[context] else 0)
        release = publication[context]
        order.append(context)
        remaining.remove(context)
    return dict(count_per_context=count, first_edges=first, interval=8459,
        warm_edges=warm, canonical_allocation_edges=allocation,
        publication_edges=publication, publication_order=order,
        pair_completion_cycles=max(publication), special=list(special),
        source_model_only=True, measured_full_sample_PRP=False)


def validate_footer(footer, count):
    value = event_calendar(count)
    need(footer['interval'] == value['interval'] and footer['warm_edges'] == value['warm_edges'] and
         footer['done_edges'] == value['publication_edges'] and
         footer['joint_cycles'] == value['pair_completion_cycles']+65536 and
         footer['setup_edges'] == [99, 199] and footer['bases'] == [604832956, 999999937] and
         footer['signed96'] is True and footer['independent_reference'] is True, 'NATIVE_CALENDAR_REFERENCE')
    need(footer['launches'] == [[first+i*8459 for i in range(count)] for first in (204,4433)],
         'EVERY_NATIVE_ACCEPTED_LAUNCH')
    if count == 2:
        need(footer['context_alone_bit_identical'] is True and footer['squares'] == 8 and
             footer['reads'] == 393216 and footer['peer_live_reads'] == 65536, 'SAME_C2_ALONE_JOINT')
    else:
        need(footer['count_per_context'] == count and footer['squares'] == 2*count and
             footer['descriptors'] == 2*(count-1) and footer['reads'] == 262144 and
             footer['peer_live_reads'] == 65536 and footer['initial_resets'] == 1 and
             footer['initial_load_words'] == 131072, 'OWN_CONTINUOUS_COUNTS_AND_NO_RELOAD')
    return value


def native_join(identity, bundle, index):
    evidence = ROOT/'queue/evidence'/identity
    native = evidence/'attempt-0/collected/output/native'
    gate_raw = (evidence/'gate-receipt.json').read_bytes()
    gate = json.loads(gate_raw)
    report_raw = (native/'report.json').read_bytes()
    report = json.loads(report_raw)
    manifest_raw = (native/'approved-manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    need(gate['id'] == identity and gate['status'] == 'PASS_expected_contracts' and
         sha(report_raw) == gate['report_sha256'] and
         sha(manifest_raw) == gate['manifest_sha256'] == report['manifest_sha256'], 'OWN_TYPED_REPORT_JOIN')
    need(manifest['sources'] == report['sources'] and
         all(report['sources'].get('rtl/'+name) == pin for name,pin in bundle['generated_sha256'].items()),
         'EVERY_OWN55_COMPILED_RTL')
    need(manifest['build']['parameters'] == dict(bundle['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42) and
         len(manifest['build']['sv_sources']) == 56, 'OWN_PARAMETERS_PLUS_STATELESS_OBSERVER')
    entry = next((row for row in index['jobs'] if row['id'] == identity), None)
    need(entry is not None and entry['gate']['sha256'] == sha(gate_raw) and
         entry['report']['sha256'] == sha(report_raw) and
         entry['selected_manifest']['sha256'] == sha(manifest_raw), 'OWN_NUMERICAL_INDEX_JOIN')
    ref = dict(id=identity, gate_sha256=sha(gate_raw), report_sha256=sha(report_raw),
               approved_manifest_sha256=sha(manifest_raw), production_sv=55)
    return ref, report, manifest, native


def read_footer(native, report, name, prefix):
    raw = (native/name).read_bytes()
    need(sha(raw) == report['artifacts'][name], 'GATE_BOUND_LOG')
    rows = [line[len(prefix):] for line in raw.decode().splitlines() if line.startswith(prefix)]
    need(len(rows) == 1, 'ONE_FOOTER')
    return json.loads(rows[0])


def close():
    need(sha((ROOT/PRODUCER).read_bytes()) == PRODUCER_PIN and
         sha((ROOT/ARITHMETIC).read_bytes()) == ARITHMETIC_PIN, 'IMMUTABLE_ARITHMETIC_PRODUCERS')
    bundle = own.source()
    capture_raw = (own.BASE/'production-bundle.json').read_bytes()
    capture = json.loads(capture_raw)
    need(capture['files'] == bundle['files'] and capture['parameters'] == bundle['parameters'] and
         capture['geometry'] == bundle['geometry'], 'OWN_CAPTURE_NOT_ANCESTOR')
    host = bundle['files'][bundle['top']+'.sv']
    for anchor in ('else phase[c]<=RAW_READY;', 'phase[phase[0]!=RAW_READY]<=CANON_LOAD;',
                   "if(canonical_load && row_address_d==ROW_W'(ROWS-1))phase[canonical_owner]<=CANON_WAIT;",
                   'context_canonical_cycles[canonical_owner]<=canon_cycles;phase[canonical_owner]<=COPY;',
                   "if(copy_committed==(AW+1)'(N-1))begin",
                   'published[canonical_owner]<=1;done_q[canonical_owner]<=1;phase[canonical_owner]<=IDLE;canonical_owned<=0;'):
        need(host.count(anchor) == 1, 'OWN_PUBLICATION_ANCHOR:'+anchor)
    image = bundle['files']['genefer_stream27_canonical_image_loadlocal_v1.sv']
    need('three edges/digit, 9N normal / 10N special.' in image and
         'READ_WORD:state<=VALUE_WORD;' in image and 'SPECIAL_WRITE:begin' in image,
         'OWN_ORDINARY_SPECIAL_CANONICAL_SERVICE')
    index_raw = (ROOT/INDEX).read_bytes()
    need(sha(index_raw) == INDEX_PIN, 'IMMUTABLE_OWN_NUMERICAL_INDEX')
    index = json.loads(index_raw)
    need(index['production']['all55_generated_sha256'] == bundle['generated_sha256'] and
         index['production']['captured_bundle']['sha256'] == sha(capture_raw), 'INDEX_ALL55_CAPTURE_JOIN')
    aw8_entry = next((row for row in index['jobs'] if row['id'] == AW8_WRAP_ID), None)
    aw8_gate_raw = (ROOT/'queue/evidence'/AW8_WRAP_ID/'gate-receipt.json').read_bytes()
    aw8_gate = json.loads(aw8_gate_raw)
    need(aw8_entry is not None and aw8_entry['gate']['sha256'] == sha(aw8_gate_raw) and
         aw8_gate['id'] == AW8_WRAP_ID and aw8_gate['status'] == 'PASS_expected_contracts',
         'AW8_RESET_NEWJOB_ACCEPTED_WRAP_GATE_JOIN')
    references = []
    measured = {}
    for count,(identity,name,prefix) in JOBS.items():
        ref,report,manifest,native = native_join(identity,bundle,index)
        actual = read_footer(native,report,name,prefix)
        value = validate_footer(actual,count)
        ref['log_sha256'] = report['artifacts'][name]
        references.append(ref)
        measured[str(count)] = dict(warm_edges=value['warm_edges'],publication_edges=value['publication_edges'],
            joint_cycles=actual['joint_cycles'], launches_per_context=count,
            joint_squares=2*count, native_total_squares=actual['squares'],
            native_total_reads=actual['reads'], real_native=True)
    ref,report,manifest,native = native_join(WRAP_ID,bundle,index)
    meta = manifest['oneshot_full_wrap']
    need(meta['production_source_unchanged'] and meta['monitor_only_stateless_observer'] and
         meta['forced_value'] == 'host cycles64 only' and
         meta['protocol_arithmetic_payload_owner_time_unchanged'] and not meta['billions_of_edges_simulated'],
         'ACCELERATED_WRAP_NOT_REAL_PROTOCOL_TIME')
    wrapped = read_footer(native,report,WRAP_LOG,'R84_C2_FULL_PASS ')
    validate_footer(wrapped,2)
    raw = (native/WRAP_LOG).read_text()
    need('R6_FULL_WRAP_PASS aliases=3 cold_accepts=2 cache_events_per_field=4 reads=393216 masks=1/2/3 '
         'independent_reference=1 real_datapath_edges=1 simulation_only=1\n' in raw,
         'ACTUAL_ONE_COLD_ACCEPT_PER_CONTEXT_THREE_ALIASES')
    ref['log_sha256'] = report['artifacts'][WRAP_LOG]
    references.append(ref)
    sample = event_calendar(1911814)
    producer = own.calendar.sample()
    need(sample['pair_completion_cycles'] == producer['pair_completion_cycles'] == 16173357856 and
         sample['warm_edges'] == producer['warm_edges'] and
         sample['publication_edges'] == producer['publication_edges'], 'OWN_SAMPLE_EVENT_REDERIVATION')
    alias_edges = own.oneshot.prove_wraps(8232)['old_alias_edges']
    need(len([t for t in alias_edges if t <= sample['pair_completion_cycles']]) == 4,
         'THREE_SUPPRESSED_ALIASES_IN_SAMPLE')
    return dict(schema='r6-own-source-healthy-sample-join-v1',status='PASS_CYCLE_LEDGER_OWN_NATIVE_JOIN_CLOCK_NULL',
        producer=dict(path=PRODUCER,sha256=PRODUCER_PIN),
        arithmetic_reuse=dict(path=ARITHMETIC,sha256=ARITHMETIC_PIN,implementation_only_not_ancestor_qualification=True),
        numerical_index=dict(path=INDEX,sha256=INDEX_PIN),
        production=dict(top=bundle['top'],root_sha256=bundle['generated_sha256'][bundle['top']+'.sv'],
            bundle_sha256=sha(capture_raw),sv_count=55,source_own_all55_join=True),
        native_calendars=measured,native_references=references,sample=sample,
        aw8_reset_newjob_reference=dict(id=AW8_WRAP_ID,gate_sha256=sha(aw8_gate_raw)),
        accepted_second_cold_edge=8436,suppressed_old_alias_edges=alias_edges[1:],
        accepted_one_shot_noncolliding_healthy_trace=True,reset_newjob_clear_aw8_native_receipt_referenced_by_index=True,
        mandatory_full_geometry_accelerated_wrap_native_pass=True,
        selected_period_ns=None,projected_pair_seconds=None,projected_amortized_seconds=None,promotion_allowed=False,
        conditions=['Healthy legal profile/owners and timely descriptor feed; no host-induced gaps or fault injection.',
            'Equal-length ordinary pair; each special final image adds65536 service edges once.',
            'Profile/cold setup and one canonical/copy per job included; external load/readback/gaps/transport excluded.'],
        scope_limits=['Scalar full-sample source calendar, not measured full-sample PRP/board/runtime or individual-test latency.',
            'Accelerated wrap changes only host timestamp; no billions of real protocol/arithmetic edges.',
            'Wrap cache checks ctx/epoch/generation sequences, not a separate expected lease-bank oracle.',
            'Forced cold+automatic-correction collision retains original global abort; acceptance wording is healthy noncolliding only.',
            'Own cache fault scope is eventual duplicate-ready abort before publication, not first matching-token age detection.',
            'Own full-contract resets do not claim epoch-wrap reset; actual own1000 covers epoch wrap/ordinal999.',
            'No old C2 sample qualification or clock inherited; own physical audit/review/advisor remain pending.'])


if __name__ == '__main__':
    print(json.dumps(close(),indent=2))

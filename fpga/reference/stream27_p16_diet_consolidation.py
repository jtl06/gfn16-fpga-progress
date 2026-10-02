"""Original P16 diet author consolidation: metadata, trace and scalar ledger only.

Never imports candidate compilers, numerical/GMP references, HDL or vendor tools.
Automatic native receipts remain authoritative; non-author review is separate.
Prints a repeatable handoff without changing any captured/native evidence.
"""
import argparse
import ast
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import tarfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
FIT = 'artifacts/s4-p16-diet-whole-full-flow-v1/project'
FIT_PIN = '0bb3de71bd01332692ba83b81a0fadc18557596956cf40685d22cb0bda8fccb8'
TOP = 'genefer_stream27_host_chain_aw16_p16_diet_v1.sv'
TOP_PIN = 'b683cb1113a17652f5d6266c4298c5eb825c6af6b9f92bd28f758dba9b8de898'
PARAMETERS = dict(AW=16, P=16, CONTEXTS=1, EPOCH_SEED=65534,
    CORR_SERIAL_BFS=2, COMM_STAGE_SHARED_MLAB=1, MONT_FACTORED=1, CANONICAL_PIPE_STAGES=1)
LEDGERS = {
    'reference/stream27_host_chain_v1.py': '0ca7724092b7b93dfe5976f8dac023cf90aab7a483e877cc3f126acee04c3759',
    'reference/stream27_host_chain_param_v3.py': '017f581581d3f832cbb511a278901afb0a9a59ae6ed14a8df6234641634aa102',
}
REVIEWS = {
    'completed_subset': ('s4-p16-diet-completed-subset-independent-v1.json', '2bf7a35197fbfb2ce55b19fe4076cef0cb183e6ed969ab7d9da7579e6e36d1b1'),
    'routed_readiness': ('s4-p16-diet-routed-readiness-independent-v1.json', '32b51f3464fc5ce4069b0ed26bcb251b5dd11547c4bdda8009068b220c43a462'),
    'completed_long': ('s4-p16-diet-long-independent-v1.json', 'f8bb79493a1b0d59719d1b3ce043598340f98db43e14a9661f8ff39d6417c622'),
}
JOBS = {
    'full9_two_stopped_jobs': 's4-aw16-p16-diet-whole-normal-q1-v1',
    'eight_small_prps': 's4-p16-diet-eight-prp-normal-q1-v1',
    'cold_short': 's4-p16-diet-short-normal-q1-v1',
    'serial_continuous100': 's4-p16-diet-continuous100-normal-q1-v1',
    'aw8_dense_calendar': 's4-p16-diet-aw8-dense-normal-q1-v1',
    'whole_host_faults_and_special': 's4-p16-diet-whole-host-faults-q1-v1',
    'thread8_continuous100': 'r75-p16-diet-threads8-q1-v1',
    'thread8_continuous1000': 's4-p16-diet-continuous1000-thread8-normal-q1-v3',
}


def need(ok, message):
    if not ok:
        raise ValueError('P16_DIET_CONSOLIDATION_' + message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def ref(path, root=ROOT):
    return dict(path=path, sha256=sha((root/path).read_bytes()))


def digest(value):
    return sha(json.dumps(value, sort_keys=True).encode())


def source_cycles(n, geometry, count, cache_hit=False, special=False, root=ROOT):
    """Execute only two source-pinned scalar function ASTs, not their imports."""
    functions = []
    for path, pin in LEDGERS.items():
        raw = (root/path).read_bytes()
        need(sha(raw) == pin, 'LEDGER_SOURCE_DRIFT')
        nodes = [x for x in ast.parse(raw).body if isinstance(x, ast.FunctionDef) and x.name == 'cycle_contract']
        need(len(nodes) == 1, 'LEDGER_FUNCTION')
        functions.append(nodes[0])
    ns = {}
    exec(compile(ast.Module(body=[functions[0]], type_ignores=[]), '[frozen scalar ledger]', 'exec'), ns)
    ns['ledger'] = SimpleNamespace(cycle_contract=ns['cycle_contract'])
    exec(compile(ast.Module(body=[functions[1]], type_ignores=[]), '[frozen canonical delta]', 'exec'), ns)
    return ns['cycle_contract'](n, geometry, count=count, cache_hit=cache_hit,
                                special=special, canonical_pipe_stages=1)


def sample_ledger(root=ROOT):
    n, base, k = 65536, 604832956, 1911814
    need(math.floor(n*math.log2(base))+1 == k, 'LEADING_BIT_COUNT')
    geometry = dict(warm_interval=8459, carry_done=12557)
    cold = source_cycles(n, geometry, k, root=root)['host_done']
    cached = source_cycles(n, geometry, k, True, root=root)['host_done']
    special = source_cycles(n, geometry, k, False, True, root=root)['host_done']
    need((cold, cached) == (16172694192, 16172694093), 'SAMPLE_CYCLES')
    need(cold-cached == 99 and special-cold == n, 'ROOT_SPECIAL_DELTA')
    finite = {str(count): source_cycles(n, geometry, count, root=root)['host_done'] for count in (1, 100, 1000)}
    need(finite == {'1': 668025, '100': 1505466, '1000': 9118566}, 'FINITE_CALENDARS')
    return dict(n=n, p=16, base=base, operations=k,
        bit_convention='K=floor(N*log2(base))+1 includes leading exponent bit; PRP starts x0=1 and squares then optionally doubles each bit. This full-size sample PRP was not executed.',
        cold_primary_cycles=cold, cached_alternate_cycles=cached,
        cold_first=102, cached_first=3, cold_root_extra=99,
        warm_interval=8459, carry_done=12557, cold_ordinary_completion=668025,
        cached_ordinary_completion=667926, finite_native_cycles=finite,
        canonical_normal_cycles=9*n, canonical_special_cycles=10*n, copy_cycles=n+3,
        canonical_and_copy_occurrences=1, special_alternate_extra_cycles=n,
        equation='102 + (1911814-1)*8459 + 12557 + 2 + 9*65536 + 65536 + 4',
        seconds_per_ns=str(Decimal(cold)/Decimal(10**9)),
        selected_period_ns=None, selected_frequency_mhz=None, projected_seconds=None,
        clock_status='UNQUALIFIED: no selected passing whole-layout audit in this snapshot',
        scope='Source-ledger compute-only input, not elapsed simulation, full PRP or board time. Cold setup and ordinary final publication/copy once included; initial host load, final readback, transport gaps and board I/O excluded.',
        sources=[ref(path, root) for path in LEDGERS])


def native(job, root=ROOT):
    base = 'queue/evidence/'+job
    directory = base+'/attempt-0/collected/output/native'
    gate = json.loads((root/base/'gate-receipt.json').read_text())
    report = json.loads((root/directory/'report.json').read_text())
    manifest = json.loads((root/directory/'approved-manifest.json').read_text())
    need(gate['status'] == 'PASS_expected_contracts' and gate['id'] == job, 'GATE:'+job)
    need(gate['report_sha256'] == ref(directory+'/report.json', root)['sha256'], 'REPORT:'+job)
    need(gate['manifest_sha256'] == ref(directory+'/approved-manifest.json', root)['sha256'] == report['manifest_sha256'], 'MANIFEST:'+job)
    need(report['sources'] == manifest['sources'], 'SOURCE_MAP:'+job)
    rtl = {PurePosixPath(name).name: manifest['sources'][name] for name in manifest['build']['sv_sources']}
    return dict(id=job, gate=ref(base+'/gate-receipt.json', root),
        report=ref(directory+'/report.json', root), manifest=ref(directory+'/approved-manifest.json', root),
        rtl_count=len(rtl), rtl_map_sha256=digest(rtl), host=report['host'], model_threads=report['model_threads'],
        overall_seconds=report['seconds'], typed_results=gate['steps']), manifest, report, rtl


def trace(report, manifest, root=ROOT):
    """Check retained ordinal/calendar/footer; no numerical reference invocation."""
    step = report['steps'][-1]
    directory = 'queue/evidence/'+JOBS['thread8_continuous1000']+'/attempt-0/collected/output/native'
    raw = (root/directory/step['log']).read_bytes()
    need(sha(raw) == step['sha256'] and step['returncode'] == 0, 'LONG_LOG')
    lines = raw.decode().splitlines(); need(len(lines) == 1001, 'LONG_TRACE_LENGTH')
    plan = manifest['continuous']['plan']; bits = plan['double_bits']
    need(len(bits) == 1000 and bits.count('1') == 500 and plan['candidate_root_sha256'] == TOP_PIN, 'LONG_PLAN')
    # Difference comes from the actual first two pops, independently of sample arithmetic.
    rows = []
    for line in lines[:999]:
        prefix, value = line.split(' ', 1); need(prefix == 'S4_CONTINUOUS_POP', 'TRACE_PREFIX')
        rows.append(json.loads(value))
    interval = rows[1]['age']-rows[0]['age']; cold_first = rows[0]['age']-interval
    need((interval, cold_first) == (8459, 102), 'DIRECT_CALENDAR')
    for index, row in enumerate(rows, 1):
        need(row == dict(index=index, age=cold_first+index*interval, bit=int(bits[index])), 'TRACE_ORDINAL')
    need(lines[999].startswith('S4_CONTINUOUS_IMAGE ') and lines[1000].startswith('S4_CONTINUOUS_PASS '), 'TRACE_FINAL')
    footer = json.loads(lines[-1].split(' ', 1)[1])
    expected = manifest['continuous']['counts_ordinary_source_projection']
    need({key: footer[key] for key in expected} == expected, 'FOOTER_COUNTERS')
    need(footer['candidate_cycles'] == source_cycles(65536, dict(warm_interval=interval, carry_done=12557), 1000, root=root)['host_done'], 'DIRECT_COLD_COMPLETION')
    return dict(log=ref(directory+'/'+step['log'], root), operations=1000, accepted_pop_rows=999,
        directly_observed_interval=interval, directly_observed_cold_first=cold_first,
        cold_completion_from_trace=footer['candidate_cycles']-999*interval,
        footer=footer, numerical_recompute=False)


def consolidate(root=ROOT):
    fitted = json.loads((root/FIT/'manifest.json').read_text())
    need(ref(FIT+'/manifest.json', root)['sha256'] == FIT_PIN and fitted['core_parameters'] == PARAMETERS, 'FIT_BINDING')
    sources = fitted['source_sha256']; need(len(sources) == 58 and sources[TOP] == TOP_PIN, 'FIT58')
    for name, pin in sources.items():
        need(sha((root/FIT/'rtl'/name).read_bytes()) == pin, 'FIT_RTL:'+name)
    reviews = {}; review_data = {}
    for kind, (name, pin) in REVIEWS.items():
        path = 'results/throughput-20260929/'+name
        need(ref(path, root)['sha256'] == pin, 'REVIEW_PIN')
        reviews[kind] = ref(path, root); review_data[kind] = json.loads((root/path).read_text())
    ready = review_data['routed_readiness']
    need(ready['physical']['source_pins'] == sources and ready['physical']['parameters'] == PARAMETERS, 'ROUTED58_JOIN')
    entries = []; full = {}
    for role, job in JOBS.items():
        entry, manifest, report, rtl = native(job, root); entry['role'] = role
        if role in ('full9_two_stopped_jobs', 'cold_short', 'serial_continuous100', 'thread8_continuous100', 'thread8_continuous1000'):
            need(len(rtl) == 69 and all(rtl.get(name) == pin for name, pin in sources.items()), 'FULL69_JOIN:'+job)
            full[role] = (manifest, report, rtl)
        entries.append(entry)
    field_entries = []
    for aw, fields in ((5, (0, 1, 2)), (8, (0, 1, 2)), (16, (0,))):
        for field in fields:
            job = f's4-diet-field-aw{aw}-p16-f{field}-normal-q1-v1'
            entry, manifest, _, _ = native(job, root)
            need(manifest['build']['parameters'] == dict(AW=aw, P=16, CONTEXTS=1,
                CORR_SERIAL_BFS=2, COMM_STAGE_SHARED_MLAB=1, MONT_FACTORED=1), 'FIELD_FLAGS')
            meta = manifest['correction_serial']
            entry.update(field=field, address_width=aw, counts=meta['counts'],
                own_calendar={key: meta['geometry'][key] for key in ('first_digit', 'warm_interval', 'carry_done', 'feedback_fifo_rows')},
                scope='One-field component equality/calendar evidence only; the exact three-field whole source join is separate.')
            field_entries.append(entry)
    long, report, rtl = full['thread8_continuous1000']
    need(report['probe'] == dict(context_threads=8, model_threads=8, expected_threads=8), 'PROBE8')
    long_entry = next(x for x in entries if x['role'] == 'thread8_continuous1000')
    validation = long_entry['typed_results'][0]['validation']; counts = validation['counts']
    need(validation['independent_reference_equal'] and validation['uninterrupted_1000_native'] and
         validation['final_actual_sha256'] == validation['final_expected_sha256'], 'FINAL_NUMERICAL_BINDING')
    need(counts['candidate_cycles'] == 9118566 and counts['operations'] == 1000 and counts['doubles'] == 500 and
         counts['signed96_words'] == 65536 and all(counts[key] == 1 for key in ('resets','loads','starts','readbacks')), 'LONG_CONTINUITY')
    cpp = 'rtl/tb/stream27_p16_diet_full_native.cpp'
    full9 = full['full9_two_stopped_jobs'][0]
    with tarfile.open(root/'queue/evidence'/JOBS['full9_two_stopped_jobs']/'attempt-0/collected/output/native/sources.tar.gz') as archive:
        raw = archive.extractfile(cpp).read()
    need(sha(raw) == full9['sources'][cpp] and b'(hit?3u:102u)+uint64_t(count-1)*INTERVAL+CARRY_DONE+2+(special?10u:9u)*N+N+4' in raw, 'OWN_COLD_CACHED_LEDGER')
    history = []
    for version in (1, 2):
        path = 'queue/done/s4-p16-diet-continuous1000-thread8-normal-q1-v'+str(version)+'.json'
        old = json.loads((root/path).read_text())
        history.append(dict(receipt=ref(path, root), status=old['result']['status'], scope='Preserved infrastructure failure before lint/build/model; not a numerical retry.'))
    return dict(schema='stream27-p16-diet-author-consolidation-v1',
        status='AUTHOR_NUMERICAL_LADDER_COMPLETE_CLOCK_UNQUALIFIED_PROMOTION_PENDING', promotion_allowed=False,
        producer=ref('reference/stream27_p16_diet_consolidation.py', root), author_tests=ref('tests/test_stream27_p16_diet_consolidation.py', root),
        candidate='Original baseline P16 diet, contexts1, canonical1; not timing7 or P8', root_sha256=TOP_PIN,
        source_binding=dict(original_fit=ref(FIT+'/manifest.json', root), parameters=PARAMETERS,
            standalone58_map_sha256=digest(sources), paired69_map_sha256=digest(rtl), exact58_subset_of69=True,
            own_full9_cpp_sha256=full9['sources'][cpp], continuous_cpp_sha256=long['sources'][long['build']['cpp_source']],
            continuous_header_sha256=long['sources']['rtl/tb/stream27_s4_continuous_config_v1.h']),
        existing_independent_reviews=reviews, receipt_index=entries, field_receipt_index=field_entries,
        completed_subset_counts=review_data['completed_subset']['results'], direct_long_trace=trace(report, long, root),
        sample_ledger=sample_ledger(root), routed_resources=ready['resources'], original_9ns_target=ready['actual_9ns_target'],
        selected_passing_period_ns=None, projected_sample_seconds=None,
        preserved_infrastructure_failures=history,
        remaining=['Non-author source-specific consolidated projection review', 'Passing saved-layout whole timing audit, if obtained', 'Advisor verification and explicit adoption'],
        scope_limits=['Own small PRPs exercise N32 and own AW8 dense calendar exercises N256; full-size sample PRP not executed.',
            'Full1000 is one dense signed mixed square/double FIFO chain with final-only publication/readback, not the complete sample PRP.',
            'Simulation wall/CPU/RAM do not establish FPGA MHz; selected clock and projection seconds are deliberately null.',
            'No baseline forecast or numerical result inherited by timing7; unlike-host serial/wide observations are not causal thread speedup.',
            'Author metadata/trace consolidation is not independent promotion review.'],
        method='Read-only source/typed-receipt joins and retained control trace plus exact frozen scalar ledger ASTs; no GMP/full-N numerical/HDL/vendor rerun.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    print(json.dumps(consolidate(parser.parse_args().root), sort_keys=True, indent=2))

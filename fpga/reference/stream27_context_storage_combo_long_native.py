"""Combined C2 own continuous pilot; no inherited runtime forecast."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
DONOR_BASE = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-native-v1'
BASE = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-ownlong-v1'
SELF = 'reference/stream27_context_storage_combo_long_native.py'
CPP = 'rtl/tb/stream27_p16_two_context_threadpilot.cpp'
HEADER = 'rtl/tb/s4_p16_two_context_full_config.h'
CPP_PIN = '0121cc93bb708e8ad2b40a3ca939aa9b2dee15393a5d7e23f49b9823ac8e8ade'
MANIFEST_PIN = 'fb3a56a95f0616c3a8b6799088ca37a1c477cc1fa274e3c7821fc75c60c8c437'
BUNDLE_PIN = '02549331f1751a55e94409bb897c89a64df33834680901010dc15ff6e57629e9'
GATE_ID = 's4-p16-c2-combo-full-normal-q1-v1'
READY = '2026-10-02T09:13:02Z'
BASES = [604832956, 999999937]


def need(ok, why):
    if not ok:
        raise ValueError('C2_COMBO_LONG_' + why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def bits(count=100):
    need(type(count) is int and count in (100, 1000), 'FINITE_COUNT')
    rows = []
    for ctx, seed in enumerate((0x1732f5a9, 0x7b28c361)):
        row, state = [ctx], seed
        for _ in range(1, count):
            state ^= (state << 13) & 0xffffffff
            state ^= state >> 17
            state ^= (state << 5) & 0xffffffff
            row.append(state & 1)
        rows.append(row)
    return rows


def config(count=100, threads=1):
    need(type(threads) is int and threads == 1, 'REAL_HOST_THREADS')
    return dict(aw=16, p=16, contexts=2, bases=BASES, count=count, threads=threads,
                doubles=sum(map(sum, bits(count))), interval=8459, carry_done=12557,
                joint_first_edges=[204, 4433])


def validate(stdout, stderr, rc, config, assets):
    count, threads = config.get('count'), config.get('threads')
    need(config == globals()['config'](count, threads) and assets == {}, 'CONFIG')
    need(type(rc) is int and rc == 0 and stderr == '' and stdout.startswith('R84_C2_THREAD100_PASS ')
         and stdout.endswith('\n') and '\n' not in stdout[:-1], 'TYPED_NORMAL')
    value = json.loads(stdout.removeprefix('R84_C2_THREAD100_PASS '))
    expected = dict(aw=16, p=16, contexts=2, bases=BASES, count_per_context=count, squares=2 * count,
        descriptors=2 * (count - 1), doubles=config['doubles'], reads=262144, signed96=True,
        independent_reference=True, initial_resets=1, initial_load_words=131072,
        interval=8459, peer_live_reads=65536, model_threads=threads)
    variable = {'launches', 'joint_cycles', 'overlap_edges', 'done_edges', 'warm_edges', 'setup_edges',
                'reference_seconds', 'model_seconds', 'seconds'}
    need(set(value) == set(expected) | variable and all(value[k] == v and type(value[k]) is type(v)
         for k, v in expected.items()), 'EXACT_COUNTS')
    need(value['launches'] == [[204 + k * 8459 for k in range(count)],
                               [4433 + k * 8459 for k in range(count)]], 'ALL_LAUNCH_EDGES')
    for name in ('done_edges', 'warm_edges', 'setup_edges'):
        need(type(value[name]) is list and len(value[name]) == 2
             and all(type(x) is int and x > 0 for x in value[name]), 'EDGE_PAIR')
    need(value['setup_edges'] == [99, 199] and value['warm_edges'] == [row[-1] + 12558 for row in value['launches']]
         and all(value['done_edges'][c] > value['warm_edges'][c] + 655360 for c in (0, 1)), 'PUBLICATION')
    release = -1
    expected_done = []
    for warm in value['warm_edges']:
        release = max(warm + 2, release + 1) + 4096 + 10 * 65536 + 6
        expected_done.append(release)
    need(value['done_edges'] == expected_done and value['joint_cycles'] == release + 65536,
         'ORIGINAL_EXACT_PUBLICATION_LEDGER')
    need(type(value['joint_cycles']) is int and max(value['done_edges']) + 65536 <= value['joint_cycles']
         < count * 8459 + 33 * 65536 + 100000 and type(value['overlap_edges']) is int
         and value['overlap_edges'] > 0, 'FINITE_CONTINUOUS_MODEL')
    limit = 1800 if count == 100 else 10450
    need(all(type(value[k]) in (int, float) and math.isfinite(value[k]) and 0 < value[k] < limit
         for k in ('reference_seconds', 'model_seconds', 'seconds')), 'FINITE_PHASES')
    need(abs(value['reference_seconds'] + value['model_seconds'] - value['seconds']) < .05, 'PHASE_SUM')
    return dict(status='PASS_expected_contracts', measurements=value, promotion_allowed=False,
        scope='Own combined C2 continuous source and recorded serial allocation; no prior forecast, clock, area or hardware qualification.')


def calendar(g, count):
    from fpga.reference import s4_two_context_model_v1 as ports
    need(count in (100, 1000) and g['warm_interval'] == g['first_digit'] + 1 == 8459
         and g['carry_done'] == 12557 and g['feedback_delay'] == 0, 'ORIGINAL_DIRECT_FEEDBACK')
    frames = sorted([ports.Frame(c, 1, ((65534, 42)[c] + k) & 65535, k,
                                  k * 8459 + c * 4229, BASES[c])
                     for c in (0, 1) for k in range(count)], key=lambda f: f.start)
    for label, first, width in (('INPUT', 0, g['rows']), ('PW', g['pointwise_accept'], g['rows']),
        ('SINK', g['sink_accept'], g['rows']), ('DIGIT', g['first_digit'], g['rows']),
        ('CARRY', g['sink_accept'], g['carry_done'] - g['sink_accept'] + 1)):
        ports.disjoint([(f.start + first, f.start + first + width - 1, f.tag) for f in frames], label)
    correction = ports.correction_calendar(frames, g, pair_interval=g['correction_pair_interval'])
    live, peak, allocation = {}, 0, []
    for frame in frames:
        live = {bank: old for bank, old in live.items() if old.start + g['last_sink'] >= frame.start}
        free = [bank for bank in range(4) if bank not in live]
        need(bool(free), 'PREFREE_FOUR_LOGICAL_LEASES')
        bank = free[0]
        live[bank] = frame
        peak = max(peak, len(live))
        allocation.append([frame.context, frame.ordinal, frame.start, bank])
    return dict(status='PASS_SOURCE_EDGE_MODEL_ONLY', frames=2 * count, per_context_interval=8459,
        launch_gaps=[4229, 4230], correction=correction, lease_allocation=allocation, lease_peak=peak,
        feedback_peak_rows=[0, 0], feedback_identity='previous_start+FIRST_DIGIT+1+r == next_start+r',
        full_N_numeric_performed=False, runtime_forecast=False)


def role(count=100, threads=1):
    """Load frozen qualified source; only driver/header/native validator change."""
    directory = DONOR_BASE / 'full-normal'
    raw = (directory / 'manifest.json').read_bytes()
    need(sha(raw) == MANIFEST_PIN and sha((directory / 'production-bundle.json').read_bytes()) == BUNDLE_PIN,
         'FROZEN_DONOR')
    # Prepare ahead; the public queue enforces this real normal prerequisite.
    manifest = json.loads(raw)
    files = {name: (directory / 'source/fpga' / name).read_bytes() for name in manifest['sources']}
    need(all(sha(files[name]) == pin for name, pin in manifest['sources'].items()), 'SOURCE_PINS')
    rtl = {name: pin for name, pin in manifest['sources'].items() if name.endswith('.sv')}
    need(len(manifest['build']['sv_sources']) == 54
         and all(name in rtl for name in manifest['build']['sv_sources']), 'PRODUCTION53_OBSERVER1')
    cpp = ROOT / 'artifacts/s4-p16-c2-explicit-own100-threadpilot-v1/source/fpga' / CPP
    need(sha(cpp.read_bytes()) == CPP_PIN, 'DESCRIPTOR_CPP')
    files[CPP] = cpp.read_bytes()
    text = files[HEADER].decode()
    need(text.count('COUNT=2,INTERVAL') == 1 and text.count('MAX_EDGES=3*11ull*N+100000') == 1, 'HEADER')
    text = text.replace('COUNT=2,INTERVAL', f'COUNT={count},INTERVAL', 1)
    text = text.replace('MAX_EDGES=3*11ull*N+100000', 'MAX_EDGES=COUNT*uint64_t(INTERVAL)+3*11ull*N+100000', 1)
    text = text[:text.index('BITS[2][2]=')] + 'BITS[2][COUNT]={' + ','.join(
        '{' + ','.join(map(str, row)) + '}' for row in bits(count)) + '};\n'
    need('INTERVAL=8459,FIRST_DIGIT=8458,CARRY_DONE=12557' in text, 'OWN_CALENDAR_HEADER')
    files[HEADER] = text.encode()
    files[SELF] = (ROOT / SELF).read_bytes()
    manifest['build']['cpp_source'] = CPP
    manifest['build']['runtime_threads'] = threads
    manifest['steps'] = [dict(name=f'normal-full-c2-combo-own{count}-percontext', argv=['{exe}'],
        expected_returncode=0, validator=dict(source=SELF, function='validate', config=config(count, threads), assets={}))]
    manifest['sources'] = {name: sha(data) for name, data in files.items()}
    need(rtl == {name: pin for name, pin in manifest['sources'].items() if name.endswith('.sv')}, 'UNCHANGED_COMBINED_RTL')
    geometry = manifest['storage2']['geometry']
    manifest['context_storage_combo']['own_long'] = dict(count_per_context=count, threads=threads,
        actual_normal_gate=GATE_ID, own_calendar=calendar(geometry, count), normal_cpp_donor_pin=CPP_PIN,
        feed_mode=True, initial_resets=1, initial_load_words=131072, descriptors=2 * (count - 1),
        reference_phase_joins_checked=True, no_reset_reload_barrier=True,
        prior_forecast_used=False, full_N_numeric_locally_performed=False, native_result=False)
    manifest['rtl_readiness']['candidate_id'] = f's4-p16-c2-combo-own{count}-v1'
    need(manifest['rtl_readiness']['rtl_ready_at_utc'] == READY, 'ORIGINAL_READINESS')
    return deepcopy(manifest), files


def prepare_role(output, count=100, threads=1):
    """Source-only emission; execution allocation belongs to existing launcher."""
    out = Path(output).resolve()
    need(out.is_relative_to(BASE) and not out.exists(), 'FRESH_OUTPUT')
    manifest, files = role(count, threads)
    source = out / 'source/fpga'
    source.mkdir(parents=True)
    for name, raw in files.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    manifest['source_root'] = str(source)
    with (out / 'manifest.json').open('x') as stream:
        json.dump(manifest, stream, indent=2)
        stream.write('\n')
    return dict(status='SOURCE_READY_NOT_NATIVE_NOT_SUBMITTED', manifest=str(out / 'manifest.json'),
                count_per_context=count, threads=threads, prior_forecast_used=False)


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def prepare_serial_pilot(output):
    """Use admitted GCP serial pairs, not the deallocated Azure wide profile."""
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    out = Path(output).resolve()
    need(not any((ROOT / p).exists() for p in ('queue/PAUSE', 'docs/briefs/PAUSE')), 'PAUSE')
    prepare_role(out, 100, 1)
    path, source = out / 'manifest.json', out / 'source/fpga'
    manifest = json.loads(path.read_bytes())
    dump(out / 'host-hours.json', candidate_ladder.budget_from_hourly())
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static' + pair + '-v1'
        worker = 's4-p16-c2-combo-own100-' + pair + '-v1'
        packet = out / ('packet-' + pair)
        result = package.prepare(path, source, profile, worker, 'run', packet, out / 'host-hours.json')
        ticket = json.loads((packet / 'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet / 'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet / 'manifest.json').read_bytes()),
            worker_id=worker, profile=profile, native_root=ticket['native_root'], runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT / 'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT / 'tools/native_package_v4.py'), stager_sha256=sha((ROOT / 'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT / name), sha256=sha((ROOT / name).read_bytes()))
                for name in ('tools/native_package_v3.py', 'tools/native_package_v2.py')], max_seconds=3700))
    logical = dict(schema='gfn16-global-ticket-v1', id='s4-p16-c2-combo-own100-serial-q1-v1', owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P1', kind='sim',
        needs='verilator', tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4), minimum_ram_gib=8,
        minimum_ram_rationale='Own source-bound serial pilot within admitted GCP pair; no prior measured duration inherited.',
        est_minutes=35, promotion_bound=False, test_role='normal', rtl_readiness=manifest['rtl_readiness'], packages=variants,
        after=[GATE_ID], on='PASS_expected_contracts')
    dump(out / 'global-ticket.json', logical)
    return dict(id=logical['id'], ticket=str(out / 'global-ticket.json'), status='PREPARED_NOT_SUBMITTED', threads=1)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_serial_pilot(args.output), indent=2))

"""Own timing58 C2 eight-thread100 pilot and source-only1000 successor.

No full-N arithmetic locally. The immutable continuous C++ donor is unchanged;
the timing cohort supplies its own RTL, profile observer, I8460 and measurements.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/throughput-20260929/trackS-c2-timing-v1'
SELF = 'reference/stream27_context_timing_long_native.py'
CPP = 'rtl/tb/stream27_p16_two_context_threadpilot.cpp'
HEADER = 'rtl/tb/s4_p16_two_context_full_config.h'
CPP_PIN = '0121cc93bb708e8ad2b40a3ca939aa9b2dee15393a5d7e23f49b9823ac8e8ade'
READY = '2026-10-02T05:26:55Z'
BASES = [604832956, 999999937]
PILOT_ID = 's4-p16-c2-timing-own100-threadpilot-q1-v1'
PILOT_STEP = 'normal-full-c2-timing-own100-percontext-threadpilot'
LONG_STEP = 'normal-full-c2-timing-continuous1000-percontext'
SCHEMA = 'stream27-p16-c2-measured-continuous-forecast-v1'
SHAPE = dict(model_command_seconds=10450, overall_seconds=10700, outer_seconds=10800, stop_grace_seconds=15)


def need(ok, why):
    if not ok:
        raise ValueError('C2_TIMING_LONG_' + why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def bits(count=1000):
    need(type(count) is int and count in (100, 1000), 'FINITE_COUNT')
    result = []
    for ctx, seed in enumerate((0x1732f5a9, 0x7b28c361)):
        row, state = [ctx], seed
        for _ in range(1, count):
            state ^= (state << 13) & 0xffffffff
            state ^= state >> 17
            state ^= (state << 5) & 0xffffffff
            row.append(state & 1)
        result.append(row)
    return result


def config(count=1000):
    return dict(aw=16, p=16, contexts=2, bases=BASES, count=count, threads=8,
                doubles=sum(map(sum, bits(count))), interval=8460, carry_done=12558,
                joint_first_edges=[204, 4434])


def validate(stdout, stderr, rc, config, assets):
    count = config.get('count')
    need(config == globals()['config'](count) and assets == {}, 'CONFIG')
    need(type(rc) is int and rc == 0 and stderr == '' and stdout.startswith('R84_C2_THREAD100_PASS ')
         and stdout.endswith('\n') and '\n' not in stdout[:-1], 'TYPED_NORMAL')
    value = json.loads(stdout.removeprefix('R84_C2_THREAD100_PASS '))
    expected = dict(aw=16, p=16, contexts=2, bases=BASES, count_per_context=count, squares=2 * count,
        descriptors=2 * (count - 1), doubles=config['doubles'], reads=4 * 65536, signed96=True,
        independent_reference=True, initial_resets=1, initial_load_words=2 * 65536, interval=8460,
        peer_live_reads=65536, model_threads=8)
    variable = {'launches', 'joint_cycles', 'overlap_edges', 'done_edges', 'warm_edges', 'setup_edges',
                'reference_seconds', 'model_seconds', 'seconds'}
    need(set(value) == set(expected) | variable and all(value[k] == v and type(value[k]) is type(v)
         for k, v in expected.items()), 'EXACT_COUNTS')
    need(value['launches'] == [[204 + k * 8460 for k in range(count)],
                               [4434 + k * 8460 for k in range(count)]], 'ALL_FIRST_AND_PERIODIC_EDGES')
    for name in ('done_edges', 'warm_edges', 'setup_edges'):
        need(type(value[name]) is list and len(value[name]) == 2
             and all(type(x) is int and x > 0 for x in value[name]), 'EDGE_PAIR')
    need(value['setup_edges'] == [99, 199] and value['warm_edges'] == [row[-1] + 12559 for row in value['launches']]
         and all(value['done_edges'][c] > value['warm_edges'][c] + 10 * 65536 for c in (0, 1)), 'FINAL_PUBLICATION')
    need(type(value['joint_cycles']) is int and max(value['done_edges']) + 65536 <= value['joint_cycles']
         < count * 8460 + 33 * 65536 + 100000 and type(value['overlap_edges']) is int
         and value['overlap_edges'] > 0, 'FINITE_CONTINUOUS_MODEL')
    limit = 1800 if count == 100 else SHAPE['model_command_seconds']
    need(all(type(value[k]) in (int, float) and math.isfinite(value[k]) and 0 < value[k] < limit
         for k in ('reference_seconds', 'model_seconds', 'seconds')), 'FINITE_PHASES')
    need(abs(value['reference_seconds'] + value['model_seconds'] - value['seconds']) < .05, 'PHASE_SUM')
    return dict(status='PASS_expected_contracts', measurements=value, promotion_allowed=False,
        scope='Own timing58 C2 uninterrupted chain, full native independent reference; no prior C2 duration, wholeclock or area inherited.')


def calendar(g, count):
    from fpga.reference import s4_two_context_model_v1 as ports
    need(count in (100, 1000) and g['warm_interval'] == g['first_digit'] + 1 == 8460
         and g['feedback_delay'] == 0, 'OWN_DIRECT_FEEDBACK')
    frames = sorted([ports.Frame(c, 1, ((65534, 42)[c] + k) & 65535, k,
                                  k * 8460 + c * 4230, BASES[c])
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
        need(bool(free), 'PREFREE_FOUR_LEASES')
        bank = free[0]
        live[bank] = frame
        peak = max(peak, len(live))
        allocation.append([frame.context, frame.ordinal, frame.start, bank])
    return dict(status='PASS_SOURCE_EDGE_MODEL_ONLY', frames=2 * count, per_context_interval=8460,
        launch_gaps=[4230, 4230], correction=correction, lease_allocation=allocation, lease_peak=peak,
        feedback_peak_rows=[0, 0], feedback_identity='previous_start+FIRST_DIGIT+1+r == next_start+r',
        full_N_numeric_performed=False, runtime_forecast=False)


def role(count=100):
    need(count in (100, 1000), 'ROLE_COUNT')
    directory = BASE / 'full-normal-v1'
    manifest = json.loads((directory / 'manifest.json').read_text())
    gate = json.loads((ROOT / 'queue/evidence/s4-p16-c2-timing-full-normal-q1-v1/gate-receipt.json').read_text())
    need(gate['status'] == 'PASS_expected_contracts', 'ACTUAL_OWN_FULL_NORMAL')
    files = {name: (directory / 'source/fpga' / name).read_bytes() for name in manifest['sources']}
    need(all(sha(files[name]) == pin for name, pin in manifest['sources'].items()), 'EXACT_OWN_FROZEN_NORMAL')
    old_rtl = {name: pin for name, pin in manifest['sources'].items() if name.endswith('.sv')}
    donor = ROOT / 'artifacts/s4-p16-c2-explicit-own100-threadpilot-v1/source/fpga' / CPP
    raw = donor.read_bytes()
    need(sha(raw) == CPP_PIN, 'EXACT_CONTINUOUS_CPP')
    files[CPP] = raw
    text = files[HEADER].decode()
    need(text.count('COUNT=2,INTERVAL') == 1 and text.count('MAX_EDGES=3*11ull*N+100000') == 1,
         'EXACT_NORMAL_COUNT_HEADER')
    text = text.replace('COUNT=2,INTERVAL', f'COUNT={count},INTERVAL', 1)
    text = text.replace('MAX_EDGES=3*11ull*N+100000', 'MAX_EDGES=COUNT*uint64_t(INTERVAL)+3*11ull*N+100000', 1)
    begin = text.index('BITS[2][2]=')
    text = text[:begin] + 'BITS[2][COUNT]={' + ','.join('{' + ','.join(map(str, row)) + '}' for row in bits(count)) + '};\n'
    need('INTERVAL=8460,FIRST_DIGIT=8459,CARRY_DONE=12558' in text, 'SOURCE_TIMING_HEADER')
    files[HEADER] = text.encode()
    files[SELF] = (ROOT / SELF).read_bytes()
    manifest['build']['cpp_source'] = CPP
    manifest['build'].pop('runtime_threads', None)
    manifest['steps'] = [dict(name=PILOT_STEP if count == 100 else LONG_STEP, argv=['{exe}'],
        expected_returncode=0, validator=dict(source=SELF, function='validate', config=config(count), assets={}))]
    manifest['sources'] = {name: sha(data) for name, data in files.items()}
    need(old_rtl == {name: pin for name, pin in manifest['sources'].items() if name.endswith('.sv')}, 'UNCHANGED59_RTL')
    manifest['context_timing']['own_long'] = dict(count_per_context=count, threads=8, feed_mode=True,
        actual_own_normal_gate=str(ROOT / 'queue/evidence/s4-p16-c2-timing-full-normal-q1-v1/gate-receipt.json'),
        own_calendar=calendar(manifest['context_timing']['calendar']['geometry'], count),
        normal_cpp_donor_pin=CPP_PIN, reference_phase_joins_checked=True, initial_resets=1,
        initial_load_words=131072, descriptors=2 * (count - 1), no_reset_reload_barrier=True,
        old_pilot_forecast_used=False, source_count_only_not_native=True, full_N_numeric_locally_performed=False)
    manifest['rtl_readiness']['candidate_id'] = f's4-p16-c2-timing-own{count}-v1'
    manifest['rtl_readiness']['rtl_ready_at_utc'] = READY
    return manifest, files


def prepare_pilot(output):
    from fpga.tools import native_threaded_wide_package_v3 as package
    from fpga.tools import native_thread_config_v1 as runtime
    from fpga.tools import global_queue_v1 as queue
    out = Path(output).resolve()
    need(out.is_relative_to(BASE) and not out.exists(), 'FRESH_PILOT_OUTPUT')
    need(not any((ROOT / name).exists() for name in ('queue/PAUSE', 'docs/briefs/PAUSE')), 'PAUSE')
    original, files = role(100)
    source = out / 'source/fpga'
    source.mkdir(parents=True)
    for name, raw in files.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    profile_id = 'azure-burst16-thread-wide815-v1'
    profile = package.runtime().profile(profile_id)
    manifest = deepcopy(original)
    manifest['build'] = runtime.configure_build(manifest['build'], 8)
    manifest['probe']['expected_json'] = runtime.expected_probe(8)
    serial = {key: deepcopy(original[key]) for key in ('build', 'probe', 'steps', 'sources')}
    manifest['wide_thread_pilot'] = dict(schema='gfn16-fixed-wide-thread-pilot-role-v1', thread_count=8,
        fixed_profile=profile_id, placement=profile['fixed_placement'],
        purpose='Own timing58/I8460 source/thread100 percontext pilot',
        serial_contract=serial, serial_contract_sha256=sha(canonical(serial)))
    path = out / 'manifest-815.json'
    dump(path, manifest)
    reference = queue.provider_capture_ref()
    budget = package.meter().make_budget(profile['host'], 3715,
        str(Path(reference['path']).relative_to(ROOT)), reference['sha256'], package.source_identity(manifest),
        profile['hardware_profile_sha256'],
        transition_path='results/throughput-20260929/azure-sim-resize-r49-v1/rate-transition-v1.json',
        transition_sha256='c4923266e1fabaeeca7cbf6e5f2444455c299accf5ed89c122927c47ed56ac92')
    dump(out / 'budget-815.json', budget)
    packet = out / 'packet-815'
    worker = 's4-p16-c2-timing-own100-wide815-v1'
    result = package.prepare(path, source, profile_id, worker, 'run', packet, out / 'budget-815.json')
    variant = dict(archive=str(packet / 'package.tar.gz'), sha256=result['archive_sha256'],
        ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet / 'manifest.json').read_bytes()),
        worker_id=worker, profile=profile_id, native_root=result['native_root'],
        runner='tools/native_threaded_wide_package_v3.py', runner_sha256=sha((ROOT / 'tools/native_threaded_wide_package_v3.py').read_bytes()),
        stager=str(ROOT / 'tools/native_threaded_wide_stage_v3.py'),
        stager_sha256=sha((ROOT / 'tools/native_threaded_wide_stage_v3.py').read_bytes()),
        stager_dependencies=[dict(path=str(ROOT / name), sha256=sha((ROOT / name).read_bytes()))
            for name in ('tools/native_threaded_wide_stage_v1.py', 'tools/native_package_v3.py', 'tools/native_package_v2.py')],
        max_seconds=3700, placement=profile['fixed_placement'])
    ticket = dict(schema='gfn16-global-ticket-v1', id=PILOT_ID, owner='p16-mlab',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P1', kind='sim', needs='verilator',
        tool_identity='azure-burst16-verilator5032-gcc13-python312-v1', resources=dict(cores=8, threads=8, ram_gib=8, scratch_gib=4),
        minimum_ram_gib=8, minimum_ram_rationale='Bounded own timing58 source/threadpilot; no old C2 peak/duration inherited.',
        est_minutes=35, promotion_bound=False, test_role='normal', rtl_readiness=original['rtl_readiness'], packages=[variant],
        after=['s4-p16-c2-timing-full-normal-q1-v1'], on='PASS_expected_contracts')
    dump(out / 'global-ticket.json', ticket)
    return dict(id=PILOT_ID, ticket=str(out / 'global-ticket.json'), status='own_pilot_prepared_not_native')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_pilot(args.output), indent=2))

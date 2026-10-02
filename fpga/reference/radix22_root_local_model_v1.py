"""N1 root-local/pass-fused ROM model; exponents only at full N.

Reuses the frozen N1 geometry, calendar and measured-cell calibration. No
field roots, NTT, HDL, vendor tools, frozen-source mutation or physical claim
are produced by this model. One read port returns three 27-bit roots/copy.
"""
from functools import lru_cache
import argparse
import hashlib
import itertools
import json
from pathlib import Path

from fpga.reference import radix22_track_a_model_v1 as frozen

ROOT = Path(__file__).resolve().parents[1]
MODEL_PIN = '304947d5b3e40e32b4955626d77e38c7b418bad0ce19e1940d44c8cd448ddcc3'
RECEIPT = 'docs/briefs/replies/2026-10-01-B20261001N-N1-radix22-model-v1.json'
RECEIPT_PIN = 'f967e2c5ada8a7eb33a4a6b307ee89c72a415a72b1f4ef69788555261de814b5'
TILING_PIN = '03c1c855e0f6e31f0fcb85d32ed2e604a935e482dfa725d7207e635cb1e963cc'
DEFAULT = ((1,), (3,), (5, 7, 9, 11, 13, 15))


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_guard():
    pins = frozen.source_guard()
    for path, pin in [('reference/radix22_track_a_model_v1.py', MODEL_PIN),
                      (RECEIPT, RECEIPT_PIN), ('reference/stream_ntt_schedule.py', TILING_PIN)]:
        need(sha(ROOT/path) == pin, 'frozen N1 reuse pin:' + path)
        pins[path] = pin
    return pins


def layout(partition=DEFAULT, *, n=65536, lanes=64):
    aw, _, beats = frozen.geometry(n, lanes)
    need(aw % 2 == 0, 'even-AW paired layout only')
    expected = tuple(range(1, aw, 2))
    partition = tuple(tuple(group) for group in partition)
    need(all(group for group in partition)
         and tuple(itertools.chain.from_iterable(partition)) == expected,
         'ordered complete contiguous paired pass partition')
    rows = {row['high']: row for row in frozen.packed_root_layout(n, lanes)['rows']}
    quartets = min(n, 2*lanes)//4
    segments = []
    for index, highs in enumerate(partition):
        copies = max(rows[high]['high_streams'] for high in highs)
        need(quartets % copies == 0, 'hardwired contiguous consumer groups')
        offset = 0
        passes = []
        for high in highs:
            row = rows[high]
            passes.append(dict(high=high, low=high-1, offset=offset, depth=row['depth'],
                issue_address_shift=row['issue_address_shift'], natural_streams=row['high_streams']))
            offset += row['depth']
        depth = 2*offset  # inverse is an address bit/offset, never a payload mux.
        blocks = frozen.m20k(depth, 81)
        segments.append(dict(index=index, highs=list(highs), copies=copies, width=81,
            words_per_read=3, consumers_per_copy=quartets//copies,
            direction_stride=offset, depth_both_directions=depth,
            M20K_per_copy=blocks, M20K=blocks*copies,
            raw_bits=depth*81*copies, passes=passes))
    root_mux = 3*quartets*27*(len(partition)-1)
    return dict(n=n, lanes=lanes, quartets=quartets, beats=beats, partition=[list(p) for p in partition],
        segments=segments, one_read_port_per_copy=True, reads_per_active_copy_per_beat=1,
        table_output_registered_edges=1, both_directions_M20K_per_field=sum(s['M20K'] for s in segments),
        raw_bits_per_field=sum(s['raw_bits'] for s in segments),
        root_stream_xor_mux_bits=0, root_direction_mux_bits=0,
        root_pass_select_mux_bits=root_mux, paired_root_mux_bits=root_mux,
        direction_in_ROM_address=True, no_dual_port_or_time_multiplex_credit=True,
        constant_upper_pass_words_stored_in_merged_ROM=True,
        no_full_N_numeric_roots_generated=True)


def request(plan, high, number, inverse, lane):
    need(type(inverse) is bool and type(lane) is int and 0 <= lane < plan['quartets'], 'root request types/lanes')
    need(type(number) is int and 0 <= number < plan['beats'], 'root request beat')
    found = [(segment, row) for segment in plan['segments'] for row in segment['passes'] if row['high'] == high]
    need(len(found) == 1, 'root request selected pass')
    segment, row = found[0]
    address = int(inverse)*segment['direction_stride'] + row['offset'] + (number >> row['issue_address_shift'])
    return dict(segment=segment['index'], copy=lane//segment['consumers_per_copy'], address=address,
                high=high, inverse=inverse)


def record_for_beat(n, lanes, high, number, lane, inverse):
    beat = frozen.paired_issue(n, lanes, high, number)
    q = beat.quartets[lane]
    aw = frozen.arith.geometry(n)
    exponent = lambda stage, u: frozen.arith.bit_reverse((n >> (stage+1))+(u >> (stage+1)), aw)
    exponents = (exponent(high, q[0]), exponent(high-1, q[0]), exponent(high-1, q[2]))
    sign = -1 if inverse else 1
    return (int(inverse), high, *(sign*e for e in exponents), int(inverse and high == aw-1))


@lru_cache(maxsize=8)
def compile_tables(partition=DEFAULT, n=65536, lanes=64):
    """Compile root descriptors, NOT numerical root values or field transforms."""
    plan = layout(partition, n=n, lanes=lanes)
    tables = []
    for segment in plan['segments']:
        copies = []
        for copy in range(segment['copies']):
            lane = copy*segment['consumers_per_copy']
            words = []
            for inverse in (False, True):
                for row in segment['passes']:
                    for address in range(row['depth']):
                        number = address << row['issue_address_shift']
                        words.append(record_for_beat(n, lanes, row['high'], number, lane, inverse))
            need(len(words) == segment['depth_both_directions'], 'closed root-local table depth')
            copies.append(tuple(words))
        tables.append(tuple(copies))
    return tuple(tables)


def symbolic_gate(partition=DEFAULT, *, n=65536, lanes=64, mutant=None):
    plan = layout(partition, n=n, lanes=lanes)
    tables = compile_tables(tuple(tuple(x) for x in partition), n, lanes)
    checked = 0
    for high in range(1, frozen.arith.geometry(n), 2):
        for number in range(plan['beats']):
            # Independent frozen packed-root expression remains the comparator.
            packed = frozen.packed_root_exponents(n, lanes, high, number)
            for inverse in (False, True):
                for lane in range(plan['quartets']):
                    req = request(plan, high, number, inverse, lane)
                    if mutant == 'wrong-direction-address':
                        req = request(plan, high, number, not inverse, lane)
                    if mutant == 'wrong-copy':
                        req['copy'] = (req['copy']+1) % plan['segments'][req['segment']]['copies']
                    actual = tables[req['segment']][req['copy']][req['address']]
                    sign = -1 if inverse else 1
                    expected = (int(inverse), high, *(sign*e for e in packed[lane]),
                                int(inverse and high == frozen.arith.geometry(n)-1))
                    need(actual == expected, 'root-local exact exponent/direction/final-scale delivery')
                    checked += 3
    return dict(status='PASS_symbolic_root_local_delivery', n=n, directions=2,
        delivered_exponents_checked=checked, compiled_descriptor_words=sum(len(c) for seg in tables for c in seg),
        numeric_root_values_generated=False, full_N_transform_performed=False)


def resources(partition=DEFAULT, *, alm_per_mux_bit=0.5, control_reserve=4096):
    old = frozen.resource_ledger(alm_per_mux_bit=alm_per_mux_bit, control_reserve=control_reserve)
    plan = layout(partition)
    selectors = old['selectors']
    data_bits = selectors['delta_data_mux_bits']
    root_bits = plan['paired_root_mux_bits']-selectors['parent_generated_root_mux_bits']
    estimate = old['zero_new_route_floor']+3*(data_bits+root_bits)*alm_per_mux_bit+control_reserve
    memory = 987-192-96+3*plan['both_directions_M20K_per_field']
    dsp = old['packed_ROM']['DSP_needed_proxy']
    passed = estimate <= 320000 and memory <= 2300 and dsp <= 1100
    return dict(partition=plan['partition'], ALMs_needed_proxy=round(estimate, 1), DSP_needed_proxy=dsp,
        M20K_legal_rectangle_proxy=memory, root_M20K_per_field=plan['both_directions_M20K_per_field'],
        root_mux_bits_per_field=plan['paired_root_mux_bits'], root_mux_delta_per_field=root_bits,
        data_mux_delta_per_field=data_bits, control_reserve=control_reserve, ALM_per_mux_bit=alm_per_mux_bit,
        delta_from_frozen_canonical_proxy=round(estimate-old['packed_ROM']['ALMs_needed_planning'], 1),
        conditional_area_gate_passed=passed,
        gate='CONDITIONAL_GO_selector_measurement_only' if passed else 'NO_GO_at_declared_proxy',
        architectural_RTL_GO=False, measured=False, physical=False,
        retains_canonical_BF_upper_normalizer_cells=True, recurrence_R1_saving_not_counted_twice=True)


def partition_frontier():
    highs = tuple(range(1, 16, 2))
    results = []
    for cuts in range(1 << 7):
        groups = [[]]
        for i, high in enumerate(highs):
            groups[-1].append(high)
            if i < 7 and cuts & (1 << i):
                groups.append([])
        results.append(resources(tuple(tuple(g) for g in groups)))
    admissible = sorted((r for r in results if r['conditional_area_gate_passed']),
                        key=lambda r: (r['M20K_legal_rectangle_proxy'], r['ALMs_needed_proxy'], r['partition']))
    return dict(partitions_evaluated=len(results), cheapest_M20K_conditional=admissible[0],
                lowest_ALM_conditional=min(admissible, key=lambda r: r['ALMs_needed_proxy']),
                models_not_measurements=True)


def hybrid_calendar():
    """Split pair(1,0) only; preserve frozen single9/pair15-edge overheads."""
    old = frozen.cycle_ledger()
    single = old['issues_per_pass']+9
    delta = 2*(2*single-old['pair_pass_cycles'])
    return dict(status='declared_calendar_only_no_native', radix2_pass_cycles=single,
        paired_pass_cycles=old['pair_pass_cycles'], extra_cycles_per_square=delta,
        ntt_cycles=old['ntt_cycles_for_declared_calendar']+delta,
        T5b_warm_conditional=old['T5b_warm_conditional']+delta,
        A4_warm_conditional=old['A4_warm_conditional']+delta,
        additional_root_route_edges_unassigned=True, resource_gate_not_assumed=True,
        physical_frequency=None, A4_failed_fit_not_a_qualified_parent=True)


def report():
    need(not (ROOT/'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    pins = source_guard()
    plan = layout()
    return dict(task='B20261001N1G', status='root_local_model_conditional_area_GO_measurement_pending',
        source_hashes=pins, model_sha256=sha(__file__), layout=plan, root_delivery=symbolic_gate(),
        resources=resources(), frontier=partition_frontier(), hybrid=hybrid_calendar(),
        cycles=frozen.cycle_ledger(), schedule_changed=False,
        next_measured_gate='Source-bound registered selector comparison: actual child ALMs/regs and root ROM inference; route>=100MHz before architecture RTL GO.',
        exclusions=['No measured selector ALM or ROM inference/placement/timing result.',
                    'Control/address/fanout/root-delay packing beyond4096 reserve remains unmeasured.',
                    'No lean-cell percentage, A4 area saving, DSP extra port or recurrence saving credited twice.',
                    'N1 architectural RTL and whole-core fit not authorized by a proxy alone.',
                    'F2 alternatives/CT-GS issue ancestry remain separate; no blind composition.'],
        numeric_full_N_NTT_locally_performed=False, whole_core_clock_claim=False, promotion_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = report()
    if args.output:
        need(args.output.is_absolute() and not args.output.exists()
             and args.output.parent.is_dir() and args.output.parent.resolve() == args.output.parent,
             'fresh canonical model receipt')
        with args.output.open('x') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    print(json.dumps(result, indent=2))

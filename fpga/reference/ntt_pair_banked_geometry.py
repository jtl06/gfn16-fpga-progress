"""Executable physical-port proposal, not RTL or a throughput result."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import time
from .ntt27_radix4_feasibility import bank_of, groups as reference_groups


def rol(x, amount, width):
    mask = (1 << width) - 1
    return ((x << amount) | (x >> (width - amount))) & mask


def ror(x, amount, width):
    return rol(x, (width - amount) % width, width)


def insert_zero(lane, bit):
    return (lane & ((1 << bit) - 1)) | ((lane >> bit) << (bit + 1))


def expand(value, positions):
    return sum(((value >> j) & 1) << bit for j, bit in enumerate(positions))


def descriptor(lg, lanes, stages):
    width = (2 * lanes).bit_length() - 1
    representatives = list(range(min(width, lg)))
    for stage in stages:
        representatives[stage % width] = stage
    assert len(set(representatives)) == len(representatives)
    fixed = [bit for bit in range(lg) if bit not in representatives]
    return width, representatives, fixed


def physical_rows(lg, lanes, stages, group):
    width, reps, fixed = descriptor(lg, lanes, stages)
    banks = 2 * lanes
    base = expand(group, fixed)
    base_bank = bank_of(base, banks)
    # The proposed b<N mask is deliberately tested, not used to define the
    # independent logical expected group below.
    mapping = {bank: base | expand(bank ^ base_bank, reps)
               for bank in range(banks) if bank < (1 << lg)}
    return base, mapping


def root_ports(lg, lanes, stages, group, stage):
    width, reps, fixed = descriptor(lg, lanes, stages)
    banks = 2 * lanes
    base = expand(group, fixed)
    shift = lg - 1 - stage
    rotation = shift % width
    root_base = (base & ((1 << stage) - 1)) << shift
    root_bank = bank_of(root_base, banks)
    mask = sum(1 << r for r, bit in enumerate(reps) if bit < stage)
    ports = {}
    for bank in range(banks):
        variable = ror(bank ^ root_bank, rotation, width)
        if variable & ~mask:
            continue
        address = root_base | sum(((variable >> r) & 1) << (bit + shift)
                                  for r, bit in enumerate(reps) if bit < stage)
        assert 0 <= address < (1 << (lg - 1))
        assert bank_of(address, banks) == bank
        ports[bank] = (address, address >> width)
    return ports, mask, rotation, root_bank


def check_geometry(lg, lanes, stages):
    n = 1 << lg
    banks = 2 * lanes
    width, reps, fixed = descriptor(lg, lanes, stages)
    group_count = 1 << len(fixed)
    independent = iter(reference_groups(lg, lanes, max(stages))) if len(stages) == 2 else None
    seen = set()
    snapshots = []
    consumers = 0
    root_count = 0
    for group in range(group_count):
        base, physical = physical_rows(lg, lanes, stages, group)
        # Reference enumeration is logical and sorted by address position,
        # independently of physical bank order and representative-coordinate order.
        if independent is not None:
            logical = set(next(independent))
        else:
            logical = {base | expand(v, sorted(reps)) for v in range(1 << len(reps))}
        assert set(physical.values()) == logical
        assert set(physical) == {bank_of(a, banks) for a in logical}
        assert not seen.intersection(logical)
        seen.update(logical)
        assert all(bank_of(a, banks) == bank for bank, a in physical.items())
        rows_a = tuple((bank, a >> width) for bank, a in physical.items())
        snapshots.append(rows_a)
        for stage in stages:
            pairing = stage % width
            orientation = (bank_of(base, banks) >> pairing) & 1
            ports, mask, rotation, root_base_bank = root_ports(lg, lanes, stages, group, stage)
            root_count += len(ports)
            required_roots = set()
            written = {}
            folded = root_base_bank ^ rol(bank_of(base, banks) & mask, rotation, width)
            routed = list(range(banks))
            for bit in range(width):
                routed = [routed[b ^ (1 << bit)] if folded & (1 << bit) else routed[b]
                          for b in range(banks)]
            routed = [routed[rol(b, rotation, width)] for b in range(banks)]
            for bit in range(width):
                routed = [routed[b] if mask & (1 << bit) else routed[b & ~(1 << bit)]
                          for b in range(banks)]
            # Enumerate actual arithmetic lane wiring, not just root sets.
            for lane in range(min(lanes, n // 2)):
                lo = insert_zero(lane, pairing)
                hi = lo | (1 << pairing)
                u_bank, v_bank = (hi, lo) if orientation else (lo, hi)
                u_addr, v_addr = physical[u_bank], physical[v_bank]
                assert not (u_addr & (1 << stage))
                assert v_addr == u_addr ^ (1 << stage)
                expected_root = (u_addr & ((1 << stage) - 1)) << (lg - 1 - stage)
                required_roots.add(expected_root)
                # Folded network: first XOR, then fixed rotation wiring,
                # then a dimension-by-dimension broadcast clip network.
                selected_bank = routed[u_bank]
                assert selected_bank in ports
                actual_root, root_row = ports[selected_bank]
                assert actual_root == expected_root
                assert root_row == expected_root >> width
                # Both result destinations invert the same lane permutation;
                # retain their logical identity rather than arithmetic values.
                for b, address in ((u_bank, u_addr), (v_bank, v_addr)):
                    assert b not in written
                    written[b] = address
                consumers += 1
            assert written == physical
            assert required_roots == {address for address, _ in ports.values()}
        # Independently reconstruct B metadata; compare every row with A's
        # saved snapshot, not merely a deduplicated address set.
        _, physical_b = physical_rows(lg, lanes, tuple(reversed(stages)), group)
        rows_b = tuple((bank, a >> width) for bank, a in physical_b.items())
        assert rows_b == rows_a
    assert seen == set(range(n))
    return dict(lg=lg, lanes=lanes, stages=list(stages), groups=group_count,
                addresses=n, consumers=consumers, root_reads=root_count), snapshots


def check_events(rows, pair, wrong_b_group=False):
    groups = len(rows)
    reads = {}
    issues = {}
    results = {}
    for group in range(groups):
        for kind, read, issue, result in ((0, 2 * group, 2 * group + 1, 2 * group + 7),
                                         (1, 2 * group + 7, 2 * group + 8, 2 * group + 14)):
            assert read not in reads and issue not in issues and result not in results
            reads[read] = (kind, group, tuple(rows[group]), pair)
            issues[issue] = (kind, group)
            results[result] = (kind, group)
    response = None
    held = None
    pending = {}
    row_tags = {}
    writes = 0
    for tick in range(2 * groups + 13):
        # Outputs and held operands at this edge are the PRE-edge state.
        if tick in issues:
            kind, group = issues[tick]
            assert response is not None and response[:2] == (kind, group)
            assert response[3] == pair
            if kind:
                assert held == (group, rows[group])
                held = None
            pending[tick + 6] = (kind, group, pair)
        if tick in results:
            kind, group = results[tick]
            assert pending.pop(tick) == (kind, group, pair)
            source_kind, source_group, commit_rows, source_pair = row_tags.pop(tick)
            assert source_pair == pair
            assert (source_kind, source_group) == (kind, group)
            assert commit_rows == rows[group]
            if kind:
                # Reads concurrent with final writes must be different rows
                # of every common physical bank; no mixed-port collision.
                if tick in reads and reads[tick][0] == 0:
                    read_rows = dict(reads[tick][2])
                    for bank, row in commit_rows:
                        assert read_rows[bank] != row
                writes += 1
            else:
                assert held is None
                held = (group, rows[group])
        response = reads.get(tick)
        if response is not None:
            if wrong_b_group and response[0] and groups > 1:
                row_tags[tick + 7] = (response[0], response[1], rows[(response[1] + 1) % groups], pair)
            else:
                row_tags[tick + 7] = response
    assert writes == groups and not pending and not row_tags and held is None
    return dict(groups=groups, stages=list(pair), active_edges=2 * groups + 13, setup_edges=1,
                final_commit_edge=2 * groups + 12, pending_after_final=0)


def control_boundary_cases():
    """Small synchronous controller blueprint, explicitly not an RTL proof.

    Sampled root reads may create a response, then a six-edge arithmetic token.
    Reset invalidates both. A detected fault suppresses same-edge work and
    starts seven full drain edges before accepting another descriptor.
    """
    cases = 0
    for groups in (1, 2, 3, 8):
        finish = 2 * groups + 12
        for stop in range(finish + 2):
            for reset in (False, True):
                response = None
                outputs = {}
                fault = False
                draining = 0
                epoch = 1
                descriptor = (16, (7, 6))
                active = True
                for tick in range(finish + 12):
                    # Ignore changed-size/order starts while active/draining.
                    start_changed = active
                    old_descriptor = descriptor
                    if tick == stop:
                        if reset:
                            response = None
                            outputs.clear()
                            active = False
                        else:
                            fault = True
                            draining = 7
                    # Prospective commit is evaluated before fault latching;
                    # detection itself blocks it, even if old_fault was zero.
                    result = outputs.pop(tick, None)
                    write = result is not None and result[1] == 1 and not fault and tick != stop
                    if write:
                        assert result[2] == epoch and result[3] == descriptor
                    if fault:
                        assert not write
                    if response is not None and not fault:
                        kind, group, token_epoch, token_descriptor = response
                        outputs[tick + 6] = (group, kind, token_epoch, token_descriptor)
                    response = None
                    if active and not fault:
                        if tick % 2 == 0 and tick < 2 * groups:
                            response = (0, tick // 2, epoch, descriptor)
                        elif tick % 2 and 7 <= tick < 2 * groups + 7:
                            response = (1, (tick - 7) // 2, epoch, descriptor)
                    if start_changed:
                        assert descriptor == old_descriptor
                    if draining:
                        draining -= 1
                        if draining == 0:
                            assert not outputs and response is None
                            active = False
                    if not active:
                        # Earliest permissible changed descriptor cannot
                        # inherit any old arithmetic or response eligibility.
                        assert not outputs and response is None
                        epoch += 1
                        descriptor = (4, (0, 1))
                        break
                cases += 1
    # Non-vacuous counterexample to registered-fault-only write eligibility.
    previous_fault, same_edge_bad_tag, prospective_commit = False, True, True
    unsafe_old_write = prospective_commit and not previous_fault
    safe_write = prospective_commit and not previous_fault and not same_edge_bad_tag
    assert unsafe_old_write and not safe_write
    return dict(reset_and_fault_boundaries=cases, drain_edges=7,
                changed_descriptor_before_drain='ignored', registered_only_fault_counterexample=True)


def directed_counterexamples():
    found = []
    # Small N does not activate all physical banks, even if L is much larger.
    _, mapping = physical_rows(2, 64, (1, 0), 0)
    assert set(mapping) != set(range(128))
    found.append(dict(name='all_banks_small_n', lg=2, lanes=64, legal_banks=len(mapping), wrong_banks=128))
    # Crossing pair h=k requires an arbitrary mask, not a low contiguous one.
    ports, mask, rotation, root_base_bank = root_ports(16, 64, (7, 6), 0, 7)
    assert mask == 0b1111110 and mask != (1 << mask.bit_count()) - 1
    found.append(dict(name='contiguous_root_mask', lg=16, lanes=64, high=7,
                      required_mask=mask, wrong_mask=(1 << mask.bit_count()) - 1))
    _, physical = physical_rows(16, 64, (14, 13), 0)
    ports, _, _, _ = root_ports(16, 64, (14, 13), 0, 13)
    data_rows = {a >> 7 for a in physical.values()}
    root_rows = {row for _, row in ports.values()}
    assert data_rows == {0, 64, 128, 192} and root_rows == {0, 1}
    found.append(dict(name='root_row_substituted_for_data_row', lg=16, lanes=64, high=14,
                      data_rows=sorted(data_rows), root_rows=sorted(root_rows)))
    _, rows = check_geometry(10, 64, (7, 6))
    try:
        check_events(rows, (7, 6), wrong_b_group=True)
    except AssertionError:
        found.append(dict(name='independently_advancing_b_group', rejected=True))
    else:
        raise AssertionError('wrong second-read group was not detected')
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if platform.node().split('.')[0] != 'aethia':
        raise RuntimeError('execute gate on aethia only')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise FileExistsError(args.output)
    before = time.monotonic()
    cases = []
    events = []
    checked_events = set()
    for lanes in (1, 2, 4, 8, 16, 32, 64):
        max_lg = 16 if lanes in (16, 64) else 8
        for lg in range(1, max_lg + 1):
            combinations = [(s,) for s in range(lg)]
            if lanes >= 2:
                combinations += [pair for s in range(1, lg) for pair in ((s, s - 1), (s - 1, s))]
            for stages in combinations:
                result, rows = check_geometry(lg, lanes, stages)
                cases.append(result)
                if len(stages) == 2 and (lg, lanes, tuple(stages)) not in checked_events:
                    events.append(check_events(rows, stages))
                    checked_events.add((lg, lanes, tuple(stages)))
            # Actual order traversal consumes each stage once; no overlap or
            # omitted odd-stage/N2 fallback, independent of the geometry loop.
            for dif in (False, True):
                order = list(range(lg - 1, -1, -1) if dif else range(lg))
                chunks = [tuple(order[j:j + (2 if lanes >= 2 else 1)])
                          for j in range(0, lg, 2 if lanes >= 2 else 1)]
                assert [s for chunk in chunks for s in chunk] == order
    boundary_cases = control_boundary_cases()
    counterexamples = directed_counterexamples()
    report = dict(status='passed_geometry_event_model_not_rtl', seconds=time.monotonic() - before,
                  control_boundary_cases=boundary_cases, directed_counterexamples=counterexamples,
                  cases=cases, events=events, case_count=len(cases),
                  physical_addresses=sum(c['addresses'] for c in cases),
                  arithmetic_lane_root_consumers=sum(c['consumers'] for c in cases),
                  source_hashes={str(p.name): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in (Path(__file__), Path(__file__).with_name('ntt27_radix4_feasibility.py'))},
                  limits=['No RTL or arithmetic value gate.', 'All lg1..16 for L16/64; other lane powers checked through lg8.',
                          'Address/routing proof is independent of field and root sign; arithmetic still requires all-field RTL.',
                          'Representative and routing network formulas are a proposal, not measured physical hardware.'])
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('cases', 'events')}, indent=2))


if __name__ == '__main__':
    main()

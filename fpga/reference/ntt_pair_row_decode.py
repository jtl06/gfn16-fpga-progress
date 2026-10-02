"""Exact row-only decoder proposal against frozen physical_rows, not RTL."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import time

from .ntt_pair_banked_geometry import descriptor, physical_rows, root_ports
from .ntt27_radix4_feasibility import bank_of


def row_decode(base, bank, lanes, stages, mutation=None):
    width = (2 * lanes).bit_length() - 1
    folded = bank_of(base, 2 * lanes)
    variable = bank ^ (0 if mutation == 'omit-base-fold' else folded)
    result = base >> width
    high = [stage for stage in stages if stage >= width]
    if mutation == 'omit-second-mask':
        high = high[:1]
    for stage in high:
        coordinate = stage % width
        if mutation == 'wrong-coordinate':
            coordinate = (coordinate + 1) % width
        if (variable >> coordinate) & 1:
            result |= 1 << (stage - width)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if platform.node().split('.')[0] != 'aethia':
        raise RuntimeError('Run this bounded model gate on aethia only')
    if args.output.exists():
        raise FileExistsError(args.output)
    geometry = Path(__file__).with_name('ntt_pair_banked_geometry.py')
    if hashlib.sha256(geometry.read_bytes()).hexdigest() != 'd0664781f21d0c5ad15e3741ccbc7ab72515e88e0ae25a76a7917df9c0a0ab85':
        raise RuntimeError('Frozen physical_rows oracle changed')
    start = time.monotonic()
    cases = addresses = groups = 0
    distinct_max = 0
    counterexamples = {}
    for lanes in (1, 2, 4, 8, 16, 32, 64):
        for lg in range(1, (16 if lanes in (16, 64) else 8) + 1):
            stage_sets = [(s,) for s in range(lg)]
            if lanes > 1:
                stage_sets += [p for s in range(1, lg) for p in ((s, s-1), (s-1, s))]
            for stages in stage_sets:
                cases += 1
                width, _, fixed = descriptor(lg, lanes, stages)
                for group in range(1 << len(fixed)):
                    groups += 1
                    base, expected = physical_rows(lg, lanes, stages, group)
                    actual = {b: row_decode(base, b, lanes, stages) for b in expected}
                    assert actual == {b: a >> width for b, a in expected.items()}
                    assert set(actual) == set(range(min(1 << lg, 2 * lanes)))
                    high_count = sum(s >= width for s in stages)
                    assert len(set(actual.values())) == 1 << high_count
                    distinct_max = max(distinct_max, len(set(actual.values())))
                    addresses += len(actual)
                    # Physical row width is clamped to one bit for small AW;
                    # check both minimum legal AW=lg and the target AW=16.
                    for aw in {lg, 16}:
                        assert all(v < 1 << max(1, aw-width) for v in actual.values())
                    for mutation in ('omit-base-fold', 'omit-second-mask', 'wrong-coordinate'):
                        if mutation in counterexamples:
                            continue
                        for b, correct in actual.items():
                            wrong = row_decode(base, b, lanes, stages, mutation)
                            if wrong != correct:
                                counterexamples[mutation] = dict(lg=lg, lanes=lanes, stages=stages,
                                    group=group, bank=b, expected_row=correct, mutant_row=wrong)
                                break
    # A B-root response row is not a data row, despite sharing a physical bank.
    lg, lanes, stages, group = 16, 64, (14, 13), 0
    _, mapping = physical_rows(lg, lanes, stages, group)
    ports, *_ = root_ports(lg, lanes, stages, group, stages[1])
    witnesses = [(b, mapping[b] >> 7, row) for b, (_, row) in ports.items()
                 if mapping[b] >> 7 != row]
    assert witnesses
    b, correct, wrong = witnesses[0]
    counterexamples['copy-B-root-row'] = dict(lg=lg, lanes=lanes, stages=stages,
        group=group, bank=b, expected_row=correct, mutant_row=wrong)
    assert len(counterexamples) == 4
    paths = [Path(__file__), geometry, Path(__file__).with_name('ntt27_radix4_feasibility.py')]
    report = dict(status='passed_row_identity_model_not_rtl', seconds=time.monotonic()-start,
        cases=cases, groups=groups, physical_rows=addresses, max_distinct_rows_per_group=distinct_max,
        counterexamples=counterexamples,
        source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        limits=['No new RTL, simulator build, physical fit or throughput result.',
                'All lg1..16 at L16/64, other powers L1..32 through lg8.',
                'Group/base generation and active-bank masks remain inherited, not redesigned.',
                'Existing timing/tag/reset contract is unchanged by proposal, not proven here.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

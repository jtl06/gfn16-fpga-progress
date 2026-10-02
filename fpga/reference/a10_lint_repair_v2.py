"""Minimal additive A10 repair for the actual AW5 native lint failure.

Original sources, modules' interfaces, arithmetic, root words, registers and
edge ledger stay frozen. New isolated file names implement the same module
names: each route level gets its own net, the admitted stage index is narrowed
explicitly, and the 32-bit diagnostic root counter gets a 32-bit expression.
No warning suppression, host-policy clone, HDL invocation or dispatch.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from fpga.reference import a10_banked_engine_generate_v1 as gen
from fpga.reference import a10_geometry_prepare_v1 as geometry

ROOT = gen.ROOT / 'fpga'
SELF = 'reference/a10_lint_repair_v2.py'
TEST = 'tests/test_a10_lint_repair_v2.py'
ENGINE_V1 = 'rtl/kernel/genefer_a10_banked27_engine_v1.sv'
ENGINE_V2 = 'rtl/kernel/genefer_a10_banked27_engine_lint_v2.sv'
ENGINE_SHA = '8543c6bf56e7d978f893248db55632503e08ed77ff03674eb55b05144a29dc94'
FAILURE = 'results/throughput-20260929/a10-aw5-f0-lint-gcp-v1/report.json'
FAILURE_SHA = '51d9e2243a5070b8ea7a5cc1ac291d2121d10464e6ff06830368b73205741479'
DIAGNOSTIC = 'results/throughput-20260929/a10-aw5-f0-lint-gcp-v1/lint.stderr.log'
DIAGNOSTIC_SHA = '7a318cfaf17e04f5f91c1b258eb6696d0f522e1720dc24bfebbf4e42fad3b0f0'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def engine_source(original):
    need(digest(original.encode()) == ENGINE_SHA, 'A10_REPAIR_FROZEN_ENGINE')
    before = "stage_root_count<=KW'(1<<"
    after = "stage_root_count<=32'(1<<"
    repaired = gen.once(original, before, after)
    need(repaired.replace(after, before) == original, 'A10_REPAIR_COUNTER_ONLY')
    return repaired


def repair_lookup(original, aw):
    need(aw in (5, 8, 16), 'A10_REPAIR_AW')
    text = original
    changed = []
    # This array's elements are separate stage levels, not a combinational
    # feedback loop. Declare levels separately so native scheduling sees that
    # exact acyclic graph without a whole-multidimensional-array dependency.
    pattern = r' wire \[26:0\] s(\d+)_route\[0:(\d+)\]\[0:(\d+)\];'
    declarations = list(re.finditer(pattern, original))
    need(len(declarations) == 3 * aw, 'A10_REPAIR_THREE_FIELD_ROUTES')
    # Three separately compiled field modules reuse local stage net names.
    for stage in range(aw):
        matches = [m for m in declarations if int(m[1]) == stage]
        need(len(matches) == 3 and len({(m[2], m[3]) for m in matches}) == 1,
             'A10_REPAIR_ROUTE_GEOMETRY')
        levels, last_stream = int(matches[0][2]), int(matches[0][3])
        declaration = matches[0][0]
        replacement = '\n'.join(
            f' wire [26:0] s{stage}_route_d{level}[0:{last_stream}];'
            for level in range(levels + 1))
        need(text.count(declaration) == 3, 'A10_REPAIR_ROUTE_DECLARATION')
        text = text.replace(declaration, replacement)
        for level in range(levels + 1):
            old = f's{stage}_route[{level}]'
            new = f's{stage}_route_d{level}'
            need(old in text, 'A10_REPAIR_ROUTE_LEVEL_USED')
            text = text.replace(old, new)
        changed.append((declaration, replacement, stage, levels))
    old = 'selected_stage_roots[stage_q]'
    new = f"selected_stage_roots[{max(1, (aw-1).bit_length())}'(stage_q)]"
    need(text.count(old) == 3, 'A10_REPAIR_STAGE_INDEX')
    text = text.replace(old, new)
    restored = text.replace(new, old)
    for declaration, replacement, stage, levels in reversed(changed):
        # Restore references before declarations; the declaration's net name
        # carries no array level selector and is replaced as a whole later.
        for level in range(levels + 1):
            restored = re.sub(rf's{stage}_route_d{level}(?=\[\d+\])',
                              f's{stage}_route[{level}]', restored)
        restored = restored.replace(replacement, declaration)
    need(restored == original, 'A10_REPAIR_LOOKUP_ONLY')
    need(re.search(r's\d+_route\[', text) is None, 'A10_REPAIR_NO_FLATTENED_ROUTE')
    return text


def prepare(manifest_path, source_root, output):
    need(not (ROOT / 'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    source_root, output = Path(source_root).resolve(), Path(output).resolve()
    need(not output.exists(), 'A10_REPAIR_FRESH_OUTPUT')
    original_raw = Path(manifest_path).read_bytes()
    original = json.loads(original_raw)
    geometry.closed(source_root, original['sources'])
    aw = original['build']['parameters']['AW']
    need(aw in (5, 8, 16), 'A10_REPAIR_AW')
    need(digest((ROOT / FAILURE).read_bytes()) == FAILURE_SHA and
         digest((ROOT / DIAGNOSTIC).read_bytes()) == DIAGNOSTIC_SHA,
         'A10_REPAIR_ACTUAL_FAILURE_IDENTITY')
    need(original['sources'][ENGINE_V1] == ENGINE_SHA, 'A10_REPAIR_ORIGINAL_ENGINE')
    lookup_names = [n for n in original['build']['sv_sources']
                    if Path(n).name.startswith('a10_packed_lookup_')]
    need(len(lookup_names) == 1, 'A10_REPAIR_LOOKUP_BINDING')
    lookup_v1 = lookup_names[0]
    lookup_v2 = f'rtl/kernel/a10_packed_lookup_aw{aw}_lint_bound_v2.sv'
    files = {n: (source_root / n).read_bytes() for n in original['sources']}
    files[ENGINE_V2] = engine_source(files[ENGINE_V1].decode()).encode()
    files[lookup_v2] = repair_lookup(files[lookup_v1].decode(), aw).encode()
    for name in (SELF, TEST, FAILURE, DIAGNOSTIC,
                 'reference/a10_geometry_prepare_v1.py',
                 'reference/a10_engine_geometry_gates_v1.py',
                 'reference/a10_native_roles_v1.py'):
        files[name] = (ROOT / name).read_bytes()
    # Both old compiled inputs stay in the closed snapshot as failure lineage,
    # but neither is compiled alongside the additive same-interface successor.
    m = json.loads(original_raw)
    m['build']['sv_sources'] = [ENGINE_V2 if n == ENGINE_V1 else
                                lookup_v2 if n == lookup_v1 else n
                                for n in m['build']['sv_sources']]
    need(ENGINE_V1 not in m['build']['sv_sources'] and
         lookup_v1 not in m['build']['sv_sources'], 'A10_REPAIR_NO_DUPLICATE_MODULES')
    m['source_root'] = '/not-a-dispatch-path/a10-lint-v2/fpga'
    m['output_parent'] = '/not-a-dispatch-path/a10-lint-v2/output'
    m.pop('lint_baseline', None)
    m['repair'] = dict(schema='a10-observed-lint-repair-v2',
        original_manifest_sha256=digest(original_raw),
        failure_report_sha256=FAILURE_SHA, diagnostic_sha256=DIAGNOSTIC_SHA,
        delta='Separate acyclic route level nets; explicitly narrow admitted stage index; widen root diagnostic count to32 bits.',
        unchanged='Modules/ports/root constants/arithmetic/RAM/registers/phase order/normalization/cycle ledger.',
        native_requalification_required=True, warning_suppression=False)
    output.mkdir(parents=True)
    source = output / 'source/fpga'
    pins = {}
    for name, raw in sorted(files.items()):
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
        pins[name] = digest(raw)
    m['sources'] = pins
    geometry.closed(source, pins)
    path = output / 'manifest.json'
    with path.open('x') as stream:
        json.dump(m, stream, indent=2)
        stream.write('\n')
    result = dict(status='prepared_observed_lint_repair_not_executed',
        source_files=len(pins), source_bytes=sum(map(len, files.values())),
        manifest_sha256=digest(path.read_bytes()), aw=aw,
        unchanged_original_source_pins=original['sources'],
        repair_source_pins={n: pins[n] for n in (SELF, ENGINE_V2, lookup_v2)},
        native_or_fit_executed=False, promotion_allowed=False)
    with (output / 'preparation.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    geometry.closed(source_root, original['sources'])
    need(Path(manifest_path).read_bytes() == original_raw, 'A10_REPAIR_DONOR_DRIFT')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'source-root', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.manifest, args.source_root, args.output), indent=2))

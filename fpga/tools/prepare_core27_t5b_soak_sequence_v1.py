"""Source-only P1 T5b soak sequence and complete segment preparation.

This is a candidate packet constructor, not a cloud/queue runner. Reference
generation and HDL execution remain on admitted Linux workers. Chunked
arithmetic coverage and the uninterrupted controller/cache/counter gate are
separate evidence classes and can never substitute for one another.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = 'reference/core27_t5b_soak_native_v1.py'
ADAPTER_SHA = '43a35c1bd1c2d256fb793a8087681e9e2c0281441eeca57aa2fd6dfdf7934db0'
HOST_USERS = {'gfn16-pilot-c4d': 'jacenli', 'gfn16-azure-f16': 'azureuser',
              'gfn16-azure-sim-f32': 'azureuser'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def adapter():
    need(sha(ROOT/ADAPTER) == ADAPTER_SHA, 'SOAK_T5B_SEQUENCE_ADAPTER_IDENTITY')
    spec = importlib.util.spec_from_file_location('_t5b_sequence_adapter', ROOT/ADAPTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan():
    module = adapter().reference()
    full = module.make_plan()
    short = module.make_plan(16, 2, 2, 1, full['seed'], full['profile']['base'])
    need(short['double_bits'] == full['double_bits'][:2], 'SOAK_T5B_SEQUENCE_PREFIX')
    gates = [
        dict(id='short-reference', kind='linux-gmpy2-reference', dependencies=[],
             case_id=short['case_id'], squares=2, chunk_squares=2, checkpoint_every=1,
             state='source_ready_not_run', max_seconds=1800),
        dict(id='short-aw16', kind='native-gate', dependencies=['short-reference'],
             case_id=short['case_id'], segment='continuous', operations=2,
             controls=['boundary', 'loaded-state'], state='requires_exact_reference',
             required_pass='T5b source/runtime-bound values, phases/cache, 1/1/1 probe, both typed rc1 controls and wall/user timing'),
        dict(id='full-reference', kind='linux-gmpy2-reference', dependencies=[],
             case_id=full['case_id'], squares=1000, chunk_squares=100, checkpoint_every=100,
             state='source_ready_not_run', max_seconds=1800),
        dict(id='chunk-runtime-admission', kind='resource-gate', dependencies=['short-aw16'],
             state='requires_actual_T5b_timing',
             required_pass='100-square normal-command conservative measured estimate fits admitted finite command/job/outer bounds including build/replay/stop; relabel smaller exact chunks if not'),
    ]
    for chunk in full['chunks']:
        gates.append(dict(id=f"chunk-{chunk['index']:02d}", kind='native-gate',
            dependencies=['full-reference', 'chunk-runtime-admission'], case_id=full['case_id'],
            segment=f"chunk-{chunk['index']:02d}", start=chunk['start'], end=chunk['end'],
            operations=100, controls=[], independent=True,
            state='requires_exact_reference_and_T5b_runtime_admission'))
    gates.extend([
        dict(id='combine-chunks', kind='boundary-combine',
             dependencies=[f"chunk-{chunk['index']:02d}" for chunk in full['chunks']],
             state='requires_all_typed_native_chunk_PASS',
             validator='reference/core27_t5b_soak_v1.py:reference().combine_chunks',
             required_pass='same T5b case/parent, all ten GMP-checked chunks and every adjacent exact residue hash'),
        dict(id='continuous-runtime-admission', kind='resource-gate', dependencies=['short-aw16'],
             state='requires_separate_admitted_finite_long_duration',
             required_pass='separate source/tool-bound 1000-square estimate and admitted duration, host-hours, protected deadline/drain; no timed-out namespace replay'),
        dict(id='continuous-1000', kind='native-gate',
             dependencies=['full-reference', 'continuous-runtime-admission'],
             case_id=full['case_id'], segment='continuous', operations=1000,
             controls=[], reset_count=1, loaded_digits=65536,
             reloads_between_operations=0, state='not_run_separate_required_gate'),
    ])
    return dict(schema='t5b-soak-dependent-sequence-v1', owner='soak-chunks', priority='P1',
        status='source_bound_sequence_not_native_evidence', lineage='promoted-t5b',
        source_hashes={ADAPTER: ADAPTER_SHA, module.SELF: sha(ROOT/module.SELF),
                       module.BENCH: sha(ROOT/module.BENCH), module.HEADER: sha(ROOT/module.HEADER)},
        parent_manifest_sha256=module.PARENT_SHA, full_plan=full, short_plan=short,
        gates=gates, independent_chunk_fanout=True, dispatcher_is_sole_launcher=True,
        current_static_bounds=dict(command_seconds=1800, overall_seconds=3600, outer_seconds=3700),
        frozen_crtmont_results_are_not_T5b_gates=True,
        chunked_coverage_does_not_satisfy_continuous_gate=True, promotion_allowed=False)


def prepare_segments(references, runtime_file, output, short=False):
    """Build every ready manifest in one batch; do not package or dispatch."""
    module = adapter()
    runtime = json.loads(Path(runtime_file).read_text())
    host = runtime['host']
    need(host in HOST_USERS, 'SOAK_T5B_SEQUENCE_RUNTIME_HOST')
    output = Path(output).resolve()
    need(not output.exists(), 'SOAK_T5B_SEQUENCE_FRESH_OUTPUT')
    generation = json.loads((Path(references)/'generation.json').read_text())
    wanted = plan()['short_plan' if short else 'full_plan']
    need(generation['case_id'] == wanted['case_id'], 'SOAK_T5B_SEQUENCE_EXACT_CASE')
    names = ['continuous'] if short else [f'chunk-{i:02d}' for i in range(10)]+['continuous']
    output.mkdir(parents=True)
    result = []
    for name in names:
        receipt = module.stage(references, name, output/name, runtime_file, host,
            '/home/'+HOST_USERS[host]+'/gfn16-worker/native/soak-t5b-sequence-v1', controls=short)
        path = output/name/'serial-manifest.json'
        result.append(dict(segment=name, manifest=str(path), manifest_sha256=sha(path),
            source_root=receipt['source_root'], ready_for_packaging=True,
            ready_for_dispatch=False, runtime_admission_required=True))
    return dict(status='all_T5b_source_manifests_prepared_no_dispatch', lineage='promoted-t5b',
                case_id=wanted['case_id'], segments=result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('plan')
    prepare = commands.add_parser('prepare')
    for name in ('references', 'runtime-file', 'output'):
        prepare.add_argument('--'+name, type=Path, required=True)
    prepare.add_argument('--short', action='store_true')
    args = parser.parse_args()
    result = plan() if args.command == 'plan' else prepare_segments(
        args.references, args.runtime_file, args.output, args.short)
    print(json.dumps(result, indent=2))

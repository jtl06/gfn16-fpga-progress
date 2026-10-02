"""Source-only additive two-thread100-square role; no reference generation.

Use the owner's exact qualified Azure cross-runtime role and unchanged source,
case, integer-reference provenance, validators and cycle contracts. Only the
shared context/model macro and typed probe change. Frozen serial work stays
separate; this finite pilot grants no long1000 or higher-thread admission.
"""
import copy
import hashlib
import json
from pathlib import Path

from ..tools import native_thread_config_v1 as runtime

ROOT = Path(__file__).resolve().parents[1]
ROLE = 'results/throughput-20260929/soak-t5b-aw16-chunk00-cross-burst16-manifest-v2'
MANIFEST_SHA = 'fae262d44c24d2e6d8318d028973bf5fbfa82dbd397f5c9c0d5807c944078f80'
CORE = 'rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1.sv'
CORE_SHA = '704f7fed433d724dbc8e56c7b725824ec36cce78d6ce8f021307837d2a96b8e7'
BENCH = 'rtl/tb/core27_t5b_soak_v1.cpp'
BENCH_SHA = 'c4972670a55bbb0c7b039e7a0175ee6918e5a95f3e0dd4a5a96c7dbc7175fab7'
HEADER = 'rtl/tb/native_runtime_context_v1.h'
HEADER_SHA = 'afd27444d1b4c991d11c84482db08f2fcef62757968e96ac83c5d44e55622f90'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def successor(serial):
    need(serial['schema'] == 'native-source-gate-v1' and serial['status'] == 'prepared_not_executed'
         and serial['host'] == 'gfn16-azure-sim-f32', 'exact bounded target role')
    need(serial['build']['parameters'] == dict(AW=16, NTT_LANES=64)
         and serial['build']['cpp_source'] == BENCH and serial['sources'].get(BENCH) == BENCH_SHA
         and serial['sources'].get(HEADER) == HEADER_SHA and serial['sources'].get(CORE) == CORE_SHA,
         'unchanged promoted T5b exact bench/context/core')
    need(serial['probe']['expected_json'] == runtime.expected_probe(1)
         and all(type(v) is int for v in serial['probe']['expected_json'].values()), 'serial donor typed probe')
    need(len(serial['sources']) == 59 and len(serial['steps']) == 1
         and serial['steps'][0]['name'] == 'soak-normal'
         and serial['steps'][0]['argv'] == ['{exe}', '{root}/soak/chunk-00.txt']
         and serial['steps'][0]['validator']['source'] == 'reference/core27_t5b_soak_cross_runtime_v1.py',
         'normal-only100-square closed role, not changed serial corpus')
    need(serial['soak']['segment'] == 'chunk-00' and serial['soak']['profile']['aw'] == 16,
         'exact bounded chunk')
    value = copy.deepcopy(serial)
    value['build'] = runtime.configure_build(value['build'], 2)
    value['probe']['expected_json'] = runtime.expected_probe(2)
    runtime.validate_build(value['build'], value['probe']['expected_json'])
    value['thread_pilot'] = dict(schema='T5b-soak-two-thread-pilot-v1', evidence_class='prepared_not_executed',
        serial_role_manifest_sha256=MANIFEST_SHA, sources_unchanged=True, validator_references_unchanged=True,
        segment='chunk-00', operations=100, start=0, end=100, expected_cycle_count=2895448,
        scope='separate exploratory two-thread100-square pilot, not replacement chunk coverage or retry',
        long1000_admission=False, higher_thread_admission=False, promotion_allowed=False)
    return value


def prepare(output, root=ROOT):
    root, output = Path(root), Path(output)
    need(output.is_absolute() and output.resolve() == output and not output.exists(), 'fresh canonical pilot output')
    manifest_path, source = root/ROLE/'cross-runtime-manifest.json', root/ROLE/'source/fpga'
    need(sha(manifest_path) == MANIFEST_SHA, 'exact qualified serial/bridge source role')
    serial = json.loads(manifest_path.read_text())
    for name, pin in serial['sources'].items():
        need(sha(source/name) == pin, 'unchanged source/case/reference bytes: '+name)
    # Parse metadata and array lengths only: never import the numeric bridge,
    # convert base**n, square/reduce an integer, execute a model or generate data.
    oracle = json.loads((source/'soak/chunk-00.json').read_text())
    segment = oracle['segment']
    need(segment['name'] == 'chunk-00' and segment['start'] == 0 and segment['end'] == segment['operations'] == 100
         and [(v['step'], len(v['digits'])) for v in segment['checkpoints']] == [(0,65536),(100,65536)],
         'exact100 operations and complete two boundary arrays')
    threaded = successor(serial)
    need(threaded['sources'] == serial['sources'] and threaded['steps'] == serial['steps'], 'source/reference/validator delta forbidden')
    output.mkdir(parents=True)
    raw = (json.dumps(threaded, indent=2)+'\n').encode()
    with (output/'threaded-manifest.json').open('xb') as stream:
        stream.write(raw)
    report = dict(schema='T5b-soak-two-thread-role-preparation-v1', status='prepared_not_executed',
        source_root=str(source.resolve()), serial_manifest=str(manifest_path.resolve()), serial_manifest_sha256=MANIFEST_SHA,
        threaded_manifest_sha256=hashlib.sha256(raw).hexdigest(), source_members=59,
        sources_unchanged=True, compiled_sources_unchanged=True, references_validators_steps_unchanged=True,
        changes={'build.runtime_threads': [None,2], 'build.cflags_added': '-DGFN16_RUNTIME_THREADS=2',
                 'probe.expected_json': [runtime.expected_probe(1),runtime.expected_probe(2)]},
        operation_count=100, expected_cycle_count=2895448, boundary_steps=[0,100],
        native_execution=False, long1000_admission=False, higher_thread_admission=False)
    with (output/'preparation.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    need(sha(manifest_path) == MANIFEST_SHA, 'serial donor drift; new output preserved')
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))

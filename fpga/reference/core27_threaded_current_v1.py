"""Current T5b AW16 normal/targeted thread-aware recipes; source checks only.

Return closed immutable content and finite manifest data for the shared package
owner. No HDL, model, compiler, SSH, cloud or resource reservation is invoked.
The same source bytes serve one/two/four/eight threads; only build flags differ.
"""
import copy
import hashlib
import json
from pathlib import Path

from . import core27_prefill_pipe_v1_prepare as normal
from . import core27_prefill_pipe_qualification_prepare_v1 as qualification
from ..tools import native_harness_adapter_v1 as adapter
from ..tools import native_thread_config_v1 as runtime

ROOT = Path(__file__).resolve().parents[1]
EXPLICIT = 'rtl/tb/core27_prefill_pipe_tail_aw16_runtime_v1.cpp'
SELF = 'reference/core27_threaded_current_v1.py'
TOOLS = ('tools/native_harness_adapter_v1.py', 'tools/native_thread_config_v1.py', 'tools/build_identity_v2.py')
CRTMONT_DONOR = 'results/throughput-20260929/core27-prefetch-r2-rootfused-crtmont-aw16-v1'
CRTMONT_REPORT_SHA = 'd32023abd40f925fade2f4844e7eb57a4cc9fee2c19203ec51569165e8ea3808'
CRTMONT_REVIEW_SHA = 'ec5e1adad36eb815b2525b30f810a1decf760a5ad1d4ec1e43502a7537ea2b0a'


def digest(value):
    return hashlib.sha256(value).hexdigest()


def recipes(threads=1, root=ROOT):
    """All recipes need shared threaded launcher admission before dispatch."""
    root = Path(root)
    if (root/'docs/briefs/PAUSE').exists():
        raise ValueError('brief PAUSE')
    # Both ancestors validate their frozen source derivations and fixtures.
    normal_manifest = normal.manifests(root)['aw16-normal']
    content, encoded, _ = qualification.packet(root)
    targeted_manifest = json.loads(encoded['aw16-anchor'])
    for name, pin in normal_manifest['sources'].items():
        raw = (root/name).read_bytes()
        if digest(raw) != pin:
            raise ValueError('frozen normal source pin ' + name)
        if name in content and raw != content[name]:
            raise ValueError('normal/targeted source closure disagreement')
        content[name] = raw
    for name in (adapter.HEADER, adapter.ADAPTER, SELF, *TOOLS):
        content[name] = (root/name).read_bytes()
    content[adapter.SELECTION] = adapter.implicit_selection(
        'rtl/tb/core27_prefill_pipe_normal_v1.cpp', 'Vcore27_prefill_pipe_probe_v1').encode()
    original = qualification.recipe.AW16_BENCH
    content[EXPLICIT] = adapter.explicit_successor(content[original].decode()).encode()
    pins = {name: digest(raw) for name, raw in sorted(content.items())}
    output = {}
    for name, source_manifest, cpp in (
            ('normal', normal_manifest, adapter.ADAPTER),
            ('targeted', targeted_manifest, EXPLICIT)):
        manifest = copy.deepcopy(source_manifest)
        manifest['sources'] = pins
        manifest['build']['cpp_source'] = cpp
        manifest['build'] = runtime.configure_build(manifest['build'], threads)
        manifest['probe']['expected_json'] = runtime.expected_probe(threads)
        runtime.validate_build(manifest['build'], manifest['probe']['expected_json'])
        manifest['thread_admission'] = dict(
            schema='gfn16-native-thread-admission-v1', evidence_class='prepared_source_only',
            requires='shared successor launcher, exact lint admission, live matching physical allocation and atomic owner locks',
            native_execution=False, promotion_allowed=False)
        output[name] = manifest
    return content, output


def crtmont_recipe(threads=1, root=ROOT, segment=0):
    """Frozen production crtmont source and exact reviewed resetting segment.

    These bytes and cycle checks precede T5b promotion. Source selection never
    substitutes the T5b candidate for the current crtmont production parent.
    """
    root = Path(root)
    if (root/'docs/briefs/PAUSE').exists():
        raise ValueError('brief PAUSE')
    if type(segment) is not int or segment not in (0, 1):
        raise ValueError('exact completed resetting segment')
    report_raw = (root/CRTMONT_DONOR/'report.json').read_bytes()
    review_raw = (root/CRTMONT_DONOR/'independent-review-v1.json').read_bytes()
    if digest(report_raw) != CRTMONT_REPORT_SHA or digest(review_raw) != CRTMONT_REVIEW_SHA:
        raise ValueError('frozen crtmont report/review drift')
    report, review = json.loads(report_raw), json.loads(review_raw)
    if (report['status'] != 'passed' or report['aw'] != 16
            or review['report_sha256'] != CRTMONT_REPORT_SHA
            or review['status'] != 'verified_g4_normal_profile'):
        raise ValueError('reviewed crtmont production source')
    content = {}
    for name, pin in report['sources'].items():
        raw = (root/name).read_bytes()
        if digest(raw) != pin:
            raise ValueError('frozen production source drift ' + name)
        content[name] = raw
    content[CRTMONT_DONOR+'/report.json'] = report_raw
    content[CRTMONT_DONOR+'/independent-review-v1.json'] = review_raw
    vector_name = CRTMONT_DONOR+f'/segment{segment}.txt'
    stdout_name = CRTMONT_DONOR+f'/test-segment{segment}.log'
    for name in (vector_name, stdout_name):
        raw = (root/name).read_bytes()
        if digest(raw) != report['artifacts'][Path(name).name]:
            raise ValueError('exact completed native fixture/stdout')
        content[name] = raw
    if b'\nLOAD ' not in content[vector_name] or b'PASS n=65536 ' not in content[stdout_name]:
        raise ValueError('resetting AW16 native completion contract')
    for name in (adapter.HEADER, adapter.ADAPTER, SELF, *TOOLS):
        content[name] = (root/name).read_bytes()
    top = report['top']
    content[adapter.SELECTION] = adapter.implicit_selection('rtl/tb/'+top.replace('genefer_', '')+'.cpp', 'V'+top).encode()
    build = runtime.configure_build(dict(top=top, sv_sources=report['compiled_source_order'],
        cpp_source=adapter.ADAPTER, parameters=dict(AW=16, NTT_LANES=64),
        cflags=['-std=c++17', '-Werror=return-type']), threads)
    manifest = dict(schema='native-source-gate-v1', status='prepared_not_executed', host='aethia',
        source_root='/home/jtl/gfn-fpga-lab/agent-work/core27-thread-current-v1/snapshot-v1/fpga',
        output_parent='/home/jtl/gfn-fpga-lab/agent-work/core27-thread-current-v1',
        sources={name: digest(raw) for name, raw in sorted(content.items())}, build=build,
        probe=dict(argv=['{exe}', '--runtime-probe'], expected_json=runtime.expected_probe(threads)),
        steps=[dict(name=f'crtmont-segment{segment}', argv=['{exe}', '{root}/'+vector_name, 'profile'],
                    expected_returncode=0, expected_stdout=content[stdout_name].decode(), expected_stderr='')],
        thread_admission=dict(schema='gfn16-native-thread-admission-v1', evidence_class='prepared_source_only',
            requires='shared successor launcher, exact lint admission, live matching physical allocation and atomic owner locks',
            native_execution=False, promotion_allowed=False))
    runtime.validate_build(build, manifest['probe']['expected_json'])
    return content, manifest


def prepare(output, counts=(1, 2), parent='crtmont', root=ROOT):
    """Stage closed role data and manifests locally, with write-once outputs."""
    output = Path(output)
    if not output.is_absolute() or output.resolve() != output or output.exists():
        raise ValueError('fresh canonical thread recipe stage')
    if type(counts) not in (list, tuple) or not counts or len(set(counts)) != len(counts):
        raise ValueError('finite distinct thread configurations')
    if parent not in ('crtmont', 't5b'):
        raise ValueError('explicit existing parent recipe')
    content = None
    manifests = {}
    for count in counts:
        runtime.thread_count(count)
        if parent == 'crtmont':
            candidate, manifest = crtmont_recipe(count, root)
            roles = {'crtmont-segment0': manifest}
        else:
            candidate, roles = recipes(count, root)
        if content is not None and content != candidate:
            raise ValueError('thread variants must share exact source bytes')
        content = candidate
        manifests.update({f'{name}-threads{count}': manifest for name, manifest in roles.items()})
    output.mkdir(parents=True)
    source = output/'source/fpga'
    source.mkdir(parents=True)
    for name, raw in content.items():
        target = source/name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    manifest_pins = {}
    for name, manifest in manifests.items():
        raw = (json.dumps(manifest, indent=2)+'\n').encode()
        with (output/(name+'-manifest.json')).open('xb') as stream:
            stream.write(raw)
        manifest_pins[name+'-manifest.json'] = digest(raw)
    # Re-evaluate immutable ancestors to detect preparation-time input drift.
    latest = crtmont_recipe(counts[0], root)[0] if parent == 'crtmont' else recipes(counts[0], root)[0]
    if latest != content:
        raise ValueError('recipe source drift; failed stage preserved')
    report = dict(schema='core27-current-thread-recipe-stage-v1', status='prepared_not_executed',
        parent=parent, thread_counts=list(counts), source_files=len(content), manifests=manifest_pins,
        identical_sources_across_threads=True, native_execution=False, promotion_allowed=False,
        requirement='Shared package successor, reviewed exact lint debt, scheduler observer, live physical allocation and owner locks remain mandatory.')
    with (output/'preparation.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--parent', choices=('crtmont', 't5b'), default='crtmont')
    parser.add_argument('--threads', type=int, nargs='+', default=[1, 2])
    args = parser.parse_args()
    print(json.dumps(prepare(args.output.resolve(), args.threads, args.parent), indent=2))

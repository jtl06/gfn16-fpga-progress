"""Source-only S4 P3: reviewed promoted-T5b cold/warm AW16 thread pilot.

Copy, hash and truncate complete records from an already qualified native
fixture. No arithmetic oracle, model, HDL compiler or host job is executed.
One/two threads share every source byte, value and cycle expectation.
"""
import copy
import hashlib
import json
from pathlib import Path
import re

from . import core27_t5b_soak_v1 as lineage
from ..tools import native_harness_adapter_v1 as adapter
from ..tools import native_thread_config_v1 as runtime

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/core27_t5b_thread_pilot_v1.py'
DONOR = 'results/throughput-20260929/core27-t5b-aw16-normal-aethia-v1'
REPORT_SHA = '96257f0e110aae95a69b971034eb83ed8abc80c186cc7cd759e70b22a48f6551'
REVIEW_SHA = '55b2819c8496a850c556aa7d72ec4865c51482047a621190b82dea2dc4068a89'
MANIFEST_SHA = '0b5041b80c0242b2e419f3d1392984d6769e1f0c6569f086d34ffebdbe6ac519'
DONOR_STDOUT_SHA = 'a3a138557f3cca042eef5f43ad1767231f7d210c1d0a3eaadb8f60a46e95de8a'
DONOR_VECTOR = 'results/throughput-20260929/core27-prefill-aw16-normal-v1/vectors.txt'
DONOR_VECTOR_SHA = '3449c1e3e1d7c0820842ecb30295b963b4aa81af6b27be8e38b7c87f2bd39f3d'
VECTOR = 'reference/fixtures/core27-t5b-thread-pilot-v1.txt'
STDOUT = 'reference/fixtures/core27-t5b-thread-pilot-v1.stdout.txt'
TOOLS = ('tools/native_harness_adapter_v1.py', 'tools/native_thread_config_v1.py', 'tools/build_identity_v2.py')


def need(ok, why):
    if not ok:
        raise ValueError(why)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pinned(root, name, pin):
    raw = (root/name).read_bytes()
    need(digest(raw) == pin, 'exact T5b pilot donor/lineage pin: '+name)
    return raw


def completed_prefix(vector, stdout):
    """Complete initial load and two full readbacks; no integer arithmetic."""
    need(type(vector) is bytes and len(vector) < 16 * (1 << 20), 'bounded completed T5b fixture')
    lines = vector.splitlines(keepends=True)
    need(lines and lines[0] == b'65536\n', 'full AW16 fixture')
    loads = [i for i, line in enumerate(lines) if line.startswith(b'LOAD ')]
    runs = [i for i, line in enumerate(lines) if line.startswith(b'RUN ')]
    need(len(runs) == 10 and sum(line.startswith(b'RUN_NOREAD ') for line in lines) == 2
         and loads and runs[:3] == [loads[0]+2, loads[0]+4, loads[0]+6],
         'complete cold/warm command boundaries')
    need(lines[loads[0]].split() == [b'LOAD', b'full-random', b'604832956']
         and lines[runs[0]].split() == [b'RUN', b'full-random-s0-d0', b'0']
         and lines[runs[1]].split() == [b'RUN', b'full-random-s1-d1', b'1'], 'reviewed cold/warm control selection')
    for i in (loads[0]+1, runs[0]+1, runs[1]+1):
        words = lines[i].split()
        need(len(words) == 65536 and all(re.fullmatch(rb'-?[0-9]+', word) for word in words),
             'complete frozen load/readback digit record')
    outputs = stdout.splitlines(keepends=True)
    need(len(outputs) == 13 and outputs[-1] == b'PASS n=65536 squares=12 readbacks=10 aborts=0\n',
         'completed qualified T5b stdout')
    for row, tag, cycles, conversion, roots in ((outputs[0], b'full-random-s0-d0', 41674, 4105, 8743),
                                              (outputs[1], b'full-random-s1-d1', 28826, 0, 0)):
        need(row.startswith(tag+b' cycles='+str(cycles).encode()+b' conversion='+str(conversion).encode()+
                            b' roots='+str(roots).encode()+b' ')
             and b' carry=4155 ' in row and row.endswith(b' readback=1\n'), 'exact T5b cold/warm cycles and readbacks')
    return b''.join(lines[:runs[2]]), b''.join(outputs[:2])+b'PASS n=65536 squares=2 readbacks=2 aborts=0\n'


def recipe(threads=1, root=ROOT):
    need(type(threads) is int and threads in (1, 2), 'P3 one/two-thread pilot only')
    root = Path(root)
    need(not (root/'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    need(root.resolve() == lineage.ROOT.resolve(), 'exact promoted lineage root')
    # This function validates source/receipts only, never invokes its numeric oracle.
    _, promoted = lineage.parent_sources()
    raw_report = pinned(root, DONOR+'/report.json', REPORT_SHA)
    raw_review = pinned(root, DONOR+'/independent-review-v1.json', REVIEW_SHA)
    raw_manifest = pinned(root, DONOR+'/approved-manifest.json', MANIFEST_SHA)
    raw_stdout = pinned(root, DONOR+'/aw16-normal.log', DONOR_STDOUT_SHA)
    report, review, donor = map(json.loads, (raw_report, raw_review, raw_manifest))
    need(report['manifest_sha256'] == MANIFEST_SHA and report['sources'] == donor['sources']
         and report['model_threads'] == 1
         and review['status'] == 'PASS_scoped_T5b_AW16_native_normal_and_exact_cycle_delta'
         and review['pins']['report_sha256'] == REPORT_SHA
         and review['pins']['manifest_sha256'] == MANIFEST_SHA
         and review['pins']['native_stdout_sha256'] == DONOR_STDOUT_SHA
         and review['pins']['successor_top_sha256'] == lineage.CORE_SHA, 'qualified promoted T5b native donor identity')
    need(all(report['sources'].get(name) == pin for name, pin in promoted.items()), 'native donor matches all promoted RTL')
    content = {name: pinned(root, name, pin) for name, pin in report['sources'].items()}
    need(digest(content[DONOR_VECTOR]) == DONOR_VECTOR_SHA, 'qualified vector identity')
    vector, stdout = completed_prefix(content[DONOR_VECTOR], raw_stdout)
    content.update({DONOR+'/report.json': raw_report, DONOR+'/independent-review-v1.json': raw_review,
                    DONOR+'/approved-manifest.json': raw_manifest, DONOR+'/aw16-normal.log': raw_stdout,
                    VECTOR: vector, STDOUT: stdout})
    for name, pin in ((lineage.FIT+'/manifest.json', lineage.FIT_SHA), (lineage.FIT+'/probe.qsf', lineage.QSF_SHA),
                      (lineage.AUDIT, lineage.AUDIT_SHA), (lineage.READINESS, lineage.READINESS_SHA),
                      (lineage.ADVISOR, lineage.ADVISOR_SHA)):
        content[name] = pinned(root, name, pin)
    for name in (adapter.HEADER, adapter.ADAPTER, SELF, 'reference/core27_t5b_soak_v1.py', *TOOLS):
        content[name] = (root/name).read_bytes()
    content[adapter.SELECTION] = adapter.implicit_selection('rtl/tb/core27_prefill_pipe_normal_v1.cpp',
                                                           'Vcore27_prefill_pipe_probe_v1').encode()
    build = copy.deepcopy(donor['build'])
    build['cpp_source'] = adapter.ADAPTER
    build = runtime.configure_build(build, threads)
    manifest = dict(schema='native-source-gate-v1', status='prepared_not_executed', host='aethia',
        source_root='/home/jtl/gfn-fpga-lab/agent-work/core27-t5b-thread-pilot-v1/source/fpga',
        output_parent='/home/jtl/gfn-fpga-lab/agent-work/core27-t5b-thread-pilot-v1',
        sources={name: digest(raw) for name, raw in sorted(content.items())}, build=build,
        probe=dict(argv=['{exe}', '--runtime-probe'], expected_json=runtime.expected_probe(threads)),
        steps=[dict(name='t5b-cold-warm', argv=['{exe}', '{root}/'+VECTOR, 'profile'],
                    expected_returncode=0, expected_stdout=stdout.decode(), expected_stderr='')],
        thread_admission=dict(schema='gfn16-native-thread-admission-v1', evidence_class='prepared_source_only',
            parent='promoted-T5b', core_sha256=lineage.CORE_SHA, physical_manifest_sha256=lineage.FIT_SHA,
            benchmark_scope='one cold and one consecutive warm AW16 square, all65536 readbacks each, both control bits and preceding input negatives',
            donor_report_sha256=REPORT_SHA, donor_review_sha256=REVIEW_SHA,
            donor_vector_sha256=DONOR_VECTOR_SHA, donor_stdout_sha256=DONOR_STDOUT_SHA,
            pilot_vector_sha256=digest(vector), pilot_stdout_sha256=digest(stdout),
            requires='exact threaded class successor, admitted same physical pair and host profile, inherited compile/fit/quota/tool/deadline guards',
            native_execution=False, promotion_allowed=False))
    runtime.validate_build(build, manifest['probe']['expected_json'])
    return content, manifest


def prepare(output, root=ROOT):
    output = Path(output)
    need(output.is_absolute() and output.resolve() == output and not output.exists(), 'fresh canonical P3 stage')
    one, a = recipe(1, root)
    two, b = recipe(2, root)
    need(one == two, 'identical P3 source and fixture bytes across thread counts')
    output.mkdir(parents=True)
    source = output/'source/fpga'
    source.mkdir(parents=True)
    for name, raw in one.items():
        target = source/name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    pins = {}
    for count, manifest in ((1, a), (2, b)):
        name = f't5b-cold-warm-threads{count}-manifest.json'
        raw = (json.dumps(manifest, indent=2)+'\n').encode()
        with (output/name).open('xb') as stream:
            stream.write(raw)
        pins[name] = digest(raw)
    need(recipe(1, root)[0] == one, 'source preparation drift; failed output preserved')
    report = dict(schema='core27-t5b-thread-pilot-stage-v1', status='prepared_not_executed',
        parent='promoted-T5b', core_sha256=lineage.CORE_SHA, physical_manifest_sha256=lineage.FIT_SHA,
        source_files=len(one), identical_sources_across_threads=True, thread_counts=[1, 2], manifests=pins,
        pilot_vector_sha256=digest(one[VECTOR]), pilot_stdout_sha256=digest(one[STDOUT]),
        native_execution=False, promotion_allowed=False)
    with (output/'preparation.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))

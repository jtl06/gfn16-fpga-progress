"""Copy the frozen short T5b P3 role for a matched fixed8core 2/4/8 pilot.

Source-only: reads/hashes retained digit records, no numeric oracle imports or
computation, HDL/tool/model execution, host reservation or queue write.
"""
import copy
import hashlib
import json
from pathlib import Path

from ..tools import native_thread_config_v1 as runtime

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/core27_t5b_thread_wide_pilot_v1.py'
ROLE = 'results/throughput-20260929/core27-t5b-thread-pilot-source-v1/t5b-cold-warm-threads1-manifest.json'
ROLE_SHA = '42fb4fde0a6ca2cd7b8c2069c353974656b1bb726f841ce19723597ca6c5b1e6'
DONOR_SOURCE = 'results/throughput-20260929/core27-t5b-thread-pilot-source-v1/source/fpga'
PROFILE = 'azure-burst16-thread-wide07-v1'
THREAD_COUNTS = (2, 4, 8)


def need(ok, why):
    if not ok:
        raise ValueError(why)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def recipe(count, root=ROOT):
    need(type(count) is int and count in THREAD_COUNTS, 'bounded pilot two/four/eight only')
    root = Path(root)
    need(not (root / 'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    raw = (root / ROLE).read_bytes()
    need(digest(raw) == ROLE_SHA, 'frozen original short T5b role identity')
    original = json.loads(raw)
    need(len(original['sources']) == 59 and len(original['steps']) == 1
         and original['steps'][0]['name'] == 't5b-cold-warm', 'reviewed complete 59-source short donor')
    content = {name: (root / DONOR_SOURCE / name).read_bytes() for name in original['sources']}
    need(all(digest(content[name]) == pin for name, pin in original['sources'].items()), 'exact full source and fixture closure')
    content[ROLE] = raw
    content[SELF] = (root / SELF).read_bytes()
    manifest = copy.deepcopy(original)
    manifest['sources'] = {name: digest(value) for name, value in sorted(content.items())}
    # Replace the sole already-exact macro; do not regenerate numeric fixtures.
    manifest['build']['runtime_threads'] = count
    flags = manifest['build']['cflags']
    need(flags.count('-DGFN16_RUNTIME_THREADS=1') == 1, 'original single context macro')
    manifest['build']['cflags'] = [f'-DGFN16_RUNTIME_THREADS={count}' if flag == '-DGFN16_RUNTIME_THREADS=1' else flag for flag in flags]
    manifest['probe']['expected_json'] = runtime.expected_probe(count)
    manifest['thread_admission'].update(evidence_class='prepared_source_only_fixed_wide',
        requires='exact fixed wide runner, source-bound hardware/allocation overlay, dispatcher constituent-pair reservation, all inherited guards')
    manifest['wide_thread_pilot'] = dict(schema='gfn16-fixed-wide-thread-pilot-role-v1',
        thread_count=count, fixed_profile=PROFILE, donor_manifest_sha256=ROLE_SHA,
        placement=dict(id='burst16-wide07-v1', lane_ids=['azure-burst16-static01-v1', 'azure-burst16-static23-v1',
                       'azure-burst16-static45-v1', 'azure-burst16-static67-v1'], cpus=list(range(8))),
        matched_allocation='all counts use identical8physical cores/800percent/8GiB/j2; not a four-core admission',
        scope='one cold and one consecutive warm square, both controls and full65536-digit readbacks',
        native_execution=False, promotion_allowed=False)
    runtime.validate_build(manifest['build'], manifest['probe']['expected_json'])
    need(manifest['steps'] == original['steps'], 'unchanged exact output and cycle contract')
    return content, manifest


def prepare(output, root=ROOT):
    output = Path(output)
    need(output.is_absolute() and output.resolve() == output and not output.exists(), 'fresh canonical fixed-wide source stage')
    recipes = {count: recipe(count, root) for count in THREAD_COUNTS}
    content = recipes[2][0]
    need(all(value[0] == content for value in recipes.values()), 'identical complete source bytes across thread counts')
    output.mkdir(parents=True)
    source = output / 'source/fpga'
    source.mkdir(parents=True)
    for name, raw in content.items():
        destination = source / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(raw)
    pins = {}
    for count, (_, manifest) in recipes.items():
        name = f't5b-cold-warm-threads{count}-manifest.json'
        raw = (json.dumps(manifest, indent=2) + '\n').encode()
        with (output / name).open('xb') as stream:
            stream.write(raw)
        pins[name] = digest(raw)
    need(recipe(2, root)[0] == content, 'source drift; failed preparation retained')
    report = dict(schema='gfn16-t5b-fixed-wide-thread-source-stage-v1', status='prepared_not_executed',
        thread_counts=list(THREAD_COUNTS), source_members=len(content), identical_sources_across_threads=True,
        donor_source_members_unchanged=59, donor_manifest_sha256=ROLE_SHA, manifests=pins,
        fixed_profile=PROFILE, native_execution=False, promotion_allowed=False)
    with (output / 'preparation.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))

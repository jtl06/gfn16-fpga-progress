"""Source-only matched current-crtmont pilot: one reviewed cold AW16 square.

No model, HDL compiler, arithmetic oracle, remote command or reservation runs.
Derive the complete first load/square/readback prefix from an immutable native
five-square fixture; retain all preceding negative host-input checks exactly.
One and two threads share source/fixture bytes and differ only in build config.
"""
import hashlib
import json
from pathlib import Path
import re

from . import core27_threaded_current_v1 as current

SELF = 'reference/core27_current_thread_pilot_v1.py'
VECTOR = 'reference/fixtures/core27-current-thread-pilot-v1.txt'
STDOUT = 'reference/fixtures/core27-current-thread-pilot-v1.stdout.txt'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def completed_prefix(vector, stdout):
    need(type(vector) is bytes and len(vector) < 16 * (1 << 20), 'bounded exact native fixture')
    lines = vector.splitlines(keepends=True)
    need(lines[0] == b'65536\n', 'current AW16 fixture only')
    loads = [index for index, line in enumerate(lines) if line.startswith(b'LOAD ')]
    runs = [index for index, line in enumerate(lines) if line.startswith(b'RUN ')]
    need(len(loads) == 1 and len(runs) == 5 and runs[0] == loads[0] + 2
         and runs[1] == runs[0] + 2, 'frozen complete load/readback command boundary')
    for index in (loads[0] + 1, runs[0] + 1):
        words = lines[index].split()
        need(len(words) == 65536 and all(re.fullmatch(rb'-?[0-9]+', word) for word in words), 'complete exact digit data')
    header = lines[runs[0]].split()
    need(header == [b'RUN', b'full-random-s0-d0', b'0'], 'reviewed first cold square')
    outputs = stdout.splitlines(keepends=True)
    need(len(outputs) == 6 and outputs[0].startswith(header[1] + b' cycles=41663 ')
         and outputs[0].endswith(b' readback=1\n')
         and outputs[-1] == b'PASS n=65536 squares=5 readbacks=5 aborts=0\n', 'completed native donor stdout')
    return b''.join(lines[:runs[1]]), outputs[0] + b'PASS n=65536 squares=1 readbacks=1 aborts=0\n'


def recipe(threads=1, root=current.ROOT):
    need(type(threads) is int and threads in (1, 2), 'matched one/two-thread pilot')
    root = Path(root)
    content, manifest = current.crtmont_recipe(threads, root, segment=0)
    donor_vector = current.CRTMONT_DONOR + '/segment0.txt'
    donor_stdout = current.CRTMONT_DONOR + '/test-segment0.log'
    vector, stdout = completed_prefix(content[donor_vector], content[donor_stdout])
    content[VECTOR], content[STDOUT] = vector, stdout
    content[SELF] = (root / SELF).read_bytes()
    manifest['sources'] = {name: digest(raw) for name, raw in sorted(content.items())}
    manifest['steps'] = [dict(name='crtmont-cold-square', argv=['{exe}', '{root}/' + VECTOR, 'profile'],
                              expected_returncode=0, expected_stdout=stdout.decode(), expected_stderr='')]
    manifest['thread_admission'].update(requires='exact static-threaded successor admission, exclusive host compile lock, physical pair ownership, quota and tool guards',
        benchmark_scope='one complete cold AW16 production crtmont square with all65536 readbacks and preceding negative input checks',
        donor_report_sha256=current.CRTMONT_REPORT_SHA, donor_review_sha256=current.CRTMONT_REVIEW_SHA,
        donor_vector_sha256=digest(content[donor_vector]), donor_stdout_sha256=digest(content[donor_stdout]),
        pilot_vector_sha256=digest(vector), pilot_stdout_sha256=digest(stdout))
    return content, manifest


def prepare(output, root=current.ROOT):
    output = Path(output)
    need(output.is_absolute() and output.resolve() == output and not output.exists(), 'fresh canonical pilot stage')
    one, manifest_one = recipe(1, root)
    two, manifest_two = recipe(2, root)
    need(one == two, 'identical pilot sources across thread configurations')
    output.mkdir(parents=True)
    source = output / 'source/fpga'
    source.mkdir(parents=True)
    for name, raw in one.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    manifest_pins = {}
    for count, manifest in ((1, manifest_one), (2, manifest_two)):
        filename = f'crtmont-cold-threads{count}-manifest.json'
        raw = (json.dumps(manifest, indent=2) + '\n').encode()
        with (output / filename).open('xb') as stream:
            stream.write(raw)
        manifest_pins[filename] = digest(raw)
    need(recipe(1, root)[0] == one, 'preparation source drift')
    result = dict(schema='core27-current-thread-pilot-stage-v1', status='prepared_not_executed',
        thread_counts=[1, 2], source_files=len(one), identical_sources_across_threads=True,
        manifests=manifest_pins, pilot_vector_sha256=digest(one[VECTOR]), pilot_stdout_sha256=digest(one[STDOUT]),
        native_execution=False, promotion_allowed=False)
    with (output / 'preparation.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))

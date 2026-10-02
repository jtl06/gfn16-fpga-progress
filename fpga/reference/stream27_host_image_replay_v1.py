"""Read-only owner replay of actual paired host native evidence, not promotion."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

from fpga.reference import stream27_host_image_native_v1 as native
from fpga.tools import native_gate_receipt_v1 as gate


def generated_closure(path, expected):
    seen = set()
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            relative = PurePosixPath(member.name)
            native.model.need(member.isfile() and not relative.is_absolute() and '..' not in relative.parts and
                              member.name not in seen and member.name in expected,
                              'HOST_IMAGE_GENERATED_MEMBER')
            seen.add(member.name)
            native.model.need(hashlib.sha256(archive.extractfile(member).read()).hexdigest() == expected[member.name],
                              'HOST_IMAGE_GENERATED_SHA')
    native.model.need(seen == set(expected), 'HOST_IMAGE_GENERATED_CLOSURE')
    return len(seen)


def replay(aw, p):
    native.contracts(aw, p)
    identifier = f's4-host-image-aw{aw}-p{p}-q1-v1'
    done = json.loads((native.ROOT/'queue/done'/f'{identifier}.json').read_text())
    package = done['package']; result = done['result']
    worker = Path(result['evidence'])/'output/native'
    native.model.need(result['status'] == 'needs_independent_review' and
                      result['properties']['ExecMainStatus'] == '0' and
                      result['properties']['MainPID'] == '0', 'HOST_IMAGE_ACTUAL_TERMINAL')
    packet = Path(package['archive']).parent; manifest = packet/'manifest.json'
    native.model.need(gate.sha(manifest) == package['manifest_sha256'] and
                      gate.sha(packet/'package.tar.gz') == package['sha256'], 'HOST_IMAGE_SELECTED_PACKAGE')
    contract = gate.make_contract(identifier, manifest)
    fresh = gate.validate_result(contract, worker/'report.json', id=identifier)
    saved = json.loads((native.ROOT/'queue/evidence'/identifier/'gate-receipt.json').read_text())
    native.model.need(fresh == saved, 'HOST_IMAGE_MACHINE_RECEIPT_REPLAY')
    report = json.loads((worker/'report.json').read_text())
    for name, pin in native.PINS.items():
        native.model.need(report['sources'][name] == pin, 'HOST_IMAGE_SOURCE_PIN ' + name)
    for negative in (False, True):
        name = 'host-image-negative-oracle' if negative else 'host-image-normal'
        row = next(step for step in report['steps'] if step['name'] == name)
        native.validate((worker/row['log']).read_text(), (worker/row['stderr_log']).read_text(),
                        row['returncode'], dict(aw=aw, p=p, negative=negative), {})
    generated = generated_closure(worker/'generated-sources.tar.gz', report['generated_source_sha256'])
    with gzip.open(worker/'model.gz', 'rb') as stream:
        raw = stream.read()
        native.model.need(raw[:4] == b'\x7fELF' and hashlib.sha256(raw).hexdigest() == report['executable_sha256'],
                          'HOST_IMAGE_NATIVE_ELF_IDENTITY')
    for key in ('lint_admission', 'build_admission'):
        native.model.need(not report[key]['fatal_class_counts'] and not report[key]['unknown_class_counts'] and
                          not report[key]['error_streams'], 'HOST_IMAGE_DEFECT_CLASSES')
    return dict(id=identifier, status='PASS_owner_exploration_replay',
                report_sha256=gate.sha(worker/'report.json'),
                gate_sha256=gate.sha(native.ROOT/'queue/evidence'/identifier/'gate-receipt.json'),
                archive_sha256=result['archive_sha256'], sources=len(report['sources']),
                generated=generated, artifacts=len(report['artifacts']),
                invocation=result['properties']['InvocationID'], properties=result['properties'],
                counts=native.contracts(aw, p)['counts'], native_seconds=report['seconds'],
                steps=[dict(name=step['name'], seconds=step['seconds'], returncode=step['returncode'])
                       for step in report['steps']], limits=report['limits'], tool_sha256=report['tool_sha256'],
                style_counts=report['lint_admission']['style_class_counts'], promotion_allowed=False,
                scope='Actual promoted-T5b paired idle host only; start=0. E0/II1 scalar-row component contract, not whole arithmetic/physical/full-N qualification.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aw', type=int, choices=(5, 8), required=True)
    parser.add_argument('--p', type=int, choices=(8, 16), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = replay(args.aw, args.p)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(result, indent=2))

"""Read-only owner replay of actual component evidence; never executes ELF."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

from fpga.reference import a10_upper_sum_native_v2 as native
from fpga.reference import a10_upper_sum_prepare_v2 as prepare
from fpga.tools import native_gate_receipt_v1 as gate


def generated_closure(path, expected):
    seen = set()
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            relative = PurePosixPath(member.name)
            native.need(member.isfile() and not relative.is_absolute() and '..' not in relative.parts and
                        member.name not in seen and member.name in expected, 'A10_UPPER_SUM_GENERATED_MEMBER')
            seen.add(member.name)
            native.need(hashlib.sha256(archive.extractfile(member).read()).hexdigest() == expected[member.name],
                        'A10_UPPER_SUM_GENERATED_SHA')
    native.need(seen == set(expected), 'A10_UPPER_SUM_GENERATED_CLOSURE')
    return len(seen)


def replay(field):
    native.contracts(field); identifier = prepare.identifier(field)
    done = json.loads((native.ROOT/'queue/done'/f'{identifier}.json').read_text())
    package = done['package']; result = done['result']; worker = Path(result['evidence'])/'output/native'
    native.need(result['status'] == 'needs_independent_review' and
                result['properties']['ExecMainStatus'] == '0' and result['properties']['MainPID'] == '0',
                'A10_UPPER_SUM_ACTUAL_TERMINAL')
    packet = Path(package['archive']).parent; manifest = packet/'manifest.json'
    native.need(gate.sha(manifest) == package['manifest_sha256'] and
                gate.sha(packet/'package.tar.gz') == package['sha256'], 'A10_UPPER_SUM_SELECTED_PACKAGE')
    contract = gate.make_contract(identifier, manifest)
    fresh = gate.validate_result(contract, worker/'report.json', id=identifier)
    saved = json.loads((native.ROOT/'queue/evidence'/identifier/'gate-receipt.json').read_text())
    native.need(fresh == saved, 'A10_UPPER_SUM_MACHINE_RECEIPT_REPLAY')
    report = json.loads((worker/'report.json').read_text())
    for name, pin in native.PINS.items():
        native.need(report['sources'][name] == pin, 'A10_UPPER_SUM_SOURCE_PIN ' + name)
    for negative in (False, True):
        name = 'upper-sum-negative-oracle' if negative else 'upper-sum-normal'
        row = next(step for step in report['steps'] if step['name'] == name)
        native.validate((worker/row['log']).read_text(), (worker/row['stderr_log']).read_text(),
                        row['returncode'], dict(field=field, negative=negative), {})
    generated = generated_closure(worker/'generated-sources.tar.gz', report['generated_source_sha256'])
    with gzip.open(worker/'model.gz', 'rb') as stream:
        raw = stream.read()
        native.need(raw[:4] == b'\x7fELF' and hashlib.sha256(raw).hexdigest() == report['executable_sha256'],
                    'A10_UPPER_SUM_NATIVE_ELF_IDENTITY')
    for key in ('lint_admission', 'build_admission'):
        native.need(not report[key]['fatal_class_counts'] and not report[key]['unknown_class_counts'] and
                    not report[key]['error_streams'], 'A10_UPPER_SUM_DEFECT_CLASSES')
    return dict(id=identifier, status='PASS_owner_exploration_replay', field=field,
                report_sha256=gate.sha(worker/'report.json'),
                gate_sha256=gate.sha(native.ROOT/'queue/evidence'/identifier/'gate-receipt.json'),
                archive_sha256=result['archive_sha256'], sources=len(report['sources']),
                generated=generated, artifacts=len(report['artifacts']),
                invocation=result['properties']['InvocationID'], properties=result['properties'],
                counts=native.contracts(field)['counts'], native_seconds=report['seconds'],
                steps=[dict(name=step['name'], seconds=step['seconds'], returncode=step['returncode'])
                       for step in report['steps']], limits=report['limits'], tool_sha256=report['tool_sha256'],
                style_counts=report['lint_admission']['style_class_counts'], promotion_allowed=False,
                scope='Actual old/new/oracle canonical BF pair, exact k+5/II1 and reset ages0..6. No engine/full-N/fit/clock/board/promotion claim.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--field', type=int, choices=range(3), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = replay(args.field)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(result, indent=2))

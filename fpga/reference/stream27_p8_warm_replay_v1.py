"""Owner exploration replay of actual P8 field artifacts, not promotion."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

from fpga.reference import stream27_p8_warm_native_v1 as native
from fpga.reference import stream27_p8_warm_prepare_v1 as prepare
from fpga.tools import native_gate_receipt_v1 as gate


def archive_closure(path, expected):
    seen = set()
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            relative = PurePosixPath(member.name)
            native.need(member.isfile() and not relative.is_absolute() and '..' not in relative.parts and
                        member.name not in seen and member.name in expected, 'P8_WARM_ARCHIVE_MEMBER')
            seen.add(member.name)
            native.need(hashlib.sha256(archive.extractfile(member).read()).hexdigest() == expected[member.name],
                        'P8_WARM_ARCHIVE_SHA')
    native.need(seen == set(expected), 'P8_WARM_ARCHIVE_CLOSURE')
    return len(seen)


def replay(aw, field):
    native.contracts(aw, field); identifier = prepare.identifier(aw, field)
    done = json.loads((native.ROOT/'queue/done'/f'{identifier}.json').read_text())
    package = done['package']; result = done['result']; worker = Path(result['evidence'])/'output/native'
    native.need(result['status'] == 'needs_independent_review' and result['properties']['ExecMainStatus'] == '0' and
                result['properties']['MainPID'] == '0', 'P8_WARM_ACTUAL_TERMINAL')
    packet = Path(package['archive']).parent; manifest_path = packet/'manifest.json'
    native.need(gate.sha(manifest_path) == package['manifest_sha256'] and
                gate.sha(packet/'package.tar.gz') == package['sha256'], 'P8_WARM_SELECTED_PACKAGE')
    manifest = json.loads(manifest_path.read_text()); profile = manifest['p8_warm']
    native.need(profile['aw'] == aw and profile['field'] == field and profile['p'] == 8 and
                manifest['build']['parameters'] == dict(AW=aw, P=8, CONTEXTS=1), 'P8_WARM_BUILD_CONFIGURATION')
    contract = gate.make_contract(identifier, manifest_path)
    fresh = gate.validate_result(contract, worker/'report.json', id=identifier)
    native.need(fresh == json.loads((native.ROOT/'queue/evidence'/identifier/'gate-receipt.json').read_text()),
                'P8_WARM_MACHINE_RECEIPT_REPLAY')
    report = json.loads((worker/'report.json').read_text()); measured = native.verify()
    for name, pin in profile['generated_sha256'].items():
        native.need(report['sources']['rtl/'+name] == pin, 'P8_WARM_ACTUAL_RTL_PIN ' + name)
    native.need(report['sources'][native.REFERENCE] == native.PINS[native.REFERENCE] and
                report['sources']['lineage/'+native.BENCH] == native.PINS[native.BENCH] and
                report['sources']['lineage/'+native.BENCH_PARENT] == native.PINS[native.BENCH_PARENT],
                'P8_WARM_FROZEN_ORACLE_LINEAGE')
    if aw == 16:
        native.need(profile['generated_sha256'] == measured['source_sha256'] and
                    profile['geometry'] == measured['geometry'], 'P8_WARM_ACTUAL_MEASURED_23_RTL')
    for negative in (False, True):
        name = 'p8-warm-negative-oracle' if negative else 'p8-warm-normal'
        row = next(step for step in report['steps'] if step['name'] == name)
        native.validate((worker/row['log']).read_text(), (worker/row['stderr_log']).read_text(), row['returncode'],
                        dict(aw=aw, field=field, negative=negative), {})
    sources = archive_closure(worker/'sources.tar.gz', report['sources'])
    generated = archive_closure(worker/'generated-sources.tar.gz', report['generated_source_sha256'])
    with gzip.open(worker/'model.gz', 'rb') as stream:
        raw = stream.read()
        native.need(raw[:4] == b'\x7fELF' and hashlib.sha256(raw).hexdigest() == report['executable_sha256'],
                    'P8_WARM_ELF_IDENTITY')
    for key in ('lint_admission', 'build_admission'):
        native.need(not report[key]['fatal_class_counts'] and not report[key]['unknown_class_counts'] and
                    not report[key]['error_streams'], 'P8_WARM_DEFECT_CLASSES')
    return dict(id=identifier, status='PASS_owner_exploration_replay', aw=aw, p=8, field=field,
                report_sha256=gate.sha(worker/'report.json'),
                gate_sha256=gate.sha(native.ROOT/'queue/evidence'/identifier/'gate-receipt.json'),
                archive_sha256=result['archive_sha256'], sources=sources, generated=generated,
                artifacts=len(report['artifacts']), invocation=result['properties']['InvocationID'],
                properties=result['properties'], counts=native.counts(aw, field), geometry=profile['geometry'],
                generated_sha256=profile['generated_sha256'], exact_23_measured_RTL=aw == 16,
                native_seconds=report['seconds'], steps=[dict(name=s['name'], seconds=s['seconds'], returncode=s['returncode'])
                                                        for s in report['steps']],
                limits=report['limits'], tool_sha256=report['tool_sha256'], style_counts=report['lint_admission']['style_class_counts'],
                promotion_allowed=False, scope='One-field P8 actual arithmetic/schedule component only, no full core/PRP/clock promotion.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aw', type=int, choices=(8, 16), required=True)
    parser.add_argument('--field', type=int, choices=range(3), required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = replay(args.aw, args.field)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(result, indent=2))

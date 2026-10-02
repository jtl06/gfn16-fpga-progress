"""Offline evidence checks; does not rerun RTL or claim a complete PRP test."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

from .stream27_longchain import CORE_SHA, GATE_SHA, validate_log


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verify(directory, gate_directory, runner):
    report = json.loads((directory / 'report.json').read_text())
    gate_path = gate_directory / 'report.json'
    gate = json.loads(gate_path.read_text())
    if digest(gate_path) != GATE_SHA or report['gate_sha256'] != GATE_SHA:
        raise ValueError('gate hash mismatch')
    if report['core_sha256'] != CORE_SHA or gate['status'] != 'passed':
        raise ValueError('wrong core or failed ancestor gate')
    if report['status'] != 'passed' or report['returncode'] != 0 or report['sources_rechecked'] is not True:
        raise ValueError('incomplete simulation')
    if report['sources'] != gate['sources']:
        raise ValueError('source closure changed')
    if digest(runner) != report['runner_sha256']:
        raise ValueError('runner mismatch')
    builds = [b for b in gate['builds'] if b['name'] == 'build-aw16']
    if len(builds) != 1 or builds[0]['executable_sha256'] != report['executable_sha256']:
        raise ValueError('executable not linked to the frozen build')
    archive = gate_directory / 'source-snapshot.tar.gz'
    with tarfile.open(archive) as source:
        for name, expected in report['sources'].items():
            members = [m for m in source.getmembers() if m.name == name]
            if len(members) != 1 or not members[0].isfile():
                raise ValueError('missing/ambiguous source: ' + name)
            with source.extractfile(members[0]) as stream:
                if hashlib.sha256(stream.read()).hexdigest() != expected:
                    raise ValueError('archived source mismatch: ' + name)
    if digest(directory / 'vectors.txt') != report['vectors']['sha256']:
        raise ValueError('vector mismatch')
    if digest(directory / 'simulation.log') != report['log_sha256']:
        raise ValueError('log mismatch')
    metadata = report['vectors']
    if (metadata['n'], metadata['squares'], metadata['readbacks']) != (65536, 128, 16):
        raise ValueError('unexpected coverage')
    if len(metadata['cases']) != 4 or any(c['operations'] != 32 or c['direct_pow_checked'] is not True for c in metadata['cases']):
        raise ValueError('unexpected chain coverage')
    metrics = validate_log((directory / 'simulation.log').read_text(), metadata)
    if metrics != report['metrics']:
        raise ValueError('reported metrics disagree with log')
    return dict(status='verified', report_sha256=digest(directory / 'report.json'),
                log_sha256=report['log_sha256'], vectors_sha256=metadata['sha256'],
                source_archive_sha256=digest(archive), source_count=len(report['sources']),
                gate_sha256=GATE_SHA, core_sha256=CORE_SHA,
                squares=128, readbacks=16, chain_lengths=[32] * 4,
                simulation_seconds=report['seconds'],
                warm_cycles=sorted({x['cycles'] for x in metrics if x['roots'] == 0}),
                cold_cycles=sorted({x['cycles'] for x in metrics if x['roots'] != 0}),
                limitations=['Four finite simulation chains, not a complete PRP test.',
                             'Only 16 checkpoints read back; other steps retain internal state.',
                             'Executable provenance follows the prior gate; no new compilation or RTL execution.',
                             'No physical timing, hardware throughput, or PrimeGrid validation claim.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--gate-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt = verify(args.directory, args.gate_directory, Path(__file__).with_name('stream27_longchain.py'))
    with args.output.open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()

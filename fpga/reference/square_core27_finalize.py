"""Narrow final gate for the caught quarter fault's omitted diagnostic.

The failed recovery report remains unchanged. Re-run the precise fault and an
unmutated matching AW7 baseline; retain every preceding completed step with its
original evidence path. Never turn an arbitrary failed report into a pass.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import resource
import socket
import subprocess
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if socket.gethostname() != 'aethia':
        raise RuntimeError('aethia only')
    resource.setrlimit(resource.RLIMIT_AS, (6 << 30, 6 << 30))
    root = Path(__file__).resolve().parents[1]
    previous, out = args.previous.resolve(), args.output.resolve()
    original_path = previous / 'report.json'
    original = json.loads(original_path.read_text())
    if original['status'] != 'failed' or original.get('error') != "RuntimeError('reject-host-quarter mutant escaped')":
        raise ValueError('not the exact diagnostic-only failed gate')
    final_step = original['steps'][-1]
    if final_step['name'] != 'reject-host-quarter' or final_step['returncode'] != -6:
        raise ValueError('unexpected final rejection')
    diagnostic = 'Assertion failed in TOP.genefer_square_core27.unnamedblk3: residue mask skew'
    if diagnostic not in Path(final_step['evidence_log']).read_text():
        raise ValueError('expected assertion absent')
    rejects = [item for item in original['steps'] if item['rejection']]
    if len(rejects) != 15 or any(item['returncode'] == 0 for item in rejects):
        raise ValueError('missing earlier fault evidence')
    if any(item.get('timed_out') or (not item['rejection'] and item['returncode']) for item in original['steps']):
        raise ValueError('another failed step is not covered')
    if original['recovery']['completed_case_ids'] != original['recovery']['original_case_ids']:
        raise ValueError('incomplete recovered normal cases')
    inputs = {str(root / name): value for name, value in original['sources'].items()}
    inputs.update(original['mutation_sources'])
    inputs[str(original_path)] = sha(original_path)
    mutant = Path(final_step['command'][0])
    inputs[str(mutant)] = original['built_executables']['build-mutant-host-quarter']
    vectors = Path(final_step['command'][1])
    inputs[str(vectors)] = sha(vectors)
    def verify():
        for name, expected in inputs.items():
            if sha(name) != expected:
                raise ValueError('identity changed: ' + name)
    verify()
    out.mkdir(parents=True, exist_ok=False)
    report = copy.deepcopy(original)
    report.update(status='running')
    report.pop('error', None)
    report['finalization'] = dict(previous_report=str(original_path), previous_sha256=sha(original_path),
        previous_status='failed', previous_error=original['error'],
        reason='Expected residue-mask assertion was missing from rejection allowlist.',
        inputs=inputs, helper_sha256=sha(__file__))
    report['sources']['reference/square_core27_finalize.py'] = sha(__file__)
    def run(name, command, reject=False):
        before = time.monotonic()
        result = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=600)
        path = out / (name + '.log')
        path.write_text(result.stdout)
        report['steps'].append(dict(name=name, command=command, returncode=result.returncode,
            rejection=reject, seconds=time.monotonic()-before, evidence_log=str(path),
            origin='executed_diagnostic_finalization'))
        print(name, result.returncode, result.stdout[-700:], flush=True)
        if reject:
            if result.returncode != -6 or diagnostic not in result.stdout:
                raise RuntimeError('precise quarter assertion did not recur')
        elif result.returncode:
            raise RuntimeError(name + ' failed')
        return result.stdout
    try:
        build_step = next(item for item in original['steps'] if item['name']=='build-mutant-host-quarter')
        command = list(build_step['command'])
        directory = out / 'build-normal-aw7'
        command[command.index('--Mdir')+1] = str(directory)
        mutated_host = str(previous / 'mutant-host-quarter.sv')
        if command.count(mutated_host) != 1:
            raise ValueError('unexpected quarter build closure')
        command[command.index(mutated_host)] = str(root / 'rtl/kernel/genefer_ntt_banked27_host_engine.sv')
        run('build-normal-aw7', command)
        executable = directory / 'Vgenefer_square_core27'
        report['finalization']['baseline_executable_sha256'] = sha(executable)
        output = run('test-normal-aw7', [str(executable), str(vectors), 'cache'])
        if 'PASS n=128 squares=12 readbacks=10 aborts=0' not in output:
            raise RuntimeError('matching AW7 baseline incomplete')
        run('reject-host-quarter-exact', list(final_step['command']), True)
        verify()
        report['status'] = 'passed'
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()

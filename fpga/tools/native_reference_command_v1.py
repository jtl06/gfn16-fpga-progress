"""Finite F2 reference-data command using the existing static host guard.

No HDL and no remote transport. The dispatcher must stage immutable sources,
admit host-hours, and launch this inside the configured bounded systemd unit.
This initial envelope accepts the existing F2 config only, not arbitrary shell
commands or a new simulation runner. Reference outputs still need their importer.
"""
import argparse
from contextlib import ExitStack
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
STATIC_SHA = '5b1b0f0dc584df8d6887235a9ddf1610f4956823aa84131438de7b8054f1e0ab'
DATA_SHA = 'aa3567a647adf0501f2bc33a98bb1f8b9ff39d7cc0e4d59ea7754c8252dc5e64'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate(config):
    need(config['schema'] == 'F2-reference-data-config-v3', 'reference config schema')
    need(config['numeric_reference_only'] is True and config['HDL_executed'] is False
         and config['promotion_allowed'] is False, 'reference-only scope')
    need(config['profile'] in ('gcp-c4d-static01-v1', 'gcp-c4d-static23-v1'), 'admitted reference profile')
    need(type(config['aw']) is int and config['aw'] in (5, 8, 16)
         and type(config['field']) is int and 0 <= config['field'] < 3, 'bounded geometry')
    root = Path(config['source_root'])
    work = Path(config['working_directory'])
    out = Path(config['expected_output_root'])
    need(root.is_absolute() and root.name == 'fpga' and root.parent == work
         and out.parent == work.parent and out.name == 'output'
         and '..' not in root.parts and '..' not in out.parts, 'reference namespace')
    files = [f'field-aw{config["aw"]}-f{config["field"]}-vectors.txt',
             f'field-aw{config["aw"]}-f{config["field"]}-vector-receipt-v3.json']
    need(config['expected_files'] == files, 'exact reference outputs')
    argv = ['/usr/bin/python3.14', '-B', '-m', 'fpga.reference.root_lookahead_field_data_v3',
            '--aw', str(config['aw']), '--field', str(config['field']), '--profile', config['profile'],
            '--output', str(out / files[0]), '--receipt', str(out / files[1])]
    need(config['argv'] == argv, 'exact reference command, no shell or alternate module')
    need(config['containment'] == dict(cpu_quota_percent=200, memory_bytes=8 << 30,
         swap_bytes=0, runtime_seconds=1800, stop_seconds=15, kill_mode='control-group'), 'fixed finite caps')
    need(config['sources'].get('tools/native_static_v1.py') == STATIC_SHA
         and config['sources'].get('reference/root_lookahead_field_data_v3.py') == DATA_SHA, 'frozen guards and generator')
    for name, digest in config['sources'].items():
        p = PurePosixPath(name)
        need(not p.is_absolute() and '..' not in p.parts and str(p) == name
             and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest), 'safe source pin')
    return root, work, out


def check_sources(root, sources):
    need(root.is_dir() and root.resolve() == root, 'canonical source directory')
    actual = {}
    for path in root.rglob('*'):
        need(not path.is_symlink(), 'no source symlinks')
        if path.is_file():
            actual[str(path.relative_to(root))] = sha(path)
    need(actual == sources, 'complete immutable reference source snapshot')


def load_static(root):
    path = root / 'tools/native_static_v1.py'
    need(sha(path) == STATIC_SHA, 'static guard hash')
    spec = importlib.util.spec_from_file_location('_reference_static_guard', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def profile_binding(config, selected):
    need(config['expected_hostname'] == selected['host']
         and config['expected_user'] == selected['user']
         and config['physical_cpus'] == selected['cpus']
         and config['runtime_sha256'] == selected['hashes']['python']
         and config['static_profile_sha256'] == selected['profile_sha256'], 'actual selected profile binding')
    locks = [dict(path=selected['interop'], mode='SH'), dict(path=selected['pair_lock'], mode='EX')]
    locks += [dict(path=p, mode='EX') for p in selected['physical_locks']]
    need(config['locks'] == locks, 'exact shared physical locks')
    need(config['scratch_reservation_bytes'] == selected['scratch_reservation_bytes']
         and config['scratch_floor_bytes'] == selected['scratch_floor_bytes'], 'scratch reservation and floor')


def run(path, pin):
    need(platform.system() == 'Linux', 'reference execution requires Linux worker')
    path = Path(path)
    need(path.is_absolute() and path.resolve() == path and sha(path) == pin, 'pinned reference config')
    config = json.loads(path.read_text())
    root, work, out = validate(config)
    check_sources(root, config['sources'])
    static = load_static(root)
    selected = static.profile(config['profile'])
    profile_binding(config, selected)
    need(Path.cwd() == work and work.resolve() == work and not out.exists(), 'exact cwd and fresh output')
    need(out.is_relative_to(Path(selected['base']))
         and Path(sys.executable).resolve() == Path(config['argv'][0]).resolve()
         and sha(sys.executable) == config['runtime_sha256'], 'native namespace and runtime identity')
    need(not (Path(selected['base']) / 'PAUSE').exists() and not (root / 'docs/briefs/PAUSE').exists(), 'native PAUSE')
    limits = static.execution_limits(selected)
    base = static.load('tools/native_shared_v1.py')
    with ExitStack() as stack:
        for lock in config['locks']:
            stack.enter_context(base.lock(Path(lock['path']), lock['mode'] == 'SH'))
        static.check_scratch_quota(Path(selected['scratch_base']), 0, 0, selected)
        static.check_scratch_quota(out.parent, 0, 0, selected)
        check_sources(root, config['sources'])
        need(sha(path) == pin, 'config stable before execution')
        out.mkdir()
        started = time.monotonic()
        result = dict(schema='native-reference-command-v1', config_sha256=pin,
                      status='failed', HDL_executed=False, promotion_allowed=False,
                      limits=limits, sources=config['sources'], outputs={})
        try:
            with (out / 'command.stdout').open('xb') as stdout, (out / 'command.stderr').open('xb') as stderr:
                env = dict(PATH='/usr/bin:/bin', PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1',
                           LC_ALL='C', LANG='C', PYTHONPATH=str(work))
                process = subprocess.Popen(config['argv'], cwd=work, env=env, stdin=subprocess.DEVNULL,
                                           stdout=stdout, stderr=stderr, start_new_session=True)
                try:
                    code = process.wait(timeout=1785)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise ValueError('bounded reference command timed out')
            result['returncode'] = code
            need(code == 0, 'reference command failed')
            check_sources(root, config['sources'])
            need(sha(path) == pin, 'config stable after execution')
            for name in config['expected_files']:
                output = out / name
                need(output.is_file() and not output.is_symlink() and output.stat().st_size <= 256 << 20,
                     'bounded regular output: ' + name)
                result['outputs'][name] = dict(sha256=sha(output), bytes=output.stat().st_size)
            result['status'] = 'completed_reference_command_needs_import_validation'
        except Exception as error:
            result['error'] = str(error)
        finally:
            result['elapsed_seconds'] = time.monotonic() - started
            for name in ('command.stdout', 'command.stderr'):
                if (out / name).is_file():
                    result['outputs'][name] = dict(sha256=sha(out / name), bytes=(out / name).stat().st_size)
            with (out / 'command-report.json').open('x') as stream:
                json.dump(result, stream, indent=2)
                stream.write('\n')
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--config-sha256', required=True)
    args = parser.parse_args()
    report = run(args.config, args.config_sha256)
    print(json.dumps(report))
    raise SystemExit(0 if report['status'] == 'completed_reference_command_needs_import_validation' else 1)

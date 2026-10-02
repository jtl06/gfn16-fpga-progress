"""Optional process-level parallelism for future, independently gated tests.

Not used by any current FPGA gate. The caller owns host/cgroup authorization,
resource reservations, source pins and the semantic oracle. Each model still
has its original thread count. No cached correctness or speedup is asserted.
"""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

LABELS = ('baseline', 'candidate')


def _stop_groups(processes):
    # start_new_session=True gives each owned command a private process group.
    # Also reap descendants if their parent exited before the peer failed.
    for process in processes.values():
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for process in processes.values():
        process.wait()


def _publish_exclusive(path, result):
    """Publish a complete receipt atomically, without replacing an old one."""
    fd, temporary = tempfile.mkstemp(prefix='.receipt-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)  # Fails if a receipt already exists.
    finally:
        os.unlink(temporary)  # Only the temporary file created just above.


def run_pair(output, command_factories, *, timeout, guard, verify):
    """Run two normal cases concurrently, then invoke the mandatory oracle.

    factories are {baseline: fn(dump_path)->argv, candidate: fn(...)->argv}.
    verify receives {label: {log: Path, dump: Path}} and must raise on any
    semantic/counter/output mismatch, returning a JSON-serializable dictionary.
    Nonzero exits are ALWAYS failures here, not expected-fault successes.
    guard executes before dispatch and during polling, in the caller's thread.
    This helper never edits the caller's shared report or active gate.
    """
    if set(command_factories) != set(LABELS):
        raise ValueError('exactly baseline and candidate are required')
    if not callable(guard) or not callable(verify) or not 0 < timeout < float('inf'):
        raise ValueError('finite timeout and explicit resource guard/oracle required')
    output = Path(output).resolve()
    guard()
    output.mkdir(parents=True, exist_ok=False)
    files = {label: {'log': output / (label + '.log'),
                     'dump': output / (label + '.dump')} for label in LABELS}
    result = {'status': 'failed', 'processes': {}, 'verification': None,
              'scope': 'Concurrent process pair; caller-defined semantic oracle'}
    processes = {}
    groups_stopped = False
    began = time.monotonic()
    environment = os.environ.copy()
    for name in ('NTT_NONCANON', 'NTT_SKIP_HOST_FUZZ'):
        environment.pop(name, None)
    result['sanitized_environment_keys'] = ['NTT_NONCANON', 'NTT_SKIP_HOST_FUZZ']
    try:
        with ExitStack() as logs:
            for label in LABELS:
                guard()
                command = list(command_factories[label](files[label]['dump']))
                if not command or not all(isinstance(arg, str) for arg in command):
                    raise ValueError('commands must be nonempty string argv lists')
                result['processes'][label] = {'command': list(command)}
                stream = logs.enter_context(files[label]['log'].open('xb'))
                process = subprocess.Popen(command, cwd=output, env=environment,
                    stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                processes[label] = process
                result['processes'][label]['pid'] = process.pid
            while True:
                statuses = {label: process.poll() for label, process in processes.items()}
                if any(code is not None and code != 0 for code in statuses.values()):
                    raise RuntimeError('normal pair command failed: ' + repr(statuses))
                if all(code is not None for code in statuses.values()):
                    break
                if time.monotonic() - began > timeout:
                    raise TimeoutError('normal pair deadline exceeded')
                guard()
                time.sleep(.02)
            _stop_groups(processes)
            groups_stopped = True
        guard()
        for paths in files.values():
            for path in paths.values():
                if not path.is_file() or path.is_symlink():
                    raise RuntimeError('missing or nonregular pair output: ' + str(path))
        verification = verify(files)
        if not isinstance(verification, dict):
            raise TypeError('oracle must return a verification dictionary')
        json.dumps(verification)  # Refuse an unpublishable success record.
        result.update(status='passed', verification=verification)
        return result
    except BaseException as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        if not groups_stopped:
            _stop_groups(processes)
        for label, process in processes.items():
            result['processes'][label]['returncode'] = process.returncode
        result['wall_seconds'] = time.monotonic() - began
        result['artifact_sha256'] = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for paths in files.values() for path in paths.values()
            if path.is_file() and not path.is_symlink()
        }
        _publish_exclusive(output / 'receipt.json', result)

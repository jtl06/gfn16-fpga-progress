# SPDX-License-Identifier: Apache-2.0
"""Default-OFF offline BOINC-style lifecycle over the R15 software backend.

No SDK calls, attachment, work fetch, project writes or PrimeGrid submission.
Project app-name/version and work-unit/proof upload formats are UNBOUND. The
private JSON CLI is NOT a BOINC/PrimeGrid job or upload format. Existing injected
callback APIs below remain compatible. Run --help for the software-only CLI.

Primary API background (not a claim of SDK linkage):
https://github.com/BOINC/boinc/wiki/API-for-native-apps
https://github.com/BOINC/boinc/wiki/Anonymous-platform
"""
import argparse
import fcntl
import hashlib
import json
import os
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
import re

from fpga.host.r15_arithmetic import Checkpoint, HostFault, SoftwareBackend, need
from fpga.host.r15_checkpoint_store import CheckpointStore, VerifiedSession


@dataclass(frozen=True)
class Status:
    suspended: bool = False
    quit_request: bool = False
    abort_request: bool = False
    no_heartbeat: bool = False


class SlotPlan:
    def __init__(self, slot, resolver, *, enabled=False):
        need(enabled is True, 'BOINC_WRAPPER_OFF')
        self.slot = Path(slot).resolve()
        self.resolver = resolver

    def path(self, logical):
        need(type(logical) is str and re.fullmatch(r'[A-Za-z0-9_.-]+', logical) and
             logical not in ('.', '..'), 'BOINC_LOGICAL_NAME')
        physical = Path(self.resolver(logical))
        if not physical.is_absolute():
            physical = self.slot/physical
        physical = physical.resolve()
        need(physical.is_relative_to(self.slot) and physical != self.slot, 'BOINC_SLOT_ESCAPE')
        return physical


class SoftwareBoincService:
    """Callbacks are test doubles, not evidence of a linked BOINC runtime."""
    def __init__(self, backend, verified, callbacks, total_steps, *, enabled=False):
        need(enabled is True and type(verified) is Checkpoint and type(total_steps) is int and
             total_steps > 0, 'BOINC_SERVICE_OFF_OR_INPUT')
        self.backend, self.verified, self.callbacks = backend, verified, callbacks
        self.total_steps = total_steps
        self.finished = False

    def poll(self):
        status = self.callbacks.status()
        need(type(status) is Status and all(type(x) is bool for x in status.__dict__.values()),
             'BOINC_STATUS')
        if status.quit_request or status.abort_request or status.no_heartbeat:
            self.backend.load(self.verified.value)
            self.callbacks.save_checkpoint(self.verified.encode())
            self.finished = True
            return 'abort_without_result_publication'
        if status.suspended:
            return 'suspended_no_progress'
        if self.callbacks.time_to_checkpoint():
            self.callbacks.save_checkpoint(self.verified.encode())
            self.callbacks.checkpoint_completed()
        fraction = min(1.0, self.verified.completed/self.total_steps)
        self.callbacks.fraction_done(fraction)
        return 'software_ready'


JOB_SCHEMA = 'r15-boinc-offline-job-v1'
SCOPE = dict(software_backend=True, BOINC_SDK=False, BOINC_client=False,
             PrimeGrid_job_compatible=False, PrimeGrid_submission=False,
             actual_device=False, HDL=False, canonical_EndA_transport=False,
             primality_or_upload_certificate=False, promotion_allowed=False)


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def _decode(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, 'OFFLINE_DUPLICATE_JSON_KEY')
            value[key] = item
        return value
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: need(False, 'OFFLINE_JSON_NONFINITE'))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise HostFault('R15_HOST_OFFLINE_JSON') from exc


def _read(path, limit=1024*1024):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit,
             'OFFLINE_REGULAR_BOUNDED_FILE')
        raw = stream.read(limit+1)
    need(len(raw) <= limit, 'OFFLINE_FILE_BOUND')
    return raw


def _atomic(path, value):
    """Private POSIX JSON publication; not a BOINC result-upload operation."""
    if path.exists() or path.is_symlink():
        _read(path)
    fd, name = tempfile.mkstemp(prefix='.r15-write-', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(_json_bytes(value)); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary.exists():
            temporary.unlink()


def validate_job(document):
    """A finite scalar recurrence test, deliberately not an inferred project ABI."""
    keys = {'schema', 'job_id', 'base', 'n', 'owner', 'context', 'initial_hex',
            'bits', 'window_size', 'gl_width'}
    need(type(document) is dict and set(document) == keys and document['schema'] == JOB_SCHEMA,
         'OFFLINE_JOB_FORMAT_ONLY_NO_PROJECT_ABI')
    need(type(document['job_id']) is str and
         re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', document['job_id']), 'OFFLINE_JOB_ID')
    for key in ('base', 'n', 'owner', 'context', 'window_size', 'gl_width'):
        need(type(document[key]) is int, 'OFFLINE_INTEGER_'+key)
    need(2 <= document['base'] <= 1000000000 and document['n'] in (32, 256),
         'OFFLINE_SMALL_PROFILE_ONLY')
    need(0 <= document['owner'] < 1 << 56 and document['context'] in (0, 1), 'OFFLINE_OWNER_CONTEXT')
    need(type(document['bits']) is str and 1 <= len(document['bits']) <= 65536 and
         re.fullmatch('[01]+', document['bits']), 'OFFLINE_DESCRIPTOR_BITS')
    need(1 <= document['gl_width'] <= document['window_size'] <= 4096 and
         document['window_size'] % document['gl_width'] == 0, 'OFFLINE_WINDOW_GEOMETRY')
    value = document['initial_hex']
    need(type(value) is str and len(value) <= 2048 and
         re.fullmatch(r'0x(?:0|[1-9a-f][0-9a-f]*)', value), 'OFFLINE_CANONICAL_HEX')
    need(int(value, 16) < document['base']**document['n']+1, 'OFFLINE_INITIAL_RESIDUE')
    return dict(document)


def source_pins():
    root = Path(__file__).resolve().parent
    return {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
            ('r15_boinc_wrapper.py', 'r15_arithmetic.py', 'r15_checkpoint_store.py')}


class OfflineCallbacks:
    """Bounded local status-file/test-double API, never BOINC shared memory."""
    def __init__(self, control_file=None):
        self.control_file = Path(control_file) if control_file is not None else None
        self.current = Status()
        self.request_checkpoint = True
        self.checkpoint_acks = 0
        self.fraction = 0.0

    def status(self):
        if self.control_file is not None:
            value = _decode(_read(self.control_file, 4096))
            need(type(value) is dict and set(value) == {'schema', 'status', 'checkpoint'} and
                 value['schema'] == 'r15-boinc-offline-control-v1' and
                 type(value['status']) is dict and set(value['status']) == set(Status.__dataclass_fields__) and
                 all(type(v) is bool for v in value['status'].values()) and
                 type(value['checkpoint']) is bool, 'OFFLINE_CONTROL_FORMAT')
            self.current = Status(**value['status']); self.request_checkpoint = value['checkpoint']
        return self.current

    def time_to_checkpoint(self):
        return self.request_checkpoint

    def checkpoint_completed(self):
        self.checkpoint_acks += 1

    def fraction_done(self, value):
        need(self.fraction <= value <= 1.0, 'OFFLINE_MONOTONIC_PROGRESS')
        self.fraction = value


def run_offline_job(document, slot, *, enabled=False, engine='python', resume=False,
                    callbacks=None, max_windows=None):
    """Run/resume verified software windows and publish a private result atomically.

    Polls happen at verified boundaries. A shorter last window uses width1,
    with no padding or invented operations. Checkpoint progress is GLOBAL to
    this software job; owner is a stable run ID, NOT a hardware lease. No real
    transport/device object is accepted. A partial/interrupted window restores
    the last committed residue AND descriptor position through VerifiedSession.
    """
    need(enabled is True and type(resume) is bool and engine in ('python', 'gmp'),
         'OFFLINE_SOFTWARE_ONLY_EXPLICIT_ENABLE')
    job = validate_job(document)
    need(max_windows is None or type(max_windows) is int and 0 <= max_windows <= 65536,
         'OFFLINE_FINITE_WINDOW_LIMIT')
    pins = source_pins()
    job_hash = hashlib.sha256(_json_bytes(job)).hexdigest()
    source = hashlib.sha256(_json_bytes(dict(job=job_hash, code=pins, engine=engine))).hexdigest()
    backend = SoftwareBackend(job['base'], job['n'], enabled=True, engine=engine)
    requested = Path(slot)
    need(requested.is_absolute() and not requested.is_symlink(), 'OFFLINE_PRIVATE_SLOT')
    root = requested.resolve()
    if not root.exists():
        need(not resume, 'OFFLINE_RESUME_MISSING_SLOT')
        root.mkdir(mode=0o700)
    need(root.is_dir(), 'OFFLINE_SLOT_DIRECTORY')
    marker = dict(schema='r15-boinc-offline-slot-v1', job_sha256=job_hash,
                  source_sha256=source, code=pins, engine=engine, scope=SCOPE)
    marker_path = root/'slot.json'
    names = {p.name for p in root.iterdir()}
    allowed = {'.r15-offline.lock','slot.json','input.json','checkpoint.r15','status.json','result.json'}
    need(all(name in allowed or re.fullmatch(r'\.(?:r15-write|checkpoint-r15)-[A-Za-z0-9_-]+',name)
             for name in names), 'OFFLINE_EMPTY_PRIVATE_SLOT_NOT_BOINC_INSTALLATION')
    if 'slot.json' in names:
        need(resume, 'OFFLINE_EXPLICIT_RESUME_REQUIRED')
        need(_decode(_read(marker_path)) == marker and _decode(_read(root/'input.json')) == job,
             'OFFLINE_RESTART_IDENTITY')
    else:
        need(not resume and names <= {'.r15-offline.lock'},
             'OFFLINE_EMPTY_PRIVATE_SLOT_NOT_BOINC_INSTALLATION')
    # Refuse foreign/populated directories BEFORE creating even a lock file.
    # Repeat identity checks under the lock to retain cooperative exclusivity.
    lock = os.open(root/'.r15-offline.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        need(stat.S_ISREG(os.fstat(lock).st_mode) and os.fstat(lock).st_nlink == 1, 'OFFLINE_LOCK_FILE')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise HostFault('R15_HOST_OFFLINE_SLOT_BUSY') from exc
        if marker_path.exists() or marker_path.is_symlink():
            need(resume, 'OFFLINE_EXPLICIT_RESUME_REQUIRED')
            need(_decode(_read(marker_path)) == marker and _decode(_read(root/'input.json')) == job,
                 'OFFLINE_RESTART_IDENTITY')
        else:
            need(not resume and {p.name for p in root.iterdir()} == {'.r15-offline.lock'},
                 'OFFLINE_EMPTY_PRIVATE_SLOT_NOT_BOINC_INSTALLATION')
            _atomic(root/'input.json', job)
            _atomic(marker_path, marker)
        store = CheckpointStore(root, source=source, owner=job['owner'], context=job['context'], enabled=True)
        if not store.path.exists() and not store.path.is_symlink():
            need(not resume, 'OFFLINE_RESTART_CHECKPOINT_MISSING')
            store.commit(Checkpoint(job['base'], job['n'], job['owner'], job['context'],
                                    0, int(job['initial_hex'], 16), source))
        _read(store.path,4*1024*1024)  # reject hardlinks as well as symlink aliases
        session = VerifiedSession(backend, store, enabled=True)
        total = len(job['bits'])
        cp = session.verified
        need(cp.completed <= total and (cp.completed == total or cp.completed % job['window_size'] == 0),
             'OFFLINE_RESTART_DESCRIPTOR_BOUNDARY')
        if cp.completed == 0:
            need(cp.value == int(job['initial_hex'], 16), 'OFFLINE_INITIAL_CHECKPOINT')
        callbacks = callbacks if callbacks is not None else OfflineCallbacks()
        status_path, result_path = root/'status.json', root/'result.json'
        if status_path.exists() or status_path.is_symlink():
            previous = _decode(_read(status_path))
            keys = {'schema','phase','job_sha256','source_sha256','verified_completed',
                    'total_steps','fraction_done','result_published','scope'}
            need(type(previous) is dict and previous.get('phase') in (
                 'running','yielded','suspended','deferred','complete','failed','aborted')
                 and set(previous) == keys | ({'error'} if previous['phase'] == 'failed' else set())
                 and previous['schema'] == 'r15-boinc-offline-status-v1'
                 and previous['job_sha256'] == job_hash and previous['source_sha256'] == source
                 and type(previous['verified_completed']) is int
                 and 0 <= previous['verified_completed'] <= cp.completed
                 and previous['total_steps'] == total
                 and previous['fraction_done'] == previous['verified_completed']/total
                 and type(previous['result_published']) is bool
                 and previous['result_published'] == (previous['phase'] == 'complete')
                 and previous['scope'] == SCOPE, 'OFFLINE_RESTART_STATUS')
            need(previous.get('phase') != 'aborted', 'OFFLINE_ABORTED_JOB_NOT_RESUMABLE')

        def status(phase, error=None):
            value = dict(schema='r15-boinc-offline-status-v1', phase=phase, job_sha256=job_hash,
                         source_sha256=source, verified_completed=session.verified.completed,
                         total_steps=total, fraction_done=session.verified.completed/total,
                         result_published=phase == 'complete', scope=SCOPE)
            if error is not None:
                value['error'] = error
            _atomic(status_path, value)
            return value

        def result():
            return dict(schema='r15-boinc-offline-result-v1', status='verified_software_result',
                        job_sha256=job_hash, source_sha256=source, base=job['base'], n=job['n'],
                        owner=job['owner'], context=job['context'], completed=total,
                        residue_hex=hex(session.verified.value),
                        checkpoint_sha256=hashlib.sha256(_read(store.path)).hexdigest(), scope=SCOPE)

        if result_path.exists() or result_path.is_symlink():
            need(session.verified.completed == total and _decode(_read(result_path)) == result(),
                 'OFFLINE_EXISTING_RESULT_MISMATCH')
            # A crash after atomic result replacement but before status update
            # is recoverable without repeating work or inventing a new result.
            return status('complete')
        windows = 0
        try:
            while True:
                current = callbacks.status()
                need(type(current) is Status and all(type(x) is bool for x in current.__dict__.values()),
                     'OFFLINE_STATUS')
                if current.abort_request:
                    return status('aborted')
                if current.quit_request or current.no_heartbeat:
                    return status('deferred')
                if current.suspended:
                    return status('suspended')
                callbacks.fraction_done(session.verified.completed/total)
                if session.verified.completed == total:
                    _atomic(result_path, result())
                    return status('complete')
                if max_windows is not None and windows == max_windows:
                    return status('yielded')
                requested_checkpoint = callbacks.time_to_checkpoint()
                need(type(requested_checkpoint) is bool, 'OFFLINE_CHECKPOINT_CALLBACK')
                begin = session.verified.completed
                bits = [bit == '1' for bit in job['bits'][begin:begin+job['window_size']]]
                width = job['gl_width'] if len(bits) % job['gl_width'] == 0 else 1
                need(session.window(bits, width), 'OFFLINE_GL_WINDOW_REJECTED')
                windows += 1
                if requested_checkpoint:
                    callbacks.checkpoint_completed()  # only after durable verified commit
                status('running')
        except (HostFault, OSError, RuntimeError, TypeError, ValueError) as exc:
            # VerifiedSession owns rollback. A failed write/GL/callback must
            # never produce a success result; the prior checkpoint is retained.
            return status('failed', str(exc))
    finally:
        os.close(lock)


def selftest(engine):
    """One bounded existing-executor recipe; small software only, no HDL."""
    import io
    import platform
    import time
    import unittest
    from unittest.mock import patch
    started = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromNames([
        'fpga.tests.test_r15_boinc_wrapper', 'fpga.tests.test_r15_boinc_offline'])
    log = io.StringIO()
    tests = unittest.TextTestRunner(stream=log, verbosity=0).run(suite)
    need(tests.wasSuccessful() and tests.testsRun == 28, 'OFFLINE_SELFTEST:'+log.getvalue()[-1500:])
    rows = []
    for base, n in ((599, 32), (600, 256)):
        document = dict(schema=JOB_SCHEMA, job_id='azure-software-fixture', base=base, n=n,
                        owner=1, context=0, initial_hex='0x7', bits='1011001'*19+'1101',
                        window_size=16, gl_width=4)
        backend = SoftwareBackend(base, n, enabled=True, engine=engine)
        modulus = base**n+1
        wanted = (pow(7, 1 << len(document['bits']), modulus)*
                  pow(2, int(document['bits'], 2), modulus)) % modulus
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve(); resumed = root/'resumed'; full = root/'full'; bad = root/'bad'
            first = run_offline_job(document, resumed, enabled=True, engine=engine, max_windows=1)
            need(first['phase'] == 'yielded' and first['verified_completed'] == 16 and
                 not (resumed/'result.json').exists(), 'OFFLINE_SELFTEST_PAUSE')
            need(run_offline_job(document, resumed, enabled=True, engine=engine, resume=True)['phase'] == 'complete'
                 and run_offline_job(document, full, enabled=True, engine=engine)['phase'] == 'complete',
                 'OFFLINE_SELFTEST_EXECUTION')
            need(_read(resumed/'result.json') == _read(full/'result.json') and
                 int(_decode(_read(full/'result.json'))['residue_hex'], 16) == wanted,
                 'OFFLINE_SELFTEST_ORACLE_RESTART')
            original = SoftwareBackend.step
            def corrupt(value, bit):
                original(value, bit)
                if value.steps == 2:
                    value.load((value.read()+1) % int(value.modulus))
            with patch.object(SoftwareBackend, 'step', corrupt):
                failure = run_offline_job(document, bad, enabled=True, engine=engine)
            need(failure['phase'] == 'failed' and failure['verified_completed'] == 0 and
                 'GL_WINDOW_REJECTED' in failure['error'] and not (bad/'result.json').exists(),
                 'OFFLINE_SELFTEST_CHOSEN_ENGINE_CORRUPTION')
        rows.append(dict(base=base, n=n, steps=137, independent_pow_equal=True,
                         restart_byte_equal=True, no_provisional_result=True, chosen_engine_corruption_rejected=True))
    return dict(schema='r15-boinc-offline-tests-v1', status='software_tests_pass', tests=tests.testsRun,
                cases=rows, runtime=backend.runtime, platform=platform.system(), source_pins=source_pins(),
                elapsed_seconds=time.monotonic()-started, scope=SCOPE)


def validate(stdout, *, require_gmp=True, expected_source_pins=None):
    """Strict existing-reference-executor output boundary; not a project result validator."""
    import math
    need(type(stdout) is str and len(stdout.encode()) <= 8192, 'OFFLINE_OUTPUT_BOUND')
    lines = stdout.splitlines()
    need(len(lines) == 1 and lines[0].startswith('R15_BOINC_OFFLINE_RESULT '), 'OFFLINE_OUTPUT_ONE_RESULT')
    value = _decode(lines[0][len('R15_BOINC_OFFLINE_RESULT '):])
    need(set(value) == {'schema','status','tests','cases','runtime','platform','source_pins','elapsed_seconds','scope'}
         and value['schema'] == 'r15-boinc-offline-tests-v1' and value['status'] == 'software_tests_pass'
         and type(value['tests']) is int and value['tests'] == 28, 'OFFLINE_OUTPUT_SCHEMA')
    need(value['scope'] == SCOPE and all(type(v) is bool for v in value['scope'].values()), 'OFFLINE_OUTPUT_SCOPE')
    expected = [dict(base=b, n=n, steps=137, independent_pow_equal=True, restart_byte_equal=True,
                     no_provisional_result=True, chosen_engine_corruption_rejected=True) for b,n in ((599,32),(600,256))]
    need(value['cases'] == expected and all(type(row[k]) is type(want[k]) for row,want in zip(value['cases'],expected)
                                         for k in want), 'OFFLINE_OUTPUT_CASES')
    need(expected_source_pins is not None and value['source_pins'] == expected_source_pins, 'OFFLINE_OUTPUT_SOURCE')
    elapsed = value['elapsed_seconds']
    need(type(elapsed) in (int,float) and math.isfinite(elapsed) and 0 <= elapsed < 105, 'OFFLINE_OUTPUT_FINITE')
    runtime = value['runtime']
    if require_gmp:
        need(value['platform'] == 'Linux' and set(runtime) == {'engine','version','gmp'}
             and runtime['engine'] == 'gmpy2' and all(type(runtime[k]) is str and runtime[k] for k in ('version','gmp')),
             'OFFLINE_OUTPUT_ACTUAL_GMP')
    return value


def recipe():
    """Declaration for the existing Azure reference executor, never a launcher."""
    root = Path(__file__).resolve().parents[1]
    members = ('__init__.py','host/__init__.py','tests/__init__.py',
               'host/r15_boinc_wrapper.py','host/r15_arithmetic.py','host/r15_checkpoint_store.py',
               'tests/test_r15_boinc_wrapper.py','tests/test_r15_boinc_offline.py')
    return dict(schema='r15-boinc-offline-recipe-v1', identity='r15-boinc-offline-azure-v1',
        source_sha256={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in members},
        argv=['{python}','-B','-m','fpga.host.r15_boinc_wrapper','--self-test','--engine','gmp'],
        validator=dict(source='host/r15_boinc_wrapper.py',function='validate',
                       config=dict(require_gmp=True,expected_source_pins=source_pins())),
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),allowed_hosts=['azure-fit'],
        max_command_seconds=105,max_unit_seconds=120,expected_returncode=0,
        scope=dict(software_only=True,HDL=False,device=False,BOINC_runtime=False,
                   PrimeGrid_submission=False,full_N_numeric=False,promotion=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--software-only', action='store_true', help='required; no SDK/device mode exists')
    parser.add_argument('--job', type=Path, help='private r15-boinc-offline-job-v1 JSON only')
    parser.add_argument('--slot', type=Path, help='new empty private directory, not a BOINC project/slot')
    parser.add_argument('--self-test', action='store_true', help='finite software-only recipe; no device/client')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--engine', choices=('python', 'gmp'), default='python')
    parser.add_argument('--control-file', type=Path, help='optional private offline status JSON, not BOINC IPC')
    parser.add_argument('--max-windows', type=int)
    args = parser.parse_args(argv)
    if args.self_test:
        if args.job or args.slot or args.resume or args.control_file or args.max_windows is not None:
            parser.error('--self-test cannot also run a supplied job')
        print('R15_BOINC_OFFLINE_RESULT '+json.dumps(selftest(args.engine),sort_keys=True))
        return 0
    if args.job is None or args.slot is None:
        parser.error('--job and --slot are required outside --self-test')
    try:
        outcome = run_offline_job(_decode(_read(args.job)), args.slot, enabled=args.software_only,
            engine=args.engine, resume=args.resume, callbacks=OfflineCallbacks(args.control_file),
            max_windows=args.max_windows)
    except (HostFault, OSError, ImportError) as exc:
        outcome = dict(phase='refused', error=str(exc), scope=SCOPE)
    print(json.dumps(outcome, sort_keys=True))
    # Private standalone exit convention, NOT boinc_finish/temporary_exit.
    return 0 if outcome['phase'] == 'complete' else 75 if outcome['phase'] in (
        'suspended', 'deferred', 'yielded') else 2


if __name__ == '__main__':
    sys.exit(main())

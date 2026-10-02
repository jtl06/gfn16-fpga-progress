"""Additive r54 watcher: transient STS failures back off, auth denials latch.

Reuse the frozen v1 source/queue/lock/claim/cutoff contracts. Never read or
edit credentials, restart native work, alter caps, or replace old receipts.
"""
import argparse
from datetime import timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

BASE_PATH = Path(__file__).with_name('plain_fit_watch_v1.py').resolve()
BASE_SHA = '0476ec4f1727bf7491f30949817bb79ec92f45a762b362c493254bda5e7609e6'
if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_SHA:
    raise ValueError('frozen watcher v1 drift')
SPEC = importlib.util.spec_from_file_location('frozen_plain_fit_watch_v1', BASE_PATH)
B = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(B)
STATE_PATH = B.STATE / 'watch-supervisor-state-v2.json'
HARD_AUTH = frozenset(('waiting_for_normal_login_metadata_change', 'ExpiredToken',
                      'explicit_auth_denial_no_tick', 'account_mismatch_no_tick',
                      'native_observation_auth_failure_waiting_for_normal_login'))
AUTH_ERROR_MARKERS = ('ExpiredToken', 'InvalidClientTokenId', 'UnrecognizedClientException',
                      'UnauthorizedRequest', 'Forbidden', 'AccessDenied', 'InvalidGrant',
                      'invalid_grant', 'TokenRefreshRequired', 'Server authentication failed')


def check_auth():
    try:
        result = subprocess.run([B.AWS, 'sts', 'get-caller-identity', '--output', 'json',
                                 '--cli-connect-timeout', '10', '--cli-read-timeout', '10'],
                                capture_output=True, text=True, timeout=25)
        if result.returncode == 0:
            value = json.loads(result.stdout)
            if value.get('Account') == B.ACCOUNT:
                return True, 'normal_session_verified'
            return False, 'account_mismatch_no_tick'
        if 'ExpiredToken' in result.stderr:
            return False, 'ExpiredToken'
        if any(marker in result.stderr for marker in AUTH_ERROR_MARKERS):
            return False, 'explicit_auth_denial_no_tick'
        return False, 'normal_sts_failed_no_tick'
    except (ValueError, OSError, subprocess.SubprocessError):
        return False, 'normal_sts_unresolved_no_tick'


class AuthLatch:
    def __init__(self, fingerprint, blocked=True):
        self.fingerprint = fingerprint
        self.blocked = blocked
        self.reason = 'waiting_for_normal_login_metadata_change' if blocked else 'normal_session_verified'
        self.failures = 0
        self.retry_at = 0.0

    def ready(self, fingerprint, check, refresh_fingerprint, now=None):
        now = time.monotonic() if now is None else now
        changed = fingerprint != self.fingerprint
        if not changed and (self.blocked or now < self.retry_at):
            return False
        valid, self.reason = check()
        self.fingerprint = refresh_fingerprint()
        if valid:
            self.blocked = False; self.failures = 0; self.retry_at = 0.0
        elif self.reason in HARD_AUTH:
            self.blocked = True; self.failures = 0; self.retry_at = 0.0
        else:
            # Unknown/transient transport is NOT auth success. No tick until
            # normal STS verifies the same account; retry the normal session.
            self.blocked = False; self.failures += 1
            self.retry_at = now + min(300, 60 * 2 ** min(self.failures - 1, 3))
        return valid

    def auth_failure(self, fingerprint):
        self.blocked = True; self.fingerprint = fingerprint
        self.reason = 'native_observation_auth_failure_waiting_for_normal_login'
        self.failures = 0; self.retry_at = 0.0


def restore_latch(previous):
    latch = AuthLatch(previous.get('credential_metadata_sha256', B.metadata()))
    if previous.get('status') == 'observing':
        latch.blocked = False; latch.fingerprint = None
    elif previous.get('reason', latch.reason) not in HARD_AUTH:
        # Repair a transient failure stranded by v1, and retain a v2 delay
        # across restart using a capped UTC remainder, not stale monotonic time.
        latch.blocked = False; latch.reason = previous['reason']
        latch.failures = min(4, max(1, previous.get('transient_failure_count', 1)))
        if previous.get('next_auth_retry_at_utc'):
            target = B.datetime.fromisoformat(previous['next_auth_retry_at_utc'])
            latch.retry_at = time.monotonic() + min(300, max(0, (target-B.utc()).total_seconds()))
    return latch


def status(observer, latch):
    delay = max(0, latch.retry_at-time.monotonic())
    value = 'auth_blocked' if latch.blocked else ('auth_backoff' if delay else 'observing')
    B.save_status(STATE_PATH, value, credential_metadata_sha256=latch.fingerprint,
                  reason=latch.reason, transient_failure_count=latch.failures,
                  next_auth_retry_at_utc=(B.utc()+timedelta(seconds=delay)).isoformat() if delay else None,
                  watcher_version=2, watcher_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  journal_last_sha256=observer.journal.rows[-1]['sha256'], jobs=observer.journal.current())


def supervise(controller, queue):
    with controller.controller_lock(B.STATE):
        observer = controller.Controller(queue, B.STATE, controller.SSHBackend(B.STATE, B.END))
        claim = observer.journal.current().get('anext-writeback-9668', {})
        if claim.get('invocation_id') != B.INVOCATION or claim.get('request_sha256') != B.REQUEST_SHA:
            raise ValueError('exact original F3 claim required; no new adoption or launch')
        old_path = STATE_PATH if STATE_PATH.exists() else B.STATE/'watch-supervisor-state-v1.json'
        previous = json.loads(old_path.read_text()) if old_path.exists() else {}
        latch = restore_latch(previous); status(observer, latch)
        next_tick = 0.0
        while B.utc() < B.END:
            if time.monotonic() >= next_tick:
                if latch.ready(B.metadata(), check_auth, B.metadata):
                    first = len(observer.journal.rows); observer.tick()
                    if any(any(marker in row.get('reason', '') for marker in AUTH_ERROR_MARKERS)
                           for row in observer.journal.rows[first:]):
                        latch.auth_failure(B.metadata())
                    status(observer, latch); next_tick = time.monotonic()+60
                elif latch.reason != 'waiting_for_normal_login_metadata_change':
                    status(observer, latch); next_tick = time.monotonic()+10
            time.sleep(min(10, max(0, (B.END-B.utc()).total_seconds())))
        B.save_status(STATE_PATH, 'cutoff_reached_no_worker_signal',
                      credential_metadata_sha256=latch.fingerprint, jobs=observer.journal.current(), watcher_version=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-sha256', required=True); parser.add_argument('--detach', action='store_true')
    args = parser.parse_args()
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != args.source_sha256:
        raise ValueError('watcher source drift')
    if B.utc() >= B.END:
        raise ValueError('original cutoff already reached')
    controller, queue = B.load_controller()
    if args.detach:
        with (B.STATE/'watch-supervisor-v2.log').open('a') as stream:
            child = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                                      '--source-sha256', args.source_sha256], stdin=subprocess.DEVNULL,
                                     stdout=stream, stderr=stream, start_new_session=True, close_fds=True)
        for _ in range(50):
            if child.poll() is not None:
                raise ValueError('watcher startup failed; original workers untouched')
            if STATE_PATH.exists():
                value = json.loads(STATE_PATH.read_text())
                if value.get('pid') == child.pid:
                    print(json.dumps(value)); return
            time.sleep(.1)
        raise ValueError('watcher startup unresolved; reconcile process before retry')
    supervise(controller, queue)


if __name__ == '__main__':
    main()

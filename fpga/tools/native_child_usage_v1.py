"""Per-child POSIX resource evidence for a single-threaded native launcher.

Public Popen poll/wait methods reap through wait4, retaining CPU and peak RSS
for this executable, rather than a cumulative build/model high-water mark.
No competing waiter may reap the same PID. No command or host is launched here.
"""
import os
import platform
import subprocess
import time


class MeasuredPopen(subprocess.Popen):
    native_usage = None

    def _record(self, status, usage):
        self.native_usage = usage
        self.returncode = os.waitstatus_to_exitcode(status)

    def poll(self):
        if self.returncode is None:
            pid, status, usage = os.wait4(self.pid, os.WNOHANG)
            if pid:
                if pid != self.pid:
                    raise ValueError('exact measured child PID')
                self._record(status, usage)
        return self.returncode

    def wait(self, timeout=None):
        if timeout is None:
            if self.returncode is None:
                pid, status, usage = os.wait4(self.pid, 0)
                if pid != self.pid:
                    raise ValueError('exact measured child PID')
                self._record(status, usage)
            return self.returncode
        deadline = time.monotonic() + timeout
        while self.poll() is None:
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(self.args, timeout)
            time.sleep(min(.01, max(0, deadline - time.monotonic())))
        return self.returncode

    def resource_receipt(self):
        if platform.system() != 'Linux' or self.native_usage is None or self.returncode is None:
            raise ValueError('reaped Linux child resource evidence required')
        usage = self.native_usage
        return dict(schema='native-wait4-child-usage-v1', pid=self.pid, returncode=self.returncode,
            user_seconds=usage.ru_utime, system_seconds=usage.ru_stime,
            peak_rss_kib=usage.ru_maxrss,
            scope='taskset exec child and its reaped descendants; Linux wait4 peak, not aggregate cgroup peak')

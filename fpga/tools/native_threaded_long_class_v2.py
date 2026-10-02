"""Intrinsic5015-second/drain guard over the frozen thread2 long executor.

The previous prepared packet is preserved. No arithmetic, resource, thread,
model/ancillary/overall bound or independent reference proof changes. A cheap
time-only guard runs at every native guard poll; original protected file/timer
checks remain before commands. Its full-envelope reserve is conservative even
after time already elapsed, and never enlarges authority or a deadline.
"""
import hashlib
from importlib import util
from pathlib import Path
import time
import types

HERE=Path(__file__).resolve().parent
SELF='tools/native_threaded_long_class_v2.py'
PREVIOUS_SHA='8eeeabd2456fd29e10a8534e007c98baf5832e94cec753f509a97df38ab7c0db'
DEADLINE=1791162766
DRAIN_LEAD_SECONDS=7200


def previous():
    path=HERE/'native_threaded_long_class_v1.py'
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=PREVIOUS_SHA:
        raise ValueError('exact preserved thread2 long parent')
    spec=util.spec_from_file_location('_intrinsic_thread2_long_parent',path)
    value=util.module_from_spec(spec);spec.loader.exec_module(value);return value


base=previous()
duration=base.duration
PINS=dict(base.PINS,**{'tools/native_threaded_long_class_v1.py':PREVIOUS_SHA})
SELECTIONS=base.SELECTIONS
profile=base.profile
validate_threaded=base.validate_threaded
execution_limits=base.execution_limits


def dependencies():
    return dict(PINS)


def guard_runtime_deadline(selected):
    if selected['host']!=duration.HOST or selected['profile_id']!=duration.PROFILE \
        or type(selected['burst_deadline_epoch']) is not int or selected['burst_deadline_epoch']!=DEADLINE:
        raise ValueError('exact measured-thread2 protected host/profile/deadline')
    horizon=duration.SHAPE['outer_seconds']+duration.SHAPE['stop_grace_seconds']
    if not time.time()+horizon < DEADLINE-DRAIN_LEAD_SECONDS:
        raise ValueError('full5015-second thread2 envelope before unchanged two-hour burst drain/deadline')


def guard_protected(selected):
    guard_runtime_deadline(selected)
    # Retain all original read-only hashes/timer checks, not only a timestamp.
    return base.base.source_policy().host.guard_protected(selected)


def adapted_source(raw,selected):
    text=base.adapted_source(raw,selected)
    for old,new in [('SELF = '+repr(base.SELF),'SELF = '+repr(SELF)),
                    ('    def guard():\n','    def guard():\n        guard_runtime_deadline(profile)\n')]:
        if text.count(old)!=1:
            raise ValueError('unique intrinsic thread2 deadline source anchor')
        text=text.replace(old,new,1)
    return text


def parent(name,receipt=None):
    selected=profile(name);prior=base.parent(name,receipt)
    value=types.ModuleType('_intrinsic_thread2_long_native_parent')
    value.__dict__.update(prior.__dict__)
    value.__dict__.update(__file__=str(Path(__file__).resolve()),LONG_RECEIPT=receipt,
                          guard_runtime_deadline=guard_runtime_deadline,guard_protected=guard_protected)
    raw=base.base.source_policy().host.static_module().pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
    exec(compile(adapted_source(raw,selected),'[intrinsic measured thread2 deadline]','exec'),value.__dict__)
    value.PROFILES={selected['host']:selected}
    return value


def execute(manifest_path,pin,out):
    namespace=dict(base.execute.__globals__,parent=parent,PINS=PINS,profile=profile)
    function=types.FunctionType(base.execute.__code__,namespace,base.execute.__name__)
    return function(manifest_path,pin,out)

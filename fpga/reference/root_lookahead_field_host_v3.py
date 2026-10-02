"""F2 reference-host successor; arithmetic is the frozen v2 code object.

Only full-numeric host admission changes. Scalar N<=256 remains portable;
large reference data requires one known static Linux profile with the same
actual cgroup/affinity/topology/own-user guard used by finite native jobs.
This module does not launch jobs or mutate the frozen oracle/host profiles.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import platform
import types

from fpga.reference import root_lookahead_field_v2 as parent
from fpga.tools import native_static_v1 as static


PARENT_SHA = '8104fa1e6eeeee0114937e1ce988078e4a2ad8bbe2b59fef9913acb3bbd34904'
STATIC_SHA = '5b1b0f0dc584df8d6887235a9ddf1610f4956823aa84131438de7b8054f1e0ab'
SELF = 'reference/root_lookahead_field_host_v3.py'
ALLOWED = frozenset({'gcp-c4d-static01-v1', 'gcp-c4d-static23-v1',
                     'aethia-static02-v1', 'aethia-static46-v1', 'aethia-static810-v1'})
ARITHMETIC = ('cyclic', 'phases', 'corpus')
_profile_id = None
_last_limits = None


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_guard():
    parent.need(sha(parent.__file__) == PARENT_SHA, 'frozen F2 arithmetic parent')
    parent.need(sha(static.__file__) == STATIC_SHA, 'frozen static host guard')
    parent.source_guard()


def configure(profile_id):
    global _profile_id, _last_limits
    source_guard()
    parent.need(type(profile_id) is str and profile_id in ALLOWED,
                'known admitted F2 numeric static profile only')
    static.profile(profile_id)  # validates the exact pinned profile descriptors
    _profile_id, _last_limits = profile_id, None


def numeric_gate(n):
    global _last_limits
    parent.field_math.geometry(n)
    if n <= 256:
        return
    source_guard()
    parent.need(platform.system() == 'Linux' and _profile_id in ALLOWED,
                'full numeric F2 reference requires configured admitted Linux profile')
    selected = static.profile(_profile_id)
    parent.need(platform.node() == selected['host'], 'known actual numeric host')
    # The existing guard proves own user, exact physical representatives/full
    # SMT topology, aggregate CPU/memory/swap/ancestor caps and RAM headroom.
    # Transport/source/outer timeout/quota/budget remain the envelope's gates.
    _last_limits = static.execution_limits(selected)


def arithmetic_namespace():
    source_guard()
    namespace = dict(parent.__dict__)
    namespace['numeric_gate'] = numeric_gate
    for name in ARITHMETIC:
        original = getattr(parent, name)
        clone = types.FunctionType(original.__code__, namespace, original.__name__,
                                   original.__defaults__, original.__closure__)
        clone.__kwdefaults__ = original.__kwdefaults__
        clone.__annotations__ = original.__annotations__
        namespace[name] = clone
        parent.need(clone.__code__ is original.__code__ and
                    clone.__defaults__ == original.__defaults__ and
                    clone.__kwdefaults__ == original.__kwdefaults__,
                    'arithmetic function/code/defaults unchanged')
    return namespace


_arithmetic = arithmetic_namespace()
cyclic, phases = _arithmetic['cyclic'], _arithmetic['phases']


def corpus(aw=5, field=0):
    source_guard()
    text, meta = _arithmetic['corpus'](aw, field)
    meta.update(host_guard_successor=SELF, host_guard_sha256=sha(__file__),
                frozen_arithmetic_parent_sha256=PARENT_SHA,
                arithmetic_code_objects_unchanged=list(ARITHMETIC),
                configured_static_profile=_profile_id, full_numeric_limits=_last_limits,
                source_only_reference_data=True, native_RTL_executed=False)
    return text, meta

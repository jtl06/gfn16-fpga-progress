"""Measured T5b thread2 long hook over the actually exercised P3 executor.

Only the exact model-step/overall/report duration bounds change. The shared
namespace, source/tool/physical/fit FD frame, quotas, lint classes, j2, context
probe, build identity v2 and per-child wait4 evidence remain inherited.
"""
import hashlib
import json
from pathlib import Path
import types

from importlib import util

HERE=Path(__file__).resolve().parent
SELF='tools/native_threaded_long_class_v1.py'
BASE_SHA='4633c3ca20a6560fdeed35590922a01de8cd572b1bf127e3d2faa4a96734751f'
DURATION_SHA='5107d198cca687d1305161d9f1a8ffd952b7691aa92e88f12326ddee65e13fb5'


def load(name,pin):
    path=HERE/name
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=pin:
        raise ValueError('exact threaded-long dependency')
    spec=util.spec_from_file_location('_threaded_long_'+path.stem,path)
    value=util.module_from_spec(spec);spec.loader.exec_module(value);return value


base=load('native_threaded_class_v1.py',BASE_SHA)
duration=load('native_threaded_duration_v1.py',DURATION_SHA)
PINS=dict(base.PINS,**{'tools/native_threaded_class_v1.py':BASE_SHA,
                     'tools/native_threaded_duration_v1.py':DURATION_SHA})
SELECTIONS={duration.PROFILE:duration.PROFILE}
execution_limits=base.execution_limits


def dependencies():
    return dict(PINS)


def profile(name):
    if name not in SELECTIONS:
        raise ValueError('measured thread2 long exact burst23 profile only')
    return base.profile(name)


def validate_threaded(manifest):
    count=base.validate_threaded(manifest)
    if count!=2:
        raise ValueError('measured long context/model must be two')
    return count


def adapted_source(raw,selected):
    text=base.adapted_source(raw,selected)
    changes=[('SELF = '+repr(base.SELF),'SELF = '+repr(SELF)),
      ('bounds=dict(command_seconds=1800, overall_seconds=3600, lock_wait_seconds=1800,',
       'duration_admission=LONG_RECEIPT, bounds=dict(command_seconds=4500, ancillary_command_seconds=1800, overall_seconds=4800, outer_seconds=5000, stop_grace_seconds=15, lock_wait_seconds=1800,'),
      ("time.monotonic() - started < 3600, 'overall timeout'",
       "time.monotonic() - started < 4800, 'overall timeout'"),
      ("time.monotonic()-begin < 1800, 'command timeout'",
       "time.monotonic()-begin < (4500 if name == LONG_RECEIPT['model_step'] else 1800), 'command timeout'")]
    for old,new in changes:
        if text.count(old)!=1:
            raise ValueError('unique measured-thread2 duration anchor: '+old)
        text=text.replace(old,new,1)
    return text


def parent(name,receipt=None):
    selected=profile(name)
    original=base.parent(name)
    # Functions MUST share the final live module dictionary. Copying a detached
    # exec namespace would strand PROFILES/LEASE_FDS and the pinned __file__.
    value=types.ModuleType('_measured_thread2_long_parent')
    value.__dict__.update(original.__dict__)
    value.__dict__.update(__file__=str(Path(__file__).resolve()),LONG_RECEIPT=receipt,
                          validate_threaded=validate_threaded)
    raw=base.source_policy().host.static_module().pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
    exec(compile(adapted_source(raw,selected),'[measured T5b thread2 finite duration]','exec'),value.__dict__)
    value.PROFILES={selected['host']:selected}
    return value


def execute(manifest_path,pin,out):
    path=Path(manifest_path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=pin:
        raise ValueError('threaded-long manifest identity')
    manifest=json.loads(path.read_text());selected=profile(manifest['cpu_profile'])
    validate_threaded(manifest)
    receipt=duration.validate(manifest,Path(manifest['source_root']),selected['host'])
    # Reuse the proven outer static4->static3 fit-lock frame and original
    # thread-aware static substitution. All children retain its inherited FDs.
    namespace=dict(base.execute.__globals__,parent=lambda name:parent(name,receipt),
                   PINS=PINS,profile=profile,validate_threaded=validate_threaded)
    execute_base=types.FunctionType(base.execute.__code__,namespace,base.execute.__name__)
    return execute_base(path,pin,out)

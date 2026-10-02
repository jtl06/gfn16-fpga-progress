"""Memory-only 8GiB pairs on the unchanged admitted burst hardware.

The single dispatcher reserves all native caps (maximum48GiB) with8GiB host
headroom. Eight pair selectors do not authorize eight simultaneous8GiB jobs.
Hardware budget identity stays the qualified parent; memory envelope is an
additional exact source pin, not a new host or rate phase.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
SELF='tools/native_static_burst8_v1.py'
PARENT_SHA='d6c2d781503926422f4647664d14d2c15a92dfe257a324f3f70c7e4e014ec9a9'
ENVELOPE='cloud/azure-burst16-memory8-profiles-v1.json'
ENVELOPE_SHA='04fe25064f68301526492ebd232dba201fb15469e88c9f2cee0d3389215a9808'


def base():
    path=HERE/'native_static_v4.py'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=PARENT_SHA:raise ValueError('unchanged admitted hardware policy')
    spec=importlib.util.spec_from_file_location('_burst_memory_parent',path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def selected_profile(profile_id):
    path=HERE.parent/ENVELOPE
    if hashlib.sha256(path.read_bytes()).hexdigest()!=ENVELOPE_SHA:raise ValueError('exact memory envelope')
    data=json.loads(path.read_text())
    if profile_id not in data['profiles']:raise ValueError('approved8GiB pair')
    value=base().profile(profile_id.replace('-static8g','-static'))
    allocation=data['profiles'][profile_id]
    if allocation['cpus']!=value['cpus'] or allocation['memory_bytes']!=8<<30 or allocation['cpu_quota_percent']!=200:
        raise ValueError('same physical pair and exact8GiB cap')
    if data['hardware_profile_sha256']!=value['profile_sha256'] or data['hardware_profile_path']!=value['profile_source']:
        raise ValueError('same qualified hardware/accounting profile')
    if data['aggregate_native_memory_cap_bytes']!=48<<30 or data['minimum_host_available_bytes']!=8<<30 or (56<<30)>=value['observed_total_memory_bytes']:
        raise ValueError('aggregate48GiB cap plus8GiB floor fits observed hardware')
    value.update(allocation,profile_id=profile_id,memory_bytes_per_lane=8<<30,
                 memory_envelope_source=ENVELOPE,memory_envelope_sha256=ENVELOPE_SHA,
                 aggregate_native_memory_cap_bytes=48<<30)
    return value


def module():
    raw=(HERE/'native_static_v4.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen static source')
    text=raw.decode().replace("SELF = 'tools/native_static_v4.py'",'SELF = '+repr(SELF))
    anchor='def profile(profile_id):\n    prior = previous()'
    if text.count(anchor)!=1:raise ValueError('unique memory selector anchor')
    text=text.replace(anchor,'def profile(profile_id):\n    prior = previous()\n    if profile_id.startswith("azure-burst16-static8g"):\n        return selected_profile(profile_id)',1)
    result=types.ModuleType('_burst8_static');result.__file__=str(Path(__file__).resolve());result.selected_profile=selected_profile
    exec(compile(text,str(HERE/'native_static_v4.py')+'[8GiB-envelope]','exec'),result.__dict__)
    result.PINS.update({'tools/native_static_v4.py':PARENT_SHA,ENVELOPE:ENVELOPE_SHA})
    result.SELECTIONS.update({name:name for name in json.loads((HERE.parent/ENVELOPE).read_text())['profiles']})
    return result


policy=module()
PINS=policy.PINS
SELECTIONS=policy.SELECTIONS
profile=policy.profile
parent=policy.parent
static_module=policy.static_module
adapted_source=policy.adapted_source
guard_toolchain=policy.guard_toolchain
guard_protected=policy.guard_protected
execution_limits=policy.execution_limits
execute_with_parent=policy.execute_with_parent
execute=policy.execute

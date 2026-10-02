"""Additive 24GiB GCP pair envelope; unchanged serial tools and execution."""
import hashlib
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
SELF='tools/native_static_gcp24_v1.py'
PARENT_SHA='d6c2d781503926422f4647664d14d2c15a92dfe257a324f3f70c7e4e014ec9a9'
PROFILE='cloud/gcp-native-24g-profiles-v1.json'
PROFILE_SHA='1d657a2bd188dee76926ba1497cec7f46089dde2d0542e1a27f77f3f143ef140'


def selected_profile(profile_id, prior):
    path=HERE.parent/PROFILE
    if hashlib.sha256(path.read_bytes()).hexdigest()!=PROFILE_SHA: raise ValueError('exact 24GiB envelope')
    data=json.loads(path.read_text())
    if profile_id not in data['profiles']: return prior.profile(profile_id)
    ordinary={'gcp-c4d-static24g01-v1':'gcp-c4d-static01-v1','gcp-c4d-static24g23-v1':'gcp-c4d-static23-v1'}
    value=prior.profile(ordinary[profile_id]); allocation=data['profiles'][profile_id]
    if allocation['cpus']!=value['cpus'] or allocation['memory_bytes']!=24<<30 or allocation['cpu_quota_percent']!=200:
        raise ValueError('same pair and exact 24GiB cap')
    if data['hashes']!=value['hashes'] or data['topology']!=value['topology'] or data['minimum_host_available_bytes']!=32<<30:
        raise ValueError('unchanged tools/topology and other24GiB plus host8GiB reservation')
    value.update(allocation,profile_id=profile_id,profile_source=PROFILE,profile_sha256=PROFILE_SHA,
                 minimum_host_available_bytes=32<<30,other_lane_reservation_bytes=24<<30,host_reserve_bytes=8<<30)
    return value


def module():
    raw=(HERE/'native_static_v4.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA: raise ValueError('frozen static host adapter')
    text=raw.decode().replace("SELF = 'tools/native_static_v4.py'",'SELF = '+repr(SELF))
    anchor='def profile(profile_id):\n    prior = previous()'
    if text.count(anchor)!=1: raise ValueError('unique profile envelope anchor')
    text=text.replace(anchor,'def profile(profile_id):\n    prior = previous()\n    if profile_id.startswith("gcp-c4d-static24g"):\n        return selected_profile(profile_id, prior)',1)
    result=types.ModuleType('_gcp24_static');result.__file__=str(Path(__file__).resolve())
    result.selected_profile=selected_profile
    exec(compile(text,str(HERE/'native_static_v4.py')+'[GCP24GiB]','exec'),result.__dict__)
    result.PINS.update({'tools/native_static_v4.py':PARENT_SHA,PROFILE:PROFILE_SHA})
    result.SELECTIONS.update({x:x for x in ('gcp-c4d-static24g01-v1','gcp-c4d-static24g23-v1')})
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

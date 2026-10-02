"""Fixed-wide identity uses the callable/live-guard repaired package/stager family."""
import hashlib
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='9e3b124a263e8386b8d63c724034301ad2de85308c1dd1a4d595d2292d349242'


def module():
    raw=(HERE/'native_profile_variants_v10.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen exact wide identity policy')
    text=raw.decode().replace('native_threaded_wide_stage_v1.py','native_threaded_wide_stage_v3.py').replace('20581efa4daadb13ec986224ed5fc1c86df339e5508fd400a5f09340482a83f9','9c9e67840871bcba9e71915fb704a8c0a051b2b352b51eab8cc177f09383e15f')
    text=text.replace('tools/native_threaded_wide_package_v1.py','tools/native_threaded_wide_package_v3.py')
    value=types.ModuleType('_callable_wide_identity');value.__file__=str(Path(__file__).resolve())
    exec(compile(text,'[callable wide identity family]','exec'),value.__dict__)
    return value


def functional_fingerprint(*args,**kwargs):return module().functional_fingerprint(*args,**kwargs)
def match_variants(*args,**kwargs):return module().match_variants(*args,**kwargs)

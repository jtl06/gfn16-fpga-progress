"""r38 policy on observed F16/F32 static hosts, preserving fit-slot locks."""
import hashlib
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='1a50703e0554575e323697a11d5bbf43778603f78b1c978406734d7678529516'
HOST_SHA='3fcd90e5a92ec332f350aa3be31eab16f106666cae42275cc2cce625960e0ac9'


def module():
    raw=(HERE/'native_class_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen class policy identity')
    text=raw.decode()
    changes=[('native_class_v1.py','native_class_v2.py'),('native_static_v2.py','native_static_v3.py'),
      ('6bfe9e244e50da02f9d3b3b1f47b0b7273158fc0b640c4311352a818b1705f6f',HOST_SHA),
      ('check_scratch_quota=static.check_scratch_quota)',
       'check_scratch_quota=static.check_scratch_quota, guard_toolchain=host.guard_toolchain, guard_protected=host.guard_protected, RUNTIME_CHECK=None)')]
    for old,new in changes:
        if old not in text:raise ValueError('unique F16 class policy anchor')
        text=text.replace(old,new)
    result=types.ModuleType('_class_v2');result.__file__=str(Path(__file__).resolve())
    exec(compile(text,str(HERE/'native_class_v1.py')+'[F16-interop]','exec'),result.__dict__)
    result.PINS['tools/native_class_v1.py']=PARENT_SHA
    return result


policy=module()
PINS=policy.PINS
SELECTIONS=policy.SELECTIONS
profile=policy.profile
parent=policy.parent
execution_limits=policy.execution_limits


def execute(manifest_path,pin,out):
    return policy.host.execute_with_parent(parent,PINS,manifest_path,pin,out)

"""Unchanged r38 class policy on the observed r49 resized static host."""
import hashlib
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
PARENT_SHA = '5a3ab8b8306e74de9d6dd9fcbe26ee185a25dff95ac6a5e1b51503ce00e543c3'
HOST_SHA = 'd6c2d781503926422f4647664d14d2c15a92dfe257a324f3f70c7e4e014ec9a9'


def module():
    raw = (HERE / 'native_class_v2.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError('frozen observed-host class policy')
    text = raw.decode()
    for old, new in [('native_class_v2.py', 'native_class_v3.py'),
                     ('native_static_v3.py', 'native_static_v4.py'),
                     ('3fcd90e5a92ec332f350aa3be31eab16f106666cae42275cc2cce625960e0ac9', HOST_SHA)]:
        if old not in text:
            raise ValueError('resized class source anchor')
        text = text.replace(old, new)
    result = types.ModuleType('_resized_class_policy')
    result.__file__ = str(Path(__file__).resolve())
    exec(compile(text, str(HERE / 'native_class_v2.py') + '[r49]', 'exec'), result.__dict__)
    result.PINS['tools/native_class_v2.py'] = PARENT_SHA
    return result


policy = module()
PINS = policy.PINS
SELECTIONS = policy.SELECTIONS
profile = policy.profile
parent = policy.parent
execution_limits = policy.execution_limits
execute = policy.execute

"""Interim automatic variants including the separately L3-admitted resized host."""
import hashlib
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='5693d9ef9de10658049cb31354d6b3d7ba2bc03fd6fed384a4cae0cbaf7abb3d'


def module():
    raw=(HERE/'native_auto_variants_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA: raise ValueError('frozen automatic variant helper')
    text=raw.decode()
    changes=[('native_azure_variant_refresh_v2.py','native_azure_variant_refresh_v3.py'),
      ('2a4f120415693b65a4f42a504cf890adcde491e123adb30dd7efaeaff7b88c4c','943d2672c082b8be003de3488062199204157403ca1b06e49d847190e54d316a'),
      ('native_profile_variants_v3.py','native_profile_variants_v4.py'),
      ('575a31c4a06d44139a406623f939bc38a591edc42304527dab2af5efe6fb4727','93350b5e7556f5a420de5e9c06cb4b9f7d672db3f685f71b57ebfc5e71635ddc'),
      ('native_class_v2.py','native_class_v3.py'),
      ('5a3ab8b8306e74de9d6dd9fcbe26ee185a25dff95ac6a5e1b51503ce00e543c3','ff1e738729c91758073b03739933172a5e578531d4bffc22d28c109c7384e505'),
      ('native_class_package_v4.py','native_class_package_v5.py'),
      ('native_package_v6.py','native_package_v7.py')]
    for old,new in changes:
        if old not in text: raise ValueError('automatic resized variant source anchor')
        text=text.replace(old,new)
    result=types.ModuleType('_resized_auto_variants');result.__file__=str(Path(__file__).resolve())
    exec(compile(text,str(HERE/'native_auto_variants_v1.py')+'[r49]','exec'),result.__dict__)
    return result


def expand_variants(*args,**kwargs): return module().expand_variants(*args,**kwargs)

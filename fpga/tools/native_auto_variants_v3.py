"""Automatic compatible static variants with explicit8GiB Azure alternatives."""
import hashlib
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='5693d9ef9de10658049cb31354d6b3d7ba2bc03fd6fed384a4cae0cbaf7abb3d'


def module():
    raw=(HERE/'native_auto_variants_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen automatic variant preparation')
    text=raw.decode()
    changes=[('native_azure_variant_refresh_v2.py','native_azure_variant_refresh_v4.py'),
      ('2a4f120415693b65a4f42a504cf890adcde491e123adb30dd7efaeaff7b88c4c','b5dca55b8ac4fc0e4f279ce93c7b178fbf115b2c8ea1afb227920ad06653e84a'),
      ('native_profile_variants_v3.py','native_profile_variants_v6.py'),
      ('575a31c4a06d44139a406623f939bc38a591edc42304527dab2af5efe6fb4727','8993b204cb4666a010c46d87b78c9c35d26f510aaca002ab2ac0095b7fb7fbdb'),
      ('native_class_v2.py','native_class_burst8_v1.py'),
      ('5a3ab8b8306e74de9d6dd9fcbe26ee185a25dff95ac6a5e1b51503ce00e543c3','8c7234c341ad20823520761c429e030f26b8ed4e90cb4b171f3f91f328cfe767'),
      ("runner='tools/native_class_package_v4.py' if azure", "runner='tools/native_class_package_burst8_v1.py' if profile.startswith('azure-burst16-static8g') else 'tools/native_class_package_v5.py' if azure"),
      ("'tools/native_package_v6.py' if azure", "'tools/native_stage_burst8_v1.py' if profile.startswith('azure-burst16-static8g') else 'tools/native_package_v7.py' if azure"),
      ("if azure:dependencies.insert(0,ROOT/'tools/native_package_v5.py')", "if azure and not profile.startswith('azure-burst16-static8g'):dependencies.insert(0,ROOT/'tools/native_package_v5.py')"),
      ("matches=[name for name in lane['profiles'] if name in policy.SELECTIONS]",
       "matches=[name for name in lane['profiles'] if name in policy.SELECTIONS and policy.profile(name)['memory_bytes'] >= ticket.get('minimum_ram_gib',ticket['resources']['ram_gib'])*(1<<30)]")]
    for old,new in changes:
        if old not in text:raise ValueError('automatic memory variant source anchor')
        text=text.replace(old,new)
    result=types.ModuleType('_memory_auto_variants');result.__file__=str(Path(__file__).resolve())
    exec(compile(text,str(HERE/'native_auto_variants_v1.py')+'[memory-compatible]','exec'),result.__dict__)
    return result


def expand_variants(*args,**kwargs):return module().expand_variants(*args,**kwargs)

"""Same-role fresh user75 serial variants; no claims, provider calls or launch."""
import hashlib
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
PARENT_SHA = 'fc3efb305ec26505b1108a5361622910aeaabdf6d836442821a8e1405b22a3e4'


def module():
    raw = (HERE / 'native_azure_variant_refresh_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError('frozen source-preserving refresh')
    text = raw.decode()
    for old, new in [
        ('native_class_package_v3.py', 'native_class_package_azure_signed_v1.py'),
        ('a8c42095d5d174b6bc622eb10774a0a581e6060b8366d981afabc39084ddcfdd',
         '4c1bbaa6ce951fb4be2786b73d048cfb1dd893806ab16add082d123e3cdc8d17'),
        ('native_profile_variants_v2.py', 'native_profile_variants_signed_v1.py'),
        ('064b9948606f1b008de2cb73a63a250ed0029f50ab3b2713483941bebf2f7d5e',
         '3f05daf7b081076732fd93e0b4d6e9a5c2d8909a36fd9c6085f827fbd7d19335'),
        ('native_class_v2.py', 'native_class_burst8_v1.py'),
        ("package.source_identity(role),selected['profile_sha256'])",
         "package.source_identity(role),selected['profile_sha256'], transition_path='results/throughput-20260929/azure-sim-resize-r49-v1/rate-transition-v1.json', transition_sha256='c4923266e1fabaeeca7cbf6e5f2444455c299accf5ed89c122927c47ed56ac92')"),
    ]:
        if old not in text:
            raise ValueError('exact75 refresh source anchor')
        text = text.replace(old, new)
    value = types.ModuleType('_qualified_azure75_refresh')
    value.__file__ = str(Path(__file__).resolve())
    exec(compile(text, '[source-identical user75 preparation]', 'exec'), value.__dict__)
    return value


def repackage_variant(*args, **kwargs):
    return module().repackage_variant(*args, **kwargs)


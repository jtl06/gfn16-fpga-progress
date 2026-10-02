"""Source-preserving refresh using the qualified r49 transition and profile."""
import hashlib
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
PARENT_SHA = 'fc3efb305ec26505b1108a5361622910aeaabdf6d836442821a8e1405b22a3e4'
PACKAGE_SHA = '3406f8b389155bfc6bf7d4fb2e0619820474ad3368bd1b2de2002a9c57fa7007'
VARIANTS_SHA = '93350b5e7556f5a420de5e9c06cb4b9f7d672db3f685f71b57ebfc5e71635ddc'
TRANSITION = 'results/throughput-20260929/azure-sim-resize-r49-v1/rate-transition-v1.json'
TRANSITION_SHA = 'c4923266e1fabaeeca7cbf6e5f2444455c299accf5ed89c122927c47ed56ac92'


def module():
    raw = (HERE/'native_azure_variant_refresh_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA: raise ValueError('frozen source preserving refresh')
    text = raw.decode()
    changes = [('native_class_package_v3.py','native_class_package_v5.py'),
               ('a8c42095d5d174b6bc622eb10774a0a581e6060b8366d981afabc39084ddcfdd',PACKAGE_SHA),
               ('native_profile_variants_v2.py','native_profile_variants_v4.py'),
               ('064b9948606f1b008de2cb73a63a250ed0029f50ab3b2713483941bebf2f7d5e',VARIANTS_SHA),
               ('native_class_v2.py','native_class_v3.py'),
               ("package.source_identity(role),selected['profile_sha256'])",
                "package.source_identity(role),selected['profile_sha256'], transition_path="+repr(TRANSITION)+", transition_sha256="+repr(TRANSITION_SHA)+")")]
    for old,new in changes:
        if old not in text: raise ValueError('qualified refresh source anchor')
        text = text.replace(old,new)
    result=types.ModuleType('_qualified_resize_refresh');result.__file__=str(Path(__file__).resolve())
    exec(compile(text,str(HERE/'native_azure_variant_refresh_v1.py')+'[qualified-r49]','exec'),result.__dict__)
    return result


def repackage_variant(*args, **kwargs): return module().repackage_variant(*args, **kwargs)

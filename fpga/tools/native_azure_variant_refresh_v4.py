"""Same-source Azure refresh with separately pinned optional8GiB envelope."""
import hashlib
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='fc3efb305ec26505b1108a5361622910aeaabdf6d836442821a8e1405b22a3e4'
VARIANTS_SHA='8993b204cb4666a010c46d87b78c9c35d26f510aaca002ab2ac0095b7fb7fbdb'


def module(profile_id):
    enlarged=profile_id.startswith('azure-burst16-static8g')
    package='native_class_package_burst8_v1.py' if enlarged else 'native_class_package_v5.py'
    package_sha='8d7c794ffd6e136b15ccf75a6e72621ae24886a3bf0cd088eca3a42acf6fc59f' if enlarged else '3406f8b389155bfc6bf7d4fb2e0619820474ad3368bd1b2de2002a9c57fa7007'
    executor='native_class_burst8_v1.py' if enlarged else 'native_class_v3.py'
    raw=(HERE/'native_azure_variant_refresh_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen source-preserving refresh')
    text=raw.decode()
    changes=[('native_class_package_v3.py',package),
      ('a8c42095d5d174b6bc622eb10774a0a581e6060b8366d981afabc39084ddcfdd',package_sha),
      ('native_profile_variants_v2.py','native_profile_variants_v6.py'),
      ('064b9948606f1b008de2cb73a63a250ed0029f50ab3b2713483941bebf2f7d5e',VARIANTS_SHA),
      ('native_class_v2.py',executor),
      ("package.source_identity(role),selected['profile_sha256'])",
       "package.source_identity(role),selected['profile_sha256'], transition_path='results/throughput-20260929/azure-sim-resize-r49-v1/rate-transition-v1.json', transition_sha256='c4923266e1fabaeeca7cbf6e5f2444455c299accf5ed89c122927c47ed56ac92')")]
    for old,new in changes:
        if old not in text:raise ValueError('memory refresh source anchor')
        text=text.replace(old,new)
    result=types.ModuleType('_memory_azure_refresh');result.__file__=str(Path(__file__).resolve())
    exec(compile(text,str(HERE/'native_azure_variant_refresh_v1.py')+'[same-source8GiB]','exec'),result.__dict__)
    return result


def repackage_variant(existing_package_dir,profile_id,*args,**kwargs):
    return module(profile_id).repackage_variant(existing_package_dir,profile_id,*args,**kwargs)

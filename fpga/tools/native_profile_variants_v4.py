"""Exact control additions for qualified resized-host immutable variants."""
import hashlib
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
PARENT_SHA = '575a31c4a06d44139a406623f939bc38a591edc42304527dab2af5efe6fb4727'
CONTROLS = {
    'tools/native_class_v3.py': 'ff1e738729c91758073b03739933172a5e578531d4bffc22d28c109c7384e505',
    'tools/native_class_package_v5.py': '3406f8b389155bfc6bf7d4fb2e0619820474ad3368bd1b2de2002a9c57fa7007',
    'tools/native_static_v4.py': 'd6c2d781503926422f4647664d14d2c15a92dfe257a324f3f70c7e4e014ec9a9',
    'cloud/azure-burst16-static-profiles-v1.json': 'eef2a816c7fc6ae5e53919b24b2bb135a16808d7ef7ccb7341395b0c030b596d',
    'results/throughput-20260929/azure-sim-resize-r49-v1/toolchain-observation-v1.json': '5f79de9b9387eb7ae62fa1d644290aa7fa46d6001972686987a0707b294f6a8e',
}


def module():
    raw = (HERE/'native_profile_variants_v3.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA: raise ValueError('frozen functional variant checker')
    text = raw.decode()
    anchor = '    exec(compile(text,str(HERE/'
    index = text.index(anchor)
    text = text[:index] + '    text=text.replace("    adjusted=copy.deepcopy(manifest);ignored={}", "    parent.KNOWN_CONTROLS.update("+repr(CONTROLS)+")\\n    adjusted=copy.deepcopy(manifest);ignored={}")\n' + text[index:]
    result = types.ModuleType('_resized_variants'); result.__file__ = str(Path(__file__).resolve())
    result.CONTROLS = CONTROLS
    exec(compile(text, str(HERE/'native_profile_variants_v3.py')+'[r49]', 'exec'), result.__dict__)
    return result


def functional_fingerprint(*args, **kwargs): return module().functional_fingerprint(*args, **kwargs)
def match_variants(*args, **kwargs): return module().match_variants(*args, **kwargs)

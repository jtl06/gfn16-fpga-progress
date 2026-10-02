"""Additive exact threaded build identity; never executes or admits a cached ELF.

Version1 remains the admission policy for frozen one-thread evidence. This
successor includes actual compiler/model/context configuration and the admitted
physical allocation. Equality grants build-key equality, never correctness,
resource reservation, dispatch or promotion.
"""
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re

try:
    from . import native_thread_config_v1 as threads
except ImportError:
    # Shared packages load pinned helpers by absolute filename. Avoid ambient
    # PYTHONPATH lookup and bind the standalone dependency to these exact bytes.
    runtime_path = Path(__file__).with_name('native_thread_config_v1.py')
    with runtime_path.open('rb') as stream:
        runtime_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    if runtime_sha != '900b4b7598a6f405ec87ceaa1e82dd391e02c18c4ddbb36f64fa93b5ac613be2':
        raise ValueError('exact standalone thread helper identity')
    spec = importlib.util.spec_from_file_location('_identity_v2_runtime', runtime_path)
    threads = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(threads)


def need(ok, why):
    if not ok:
        raise ValueError(why)


def digest_ok(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def build_identity(manifest, profile):
    need(manifest.get('schema') == 'native-source-gate-v1', 'source-gate schema')
    sources = manifest['sources']
    need(type(sources) is dict and sources and all(digest_ok(value) for value in sources.values()), 'source hashes')
    for name in sources:
        path = PurePosixPath(name)
        need(type(name) is str and str(path) == name and not path.is_absolute()
             and '..' not in path.parts and name not in ('', '.'), 'safe source closure')
    build = manifest['build']
    need(all(name in sources for name in build['sv_sources'] + [build['cpp_source']]), 'complete compiled source closure')
    need(type(build['parameters']) is dict and all(type(value) is int for value in build['parameters'].values()), 'typed HDL parameters')
    runtime = threads.validate_build(build, manifest['probe']['expected_json'])
    need(profile.get('hashes') and all(digest_ok(value) for value in profile['hashes'].values()), 'exact tool hashes')
    allocation = threads.validate_allocation(profile['runtime_allocation'], runtime)
    identity = dict(schema='gfn16-native-build-identity-v2', host=manifest['host'],
                    source_root=manifest['source_root'], sources=sources, build=build,
                    tool_hashes=profile['hashes'], verilator_dir=profile['verilator_dir'],
                    tool_paths=profile.get('tool_paths', {}),
                    abi='approved-host-linux-x86_64-thread-aware-v1', model_threads=runtime,
                    context_threads=runtime, compile_workers=2, runtime_allocation=allocation,
                    verilator_flags=threads.verilator_flags(build))
    identity = json.loads(json.dumps(identity))
    encoded = json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()
    return dict(identity=identity, build_key=hashlib.sha256(encoded).hexdigest())

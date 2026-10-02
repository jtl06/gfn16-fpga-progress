"""Read-only role runtime scope; compatible compilers do not imply portable assets.

Call before automatic host expansion, selection and launch. No candidate imports,
native execution, artifact rewrites or approval inference occur here.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath

SOAK = 'reference/core27_t5b_soak_native_v1.py'
SOAK_SHA = '43a35c1bd1c2d256fb793a8087681e9e2c0281441eeca57aa2fd6dfdf7934db0'


def need(ok, why):
    if not ok:
        raise ValueError('role host scope: ' + why)


def read_pinned(path, pin):
    path = Path(path)
    need(not path.is_symlink() and path.is_file(), 'regular pinned input')
    raw = path.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == pin, 'input hash mismatch')
    return json.loads(raw)


def hosts(value):
    need(type(value) is list and value and all(type(x) is str and x for x in value)
         and len(value) == len(set(value)), 'nonempty unique host list')
    return set(value)


def host_allowed(ticket, host):
    """Return False outside the intersection; malformed/broken bindings raise.

    Unrestricted ordinary roles retain existing behavior. The exact known soak
    validator is default-safe even when its duration proof is absent: its closed
    runtime asset's hostname remains mandatory. A distinct cross-runtime bridge
    is a new source identity, not an exception to this validator's contract.
    """
    scope = None
    if 'allowed_hosts' in ticket:
        scope = hosts(ticket['allowed_hosts'])
    package = ticket.get('package')
    if not package:
        variants = ticket.get('packages', ticket.get('package_variants', []))
        need(bool(variants), 'immutable package required')
        package = variants[0]
    directory = Path(package['archive']).parent
    manifest = read_pinned(directory / 'manifest.json', package['manifest_sha256'])
    proof_ref = ticket.get('measured_runtime_admission')
    if proof_ref is not None:
        need(type(proof_ref) is dict and set(proof_ref) == {'path', 'sha256'}, 'proof reference')
        proof = read_pinned(proof_ref['path'], proof_ref['sha256'])
        need(type(proof.get('status')) is str and proof['status'].startswith('PASS_'),
             'duration proof must record a passed contract')
        admitted = hosts(proof['compatible_hosts'])
        need(proof['source_model_build'] == manifest['build'], 'duration model configuration binding')
        pins = proof['source_model_pins']
        need(type(pins) is dict and pins, 'duration model source binding')
        need(all(manifest['sources'].get(name) == pin for name, pin in pins.items()),
             'duration model source binding')
        scope = admitted if scope is None else scope & admitted
    for step in manifest.get('steps', []):
        validator = step.get('validator', {})
        if validator.get('source') != SOAK:
            continue
        need(manifest['sources'].get(SOAK) == SOAK_SHA, 'known soak validator changed')
        relative = validator.get('assets', {}).get('runtime')
        need(type(relative) is str and relative and not PurePosixPath(relative).is_absolute()
             and '..' not in PurePosixPath(relative).parts, 'closed runtime asset path')
        root = directory / 'capture/source/fpga'
        path = root / relative
        need(path.resolve().is_relative_to(root.resolve()), 'runtime asset escapes source root')
        runtime = read_pinned(path, manifest['sources'][relative])
        admitted = hosts([runtime['host']])
        scope = admitted if scope is None else scope & admitted
    return scope is None or host in scope

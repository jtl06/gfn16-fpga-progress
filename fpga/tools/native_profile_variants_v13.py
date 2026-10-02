"""Exact ordinal3300 controls; preserve the complete source-bound duration."""
import copy
import hashlib
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT_SHA = '270ca203ddb4ac52e93156b03aa21f953519e3594f2c667b825b36fa67fb9be7'
CONTROLS = {
    'tools/native_ordinal_duration_v1.py': 'b68a3984f581b4ae3170b1e48b62fc9d6214fe1e6bf47daf1bb30c96aa25c8d6',
    'tools/native_ordinal_class_v1.py': '744f041a01b7104762f3220a2a7e60141b19ebd4c472c24301d7c45b7d11a8f0',
    'tools/native_ordinal_package_v1.py': '2fc6d2dfab63f7b366826b51c59efa74c7c39f0ed77615da75dbeb4cff719245',
    'tools/native_ordinal_stage_v1.py': 'a431a6efa0b9c63c75f553dc5994b4481c71458b25bdcfd33742d65e154cc1ff',
}
REQUIRED = set(CONTROLS) - {'tools/native_ordinal_stage_v1.py'}


def need(ok, why):
    if not ok:
        raise ValueError('ordinal identity: ' + why)


def load(name, pin):
    path = HERE / name
    need(not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == pin,
         'exact trusted helper')
    spec = importlib.util.spec_from_file_location('_ordinal_identity_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def functional_fingerprint(manifest, budget=None, source_root=None):
    parent = load('native_profile_variants_v12.py', PARENT_SHA)
    sources = manifest['sources']
    ordinal = (bool(set(CONTROLS) & set(sources)) or
               manifest.get('runtime_duration', {}).get('shape', {}).get('id') ==
               'ordinal-single-model3300-v1')
    if not ordinal:
        return parent.functional_fingerprint(manifest, budget, source_root)
    need(manifest['host'] == 'gfn16-pilot-c4d' and manifest.get('phase') == 'run' and
         manifest['cpu_profile'] in ('gcp-c4d-static01-v1', 'gcp-c4d-static23-v1'),
         'exact GCP8GiB run placement')
    need(budget is not None and budget.get('provider') == 'gcp', 'GCP accounting only')
    need(source_root is not None, 'immutable source root required')
    root = Path(source_root)
    need(root.is_dir() and root.resolve() == root, 'canonical source root')
    need(REQUIRED <= set(sources), 'complete exact ordinal family')
    mandatory = set(manifest['build']['sv_sources']) | {manifest['build']['cpp_source']}
    for step in manifest['steps']:
        if 'validator' in step:
            mandatory.add(step['validator']['source'])
            mandatory.update(step['validator']['assets'].values())
    ignored = {}
    for name, pin in CONTROLS.items():
        if name not in sources:
            continue
        path = root / name
        need(name not in mandatory, 'compiled/validator/asset cannot be excluded')
        need(sources[name] == pin and path.resolve() == path and path.is_file() and
             hashlib.sha256(path.read_bytes()).hexdigest() == pin, 'source-closed control: ' + name)
        ignored[name] = pin
    policy = load('native_ordinal_duration_v1.py', CONTROLS['tools/native_ordinal_duration_v1.py'])
    policy.validate(manifest, root, manifest['host'])
    adjusted = copy.deepcopy(manifest)
    for name in ignored:
        del adjusted['sources'][name]
    value = parent.functional_fingerprint(adjusted, budget, source_root)
    need(value['identity']['runtime_duration'] == manifest['runtime_duration'],
         'complete duration shape and contract retained')
    value['ignored_exact_controls'].update(ignored)
    return value


def match_variants(variants):
    need(type(variants) is list and len(variants) >= 2, 'multiple immutable variants')
    values = [functional_fingerprint(v['manifest'], v.get('budget'), v.get('source_root'))
              for v in variants]
    need(len({v['sha256'] for v in values}) == 1, 'functional role or duration differs')
    return dict(status='MATCH_functional_role_only', functional_sha256=values[0]['sha256'],
                one_logical_claim_required=True, fresh_budget_admission_conferred=False,
                variants=values)

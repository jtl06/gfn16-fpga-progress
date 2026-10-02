"""Exact finite-long framework lineage; retain role, evidence and duration shape."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT_SHA = '8993b204cb4666a010c46d87b78c9c35d26f510aaca002ab2ac0095b7fb7fbdb'
CONTROLS = {
    'tools/native_long_duration_v1.py': 'aed7092d33ddedf19405e8da4df4e4bc1b31e29d1054369dd2ef4805f8d89b2c',
    'tools/native_long_class_v1.py': 'ed9c3bbc8796862effc9409beff9a440cb2d13cd4b4cb55f822925ab5ecf1c4f',
    'tools/native_long_class_v2.py': 'a57b61814ae9e19e878a35d186987f67093dc50fb369e764eb3bb468f157149b',
    'tools/native_long_package_v1.py': '84f806d3b6a5a09acd652849418e65f55f05e443ee325980b30085c1f9cdc64f',
    'tools/native_long_package_v2.py': '1e68060c89b8a013b42e87bb11ced3443b42dc74872e6f2dcbc3b3e39ecc7d06',
    'tools/native_long_package_v3.py': 'c97bbe37261bebc546abba7e8bce99e5fefc6d791c0e63a11160e7883426aa63'}


def module():
    path = HERE / 'native_profile_variants_v6.py'
    if hashlib.sha256(path.read_bytes()).hexdigest() != PARENT_SHA:
        raise ValueError('exact functional checker')
    spec = importlib.util.spec_from_file_location('_long_variants_parent', path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    value.CONTROLS.update(CONTROLS)
    return value


def functional_fingerprint(manifest, *args, **kwargs):
    value = module().functional_fingerprint(manifest, *args, **kwargs)
    if 'runtime_duration' in manifest:
        value['identity']['runtime_duration'] = manifest['runtime_duration']
        value['sha256'] = hashlib.sha256(json.dumps(value['identity'], sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return value


def match_variants(variants):
    if type(variants) is not list or len(variants) < 2:
        raise ValueError('multiple exact immutable variants')
    values = [functional_fingerprint(v['manifest'], v.get('budget'), v.get('source_root')) for v in variants]
    if len({v['sha256'] for v in values}) != 1:
        raise ValueError('functional role or duration contract differs')
    return dict(status='MATCH_functional_role_only', functional_sha256=values[0]['sha256'],
                one_logical_claim_required=True, fresh_budget_admission_conferred=False, variants=values)

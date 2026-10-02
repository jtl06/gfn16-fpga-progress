"""Exact signed-pending accounting successor; unchanged roles delegate frozen14."""
import hashlib
import importlib.util
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='a2b66dccc438fd84a8d643c3be1a7bda7995b0829197842df4bd1a79c6618ffa'
SIGNED_SHA='9c3d902e3da0969145c4148f06a51ec9ca22a322513068074f7b338cb8ddf137'
PACKAGE_SHA='4c1bbaa6ce951fb4be2786b73d048cfb1dd893806ab16add082d123e3cdc8d17'


def parent(signed=False):
    path=HERE/'native_profile_variants_v14.py';raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:
        raise ValueError('frozen historical identity source')
    value=types.ModuleType('_signed_historical_identity');value.__file__=str(Path(__file__).resolve())
    text=raw.decode()
    if signed:
        for old,new in [('host_hours_azure_v5.py','host_hours_azure_signed_v1.py'),
            ('4f5a066527f5531c480d6c8ccb3d6c213b57bdf26e18e2b14cfb55e5958a2ced',SIGNED_SHA),
            ('native_class_package_azure75_v1.py','native_class_package_azure_signed_v1.py'),
            ('231c1b9edc6bcf65a071cf5333e30041ca7af66efb6ae95cc1ec822ad2dcf960',PACKAGE_SHA)]:
            if old not in text:raise ValueError('exact signed historical source anchor')
            text=text.replace(old,new)
    exec(compile(text,'[signed pending historical identity]','exec'),value.__dict__)
    return value


def functional_fingerprint(manifest,budget=None,source_root=None):
    signed=bool(budget and budget.get('checker_sha256')==SIGNED_SHA)
    return parent(signed).functional_fingerprint(manifest,budget,source_root)


def match_variants(variants):
    values=[functional_fingerprint(v['manifest'],v.get('budget'),v.get('source_root')) for v in variants]
    if len(values)<2 or len({v['sha256'] for v in values})!=1:
        raise ValueError('functional role/source/outcomes differ')
    return dict(status='MATCH_functional_role_only',functional_sha256=values[0]['sha256'],
        one_logical_claim_required=True,fresh_budget_admission_conferred=False,variants=values)

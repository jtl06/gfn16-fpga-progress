"""Exact known memory-envelope controls; functional role is unchanged."""
import hashlib
import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parent
PARENT_SHA='93350b5e7556f5a420de5e9c06cb4b9f7d672db3f685f71b57ebfc5e71635ddc'
CONTROLS={
 'tools/native_static_gcp24_v1.py':'0757179bb692e6dadc0a163a4847303c1ed49d9d57bb306a40af9d881e818bc7',
 'tools/native_class_gcp24_v1.py':'13697e0cf18f4fddfc896b35d32e6fa26123639b304e5ae42ff99a03890a8fff',
 'tools/native_class_package_gcp24_v1.py':'39a85fbde4a87b773fc51fb0fad65f7a21e7549c91bd6d13f7dd33b404ef1d32',
 'cloud/gcp-native-24g-profiles-v1.json':'1d657a2bd188dee76926ba1497cec7f46089dde2d0542e1a27f77f3f143ef140'}


def module():
    path=HERE/'native_profile_variants_v4.py'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=PARENT_SHA: raise ValueError('exact functional checker')
    spec=importlib.util.spec_from_file_location('_memory_variant_parent',path)
    parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
    parent.CONTROLS.update(CONTROLS)
    return parent


def functional_fingerprint(*args,**kwargs):return module().functional_fingerprint(*args,**kwargs)
def match_variants(*args,**kwargs):return module().match_variants(*args,**kwargs)

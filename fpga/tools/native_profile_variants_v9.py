"""Exact memory-only Azure24 controls; all role/runtime proof remains bound."""
import hashlib
import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parent
PARENT_SHA='11cfdd0c35bc0e2afebc61c47bf83a0d05a60be3691e3f0f675e8a39919d9e73'
CONTROLS={
 'tools/native_static_burst24_v1.py':'b5c6f1f9c1ab74203df59de8f0a6b71d033c478c4bc86a88ac8038814b27d7f1',
 'tools/native_class_burst24_v1.py':'bac59e83c7d65bd6e99d209789121ea6109657bdef9dc7c5f482ffbfadf90911',
 'tools/native_class_package_burst24_v1.py':'9b4fc9d321c305bf69a345792af9b908782c76595ece7e39fb3f827cf83af8ff',
 'cloud/azure-burst16-memory24-profiles-v1.json':'83e6b6ccb3de25fa266e9da52262e6461498f9cd0ea2a462cfafcd8d991e3e59'}


def module():
    path=HERE/'native_profile_variants_v8.py'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=PARENT_SHA:raise ValueError('exact historical variant checker')
    spec=importlib.util.spec_from_file_location('_memory24_variants',path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    original=value.load
    def load(path,pin):
        result=original(path,pin)
        if path.name=='native_profile_variants_v7.py':result.CONTROLS.update(CONTROLS)
        return result
    value.load=load
    return value


def functional_fingerprint(*args,**kwargs):return module().functional_fingerprint(*args,**kwargs)
def match_variants(*args,**kwargs):return module().match_variants(*args,**kwargs)

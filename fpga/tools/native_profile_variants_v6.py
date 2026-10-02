"""Exact known memory-envelope controls; functional role is unchanged."""
import hashlib
import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parent
PARENT_SHA='aaf4cff3fd16c9226b7d28f8cffe21dc89890f2a229b5a0a8d7ca51f6e6269c7'
CONTROLS={
 'tools/native_static_burst8_v1.py':'45ae0c241c3a9fbe158d3cb3dbbf569760a1a6af0f3a2d47cb9c75cd2a9ba5cf',
 'tools/native_class_burst8_v1.py':'8c7234c341ad20823520761c429e030f26b8ed4e90cb4b171f3f91f328cfe767',
 'tools/native_class_package_burst8_v1.py':'8d7c794ffd6e136b15ccf75a6e72621ae24886a3bf0cd088eca3a42acf6fc59f',
 'cloud/azure-burst16-memory8-profiles-v1.json':'04fe25064f68301526492ebd232dba201fb15469e88c9f2cee0d3389215a9808'}


def module():
    path=HERE/'native_profile_variants_v5.py'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=PARENT_SHA: raise ValueError('exact functional checker')
    spec=importlib.util.spec_from_file_location('_memory_variant_parent',path)
    parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
    parent.CONTROLS.update(CONTROLS)
    return parent


def functional_fingerprint(*args,**kwargs):return module().functional_fingerprint(*args,**kwargs)
def match_variants(*args,**kwargs):return module().match_variants(*args,**kwargs)

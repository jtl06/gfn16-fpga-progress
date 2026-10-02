"""Preserve exact wide allocation/cache identity in short threaded pilot keys."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PARENT_SHA='d038948c78649f80b31a45f5710cfb61eeaf8f089a2e35fa0a60f17312f16ec8'
STAGER_SHA='20581efa4daadb13ec986224ed5fc1c86df339e5508fd400a5f09340482a83f9'


def load(name,pin):
    path=HERE/name
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=pin:raise ValueError('exact fixed-placement identity helper')
    spec=importlib.util.spec_from_file_location('_wide_variant_'+path.stem,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def functional_fingerprint(manifest,budget=None,source_root=None):
    parent=load('native_profile_variants_v9.py',PARENT_SHA)
    if 'wide_thread_pilot' not in manifest and 'tools/native_threaded_wide_package_v1.py' not in manifest['sources']:
        return parent.functional_fingerprint(manifest,budget,source_root)
    if source_root is None:raise ValueError('wide identity needs immutable source closure')
    root=Path(source_root);stage=load('native_threaded_wide_stage_v1.py',STAGER_SHA)
    payload={'manifest.json':json.dumps(manifest).encode()}
    observation='results/throughput-20260929/core27-t5b-thread-wide-topology-v1/observation-v2.json'
    for name,pin in {stage.HARDWARE:stage.HARDWARE_SHA,stage.OVERLAY:stage.OVERLAY_SHA,
                     observation:'d001cb0cb31811ac965d0828dfdf2d6ffacf120d8d7a976b9944315a6fa646a3'}.items():
        path=root/name
        if path.resolve()!=path or manifest['sources'].get(name)!=pin or hashlib.sha256(path.read_bytes()).hexdigest()!=pin:
            raise ValueError('source-closed exact wide hardware/cache/allocation')
        payload['capture/source/fpga/'+name]=path.read_bytes()
    contract=manifest.get('fixed_execution',{})
    stage.profile_from_payload(payload,dict(profile=manifest['cpu_profile'],placement=contract.get('placement'),fixed_execution=contract),manifest['sources'])
    role=manifest['wide_thread_pilot'];count=manifest['build']['runtime_threads']
    if type(count) is not int or count not in (2,4,8) or type(role.get('thread_count')) is not int or role['thread_count']!=count:
        raise ValueError('exact wide model/context role count')
    value=parent.functional_fingerprint(manifest,budget,source_root)
    value['identity'].update(fixed_execution=contract,wide_thread_pilot=role)
    value['sha256']=hashlib.sha256(json.dumps(value['identity'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return value


def match_variants(variants):
    if type(variants) is not list or len(variants)<2:raise ValueError('multiple immutable variants')
    values=[functional_fingerprint(v['manifest'],v.get('budget'),v.get('source_root')) for v in variants]
    if len({v['sha256'] for v in values})!=1:raise ValueError('functional source/count/fixed allocation differs')
    return dict(status='MATCH_functional_role_only',functional_sha256=values[0]['sha256'],one_logical_claim_required=True,
                fresh_budget_admission_conferred=False,variants=values)

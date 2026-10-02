"""Historical5015-budget identity for the exact measured thread2 long family.

Other roles use the frozen matcher unchanged. Historical replay is not fresh
launch admission. All role sources, outcomes and full duration proof remain.
"""
import copy
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PARENT_SHA='cfb2873effce30593d6f32b417ab4ea8409f5c81a031652935f28c21d5fea5b0'
METER_SHA='d133b301ff0dc193774090f991ffa8bc6ee51f06fd318d21ff89673b1632a20c'
FAMILY={
 'tools/native_threaded_long_package_v2.py':'3da644327e3bdc7cdef0ae9804516b22942900a08b1e6a8faf19719011fcf04c',
 'tools/native_threaded_long_class_v2.py':'8df98eae0fa2b82f868eadf2730cb1b47c11fdf02f07445b1c3b62983e1edfb4',
 'tools/native_threaded_duration_v1.py':'5107d198cca687d1305161d9f1a8ffd952b7691aa92e88f12326ddee65e13fb5'}
SHAPE=dict(id='t5b-burst23-thread2-continuous5000-v1',model_command_seconds=4500,
 ancillary_command_seconds=1800,overall_seconds=4800,outer_seconds=5000,
 stop_grace_seconds=15,lock_wait_seconds=1800,model_threads=2)


def need(ok,why):
    if not ok:raise ValueError(why)


def load(path,pin):
    need(path.resolve()==path and hashlib.sha256(path.read_bytes()).hexdigest()==pin,'exact variant dependency')
    spec=importlib.util.spec_from_file_location('_threaded_long_variant_'+path.stem,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def functional_fingerprint(manifest,budget=None,source_root=None):
    parent=load(HERE/'native_profile_variants_v7.py',PARENT_SHA)
    if 'tools/native_threaded_long_package_v2.py' not in manifest['sources']:
        return parent.functional_fingerprint(manifest,budget,source_root)
    need(all(manifest['sources'].get(k)==v for k,v in FAMILY.items()),'exact measured threaded-long2 family')
    need(manifest['host']=='gfn16-azure-sim-f32' and manifest['cpu_profile']=='azure-burst16-static23-v1'
         and type(manifest['build']['runtime_threads']) is int and manifest['build']['runtime_threads']==2
         and manifest['runtime_duration']['shape']==SHAPE,'exact measured profile/thread/duration')
    need(budget and budget.get('provider')=='azure' and budget.get('checker_sha256')==METER_SHA,'source-bound Azure5015 accounting')
    root=Path(source_root);need(root.resolve()==root and root.is_dir(),'canonical accounting closure')
    checker=load(HERE.parent/'cloud/host_hours_azure_v3.py',METER_SHA)
    pins=checker.evidence_pins(budget)
    for name,pin in {**pins,**FAMILY}.items():
        path=root/name
        need(not Path(name).is_absolute() and '..' not in Path(name).parts and path.resolve()==path
             and manifest['sources'].get(name)==pin and hashlib.sha256(path.read_bytes()).hexdigest()==pin,'closed accounting/control evidence')
    checker.ROOT=root
    provider=json.loads((root/budget['provider_inputs']['path']).read_text())
    role=manifest.get('budget_source_members')
    need(type(role) is dict and role and all(manifest['sources'].get(k)==v for k,v in role.items()),'original source-bound role')
    identity={key:manifest[key] for key in ('build','probe','steps')};identity['sources']=role
    source_pin=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    checker.validate_budget(budget,manifest['host'],5015,source_sha256=source_pin,
      profile_sha256='eef2a816c7fc6ae5e53919b24b2bb135a16808d7ef7ccb7341395b0c030b596d',
      now=datetime.fromisoformat(provider['observed_at_utc'].replace('Z','+00:00')))
    mandatory=set(manifest['build']['sv_sources'])|{manifest['build']['cpp_source']}
    for step in manifest['steps']:
        if 'validator' in step:mandatory|={step['validator']['source'],*step['validator']['assets'].values()}
    adjusted=copy.deepcopy(manifest);ignored={}
    for name,pin in pins.items():
        if name not in role and name not in mandatory:ignored[name]=pin;adjusted['sources'].pop(name)
    result=parent.functional_fingerprint(adjusted)
    result.update(ignored_historical_accounting=ignored,fresh_budget_admission_conferred=False)
    return result


def match_variants(variants):
    need(type(variants) is list and len(variants)>=2,'multiple immutable variants')
    values=[functional_fingerprint(v['manifest'],v.get('budget'),v.get('source_root')) for v in variants]
    need(len({v['sha256'] for v in values})==1,'functional role or duration differs')
    return dict(status='MATCH_functional_role_only',functional_sha256=values[0]['sha256'],one_logical_claim_required=True,
                fresh_budget_admission_conferred=False,variants=values)

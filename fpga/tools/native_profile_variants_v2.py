"""Cross-host functional identity with exact historical accounting evidence.

Historical budget replay identifies nonfunctional accounting inputs only; it
never grants fresh launch admission. Live package budget checks are unchanged.
"""
import copy
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PARENT_SHA='ef4e69d99301c29a2b6c26b06035bcd854eb81eecf5b4666de2fa6795d5f00dc'
METER_SHA='b0875ec8fb12780c637548e9664d25d47a2b77bb8ef7d3ff997bbdfc640a8c9e'

def need(ok,why):
    if not ok:raise ValueError(why)
def load(path,pin):
    need(path.resolve()==path and hashlib.sha256(path.read_bytes()).hexdigest()==pin,'exact variant helper')
    spec=importlib.util.spec_from_file_location('_variant_'+path.stem,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def functional_fingerprint(manifest,budget=None,source_root=None):
    parent=load(HERE/'native_profile_variants_v1.py',PARENT_SHA)
    adjusted=copy.deepcopy(manifest);ignored={}
    if budget and budget.get('provider')=='azure':
        need(source_root is not None,'Azure accounting source root required')
        root=Path(source_root);need(root.resolve()==root and root.is_dir(),'canonical accounting closure root')
        checker=load(HERE.parent/'cloud/host_hours_azure_v2.py',METER_SHA)
        need(budget.get('checker_sha256')==METER_SHA and budget.get('host')==manifest['host'],'exact Azure accounting host/checker')
        pins=checker.evidence_pins(budget)
        for name,pin in pins.items():
            path=root/name
            need(not Path(name).is_absolute() and '..' not in Path(name).parts and path.resolve()==path
                 and manifest['sources'].get(name)==pin and hashlib.sha256(path.read_bytes()).hexdigest()==pin,'closed accounting evidence')
        # Historical replay reads only this capture's source-closed files. Use
        # its capture time to validate its original accounting, never current
        # eligibility; stale live admission remains forbidden elsewhere.
        checker.ROOT=root
        provider=json.loads((root/budget['provider_inputs']['path']).read_text())
        role=manifest.get('budget_source_members')
        need(type(role) is dict and role and all(manifest['sources'].get(k)==v for k,v in role.items()),'source-bound original role members')
        identity={key:manifest[key] for key in ('build','probe','steps')};identity['sources']=role
        source_pin=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        checker.validate_budget(budget,manifest['host'],3715,source_sha256=source_pin,
            now=datetime.fromisoformat(provider['observed_at_utc'].replace('Z','+00:00')))
        mandatory=set(manifest['build']['sv_sources'])|{manifest['build']['cpp_source']}
        for step in manifest['steps']:
            if 'validator' in step:mandatory|={step['validator']['source'],*step['validator']['assets'].values()}
        for name,pin in pins.items():
            if name not in role and name not in mandatory:
                ignored[name]=pin;adjusted['sources'].pop(name)
    value=parent.functional_fingerprint(adjusted)
    value['ignored_historical_accounting']=ignored
    value['fresh_budget_admission_conferred']=False
    return value

def match_variants(variants):
    need(type(variants) is list and len(variants)>=2,'multiple exact immutable variants')
    values=[functional_fingerprint(item['manifest'],item.get('budget'),item.get('source_root')) for item in variants]
    need(len({value['sha256'] for value in values})==1,'cross-host functional role/config/outcomes differ')
    return dict(status='MATCH_functional_role_only',functional_sha256=values[0]['sha256'],one_logical_claim_required=True,
                fresh_budget_admission_conferred=False,variants=values)

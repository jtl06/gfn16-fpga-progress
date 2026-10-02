"""Exact functional matching with historical Azure meter-v2/v3 captures."""
import hashlib
import importlib.util
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='064b9948606f1b008de2cb73a63a250ed0029f50ab3b2713483941bebf2f7d5e'
METER_SHA='d133b301ff0dc193774090f991ffa8bc6ee51f06fd318d21ff89673b1632a20c'
PACKAGE_SHA='9ca500ca811740232017de9f3f852bc8e838e5384769e26c401ab891d3295564'

def module(new=False):
    raw=(HERE/'native_profile_variants_v2.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('exact variant parent')
    text=raw.decode()
    if new:
        text=text.replace('host_hours_azure_v2.py','host_hours_azure_v3.py').replace('b0875ec8fb12780c637548e9664d25d47a2b77bb8ef7d3ff997bbdfc640a8c9e',METER_SHA)
    anchor="    parent=load(HERE/'native_profile_variants_v1.py',PARENT_SHA)"
    if text.count(anchor)!=1:raise ValueError('variant control source anchor')
    text=text.replace(anchor,anchor+"\n    parent.KNOWN_CONTROLS['tools/native_class_package_v4.py']='"+PACKAGE_SHA+"'",1)
    result=types.ModuleType('_meter_phase_variants');result.__file__=str(Path(__file__).resolve())
    exec(compile(text,str(HERE/'native_profile_variants_v2.py')+'[r49]','exec'),result.__dict__)
    return result

def functional_fingerprint(manifest,budget=None,source_root=None):
    use_new=bool(budget and budget.get('kind')=='azure-host-hours-v3')
    return module(use_new).functional_fingerprint(manifest,budget,source_root)

def match_variants(variants):
    if type(variants) is not list or len(variants)<2:raise ValueError('multiple immutable variants')
    values=[functional_fingerprint(v['manifest'],v.get('budget'),v.get('source_root')) for v in variants]
    if len({v['sha256'] for v in values})!=1:raise ValueError('functional role/config/outcomes differ')
    return dict(status='MATCH_functional_role_only',functional_sha256=values[0]['sha256'],one_logical_claim_required=True,fresh_budget_admission_conferred=False,variants=values)

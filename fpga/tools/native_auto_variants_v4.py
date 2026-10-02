"""Mechanical serial variants with qualified75 accounting; no queue writes."""
import hashlib
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='5693d9ef9de10658049cb31354d6b3d7ba2bc03fd6fed384a4cae0cbaf7abb3d'


def module():
    raw=(HERE/'native_auto_variants_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:
        raise ValueError('frozen automatic variant preparation')
    text=raw.decode()
    for old,new in [
        ('6fd1904025f4d76557497dba2eac2a5514b419a799c8616b177bc696f051379a','7e9f54325a032fd4b6db88f95dca5f62b1ff9ae431ab58e00b4597a584692496'),
        ('native_azure_variant_refresh_v2.py','native_azure_variant_refresh_v5.py'),
        ('2a4f120415693b65a4f42a504cf890adcde491e123adb30dd7efaeaff7b88c4c','d62511d7a752858ff3e455e973fc87bd1ff33387ed181ba46ff1c2c23973a222'),
        ('native_profile_variants_v3.py','native_profile_variants_v14.py'),
        ('575a31c4a06d44139a406623f939bc38a591edc42304527dab2af5efe6fb4727','8839740fdef8c5ea52df5064aaf3b91ace4568df462f10f3deeadb3e0a87ac97'),
        ('native_class_v2.py','native_class_burst8_v1.py'),
        ('5a3ab8b8306e74de9d6dd9fcbe26ee185a25dff95ac6a5e1b51503ce00e543c3','8c7234c341ad20823520761c429e030f26b8ed4e90cb4b171f3f91f328cfe767'),
        ('tools/native_class_package_v4.py','tools/native_class_package_azure75_v1.py'),
        ('tools/native_package_v6.py','tools/native_stage_azure75_v1.py'),
        ("    if azure:dependencies.insert(0,ROOT/'tools/native_package_v5.py')",''),
        ("matches=[name for name in lane['profiles'] if name in policy.SELECTIONS]",
         "matches=[name for name in lane['profiles'] if name in policy.SELECTIONS and policy.profile(name)['memory_bytes']>=ticket.get('minimum_ram_gib',ticket['resources']['ram_gib'])*(1<<30)]"),
        ("if any(p['profile'] in lane['profiles'] for p in variants):continue",
         "if any(p['profile'] in lane['profiles'] and p.get('resources',ticket['resources'])['ram_gib']>=ticket.get('minimum_ram_gib',ticket['resources']['ram_gib']) for p in variants):continue"),
        ("old=json.loads((template/'manifest.json').read_text());native=json.loads((template/'ticket.json').read_text())",
         "old=json.loads((template/'manifest.json').read_text());native=json.loads((template/'ticket.json').read_text());need('runtime_duration' not in old and 'fixed_execution' not in old and old['probe']['expected_json']==dict(context_threads=1,model_threads=1,expected_threads=1),'special duration/thread/allocation is not serial-convertible')"),
    ]:
        if old not in text:
            raise ValueError('exact75 automatic source anchor: '+old)
        text=text.replace(old,new)
    value=types.ModuleType('_qualified_azure75_auto');value.__file__=str(Path(__file__).resolve())
    # Existing three aethia serial profiles reuse the same immutable packager;
    # local zero-cost accounting is never substituted for a cloud provider.
    text=text.replace("elif host['provider']=='gcp':", "elif host['provider'] in ('gcp','local'):")
    start=text.index("                    quote=load('cloud/host_hours_admit_v1.py')")
    stop=text.index("                    dump(target/'budget.json'",start)
    previous=text[start:stop]
    replacement="                    if host['provider']=='local':\n                        need(host['name']=='aethia','existing local host only')\n                        budget=dict(provider='local',host='aethia',cloud_cost_usd=0)\n                    else:\n"+''.join('    '+line+'\n' for line in previous.splitlines())
    text=text[:start]+replacement+text[stop:]
    exec(compile(text,'[mechanical user75 serial variants]','exec'),value.__dict__)
    return value


def expand_variants(*args,**kwargs):
    return module().expand_variants(*args,**kwargs)

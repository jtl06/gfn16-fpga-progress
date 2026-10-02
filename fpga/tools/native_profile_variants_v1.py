"""Exact shared-control exclusions for dual static profile functional identity.

No directory-wide exclusions. Unknown or changed helpers remain functional
inputs, and compiled/validator/asset files can never be excluded.
"""
import hashlib
import json
from pathlib import PurePosixPath
import re

KNOWN_CONTROLS = {
  "cloud/aethia-native-thread-profiles-v2.json": "837b27f292704ce8f46d03d37bed9b520aedc02da33a9b389b12588a71c5c916",
  "cloud/azure-f32-static-profiles-v1.json": "7919c768a8f39cbf98fdaf687ee562ef152a4de922b0abe7ce10de44972c88a2",
  "cloud/azure-native-static-profiles-v1.json": "c6d0dd6cc08f305492f7569eb0dfd08a855e1c75373917c3c971efae8fc871eb",
  "cloud/azure-protected-admission-earlier-v1.json": "c2913b1c3c24e85cacbe46fe4de6c6935d5acbcb819a8867e96453d16ed1b6c0",
  "cloud/gcp-native-thread-profiles-v1.json": "c91d5c5519c9ef5c14aa1d1c014f2f4f0152170f77404cfd63dbabf4b5035fa5",
  "results/throughput-20260929/azure-sim-f32-admission-v1/toolchain-terminal-v1.json": "07a3b872a4446a617bcd29f6d6ef96666c4df207f00d54c2c1d4fecde0ac54e2",
  "results/throughput-20260929/azure-simulation-setup-v6/toolchain-observation-v1.json": "f837ea7803e820e22ee08bf5bf9ff3e166924745737c7c595278f1cd5fe4b01b",
  "tools/build_identity_v1.py": "b0e1ab77c0fc06a6b0cc958061394dad1f990aa52eb1e76d96922c25225788a2",
  "tools/native_class_package_v1.py": "61ae733fbd269a040aa73f02cf1d86810216fba24b57dc9ab4d8aade896a4932",
  "tools/native_class_package_v2.py": "03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604",
  "tools/native_class_package_v3.py": "a8c42095d5d174b6bc622eb10774a0a581e6060b8366d981afabc39084ddcfdd",
  "tools/native_class_v1.py": "1a50703e0554575e323697a11d5bbf43778603f78b1c978406734d7678529516",
  "tools/native_class_v2.py": "5a3ab8b8306e74de9d6dd9fcbe26ee185a25dff95ac6a5e1b51503ce00e543c3",
  "tools/native_lint_classes_v1.py": "0f9b3cfd9a2723a8fb10f4b30614da253e04e3eab52e220241403fec8908d031",
  "tools/native_package_v1.py": "1ae024a4efe23410758f6cd17507dc1941d809803c539ee84bb2565f069a0219",
  "tools/native_runtime_toolchain_v1.py": "1556444c29fa2ae2e891cced55220ac81d11dd9fa51294db75571d5eb5f8bd5b",
  "tools/native_shared_v1.py": "7bae7c05f7a3a5a83c55f9eb4f9dc33476b3051841661da8a45627d20424e10b",
  "tools/native_source_gate_aethia_cpu02_v2.py": "452f9bfdebc535d39c1e493b61378de50720088788698435fd6d11974eb670b3",
  "tools/native_static_package_v1.py": "92f87083f3b70a3d64110d18ac3ff89af0783c2c4d15ab7ed65bfd2b4f217693",
  "tools/native_static_v1.py": "5b1b0f0dc584df8d6887235a9ddf1610f4956823aa84131438de7b8054f1e0ab",
  "tools/native_static_v2.py": "6bfe9e244e50da02f9d3b3b1f47b0b7273158fc0b640c4311352a818b1705f6f",
  "tools/native_static_v3.py": "3fcd90e5a92ec332f350aa3be31eab16f106666cae42275cc2cce625960e0ac9",
  "tools/native_test_queue_v1.py": "f76fd5b98a7a390a8573fbab87e6721ba5d631cddcc7ef7fbd3967b03f8f4fab",
  "tools/native_user_quota_v1.py": "a55c3192c85b272dad59acc5d4b782b69f78e927e2f559106534b27ba6aab3c3",
  "tools/native_user_quota_v2.py": "1a628027f1f083866cd3ddb7246c2da27523623d05a5fd107b43271bdefccfe3",
  "tools/snapshot_native_sources_v2.py": "db9786b52e0bb53545aa9a800f45dc00beec6663346cfa77f3ec2d0b1c6c5f83"
}


def need(ok,why):
    if not ok:raise ValueError(why)


def functional_fingerprint(manifest):
    need(type(manifest) is dict and manifest.get('schema')=='native-source-gate-v1','source manifest')
    sources=manifest['sources'];build=manifest['build'];probe=manifest['probe'];steps=manifest['steps']
    need(type(sources) is dict and sources,'closed source map')
    mandatory=set(build['sv_sources'])|{build['cpp_source']}
    for step in steps:
        if 'validator' in step:
            mandatory.add(step['validator']['source'])
            mandatory.update(step['validator']['assets'].values())
    need(mandatory<=set(sources),'compiled/validator/asset closure')
    for name,pin in sources.items():
        path=PurePosixPath(name)
        need(type(name) is str and str(path)==name and not path.is_absolute() and '..' not in path.parts,'safe source name')
        need(type(pin) is str and re.fullmatch('[0-9a-f]{64}',pin),'source SHA256')
    retained={name:pin for name,pin in sources.items() if name in mandatory or KNOWN_CONTROLS.get(name)!=pin}
    ignored={name:pin for name,pin in sources.items() if name not in retained}
    # Preserve the complete ordered build/config/probe/outcome contract and all
    # non-framework role, lineage, reference, vector, and design sources.
    identity=dict(schema='native-functional-variant-v1',sources=retained,build=build,probe=probe,steps=steps)
    encoded=json.dumps(identity,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return dict(sha256=hashlib.sha256(encoded).hexdigest(),identity=identity,ignored_exact_controls=ignored)


def match_variants(manifests):
    need(type(manifests) is list and len(manifests)==2,'exact dual static variants')
    need({m['cpu_profile'] for m in manifests}=={'gcp-c4d-static01-v1','gcp-c4d-static23-v1'},'both distinct GCP static profiles')
    need(all(m['host']=='gfn16-pilot-c4d' and m.get('phase')=='run' for m in manifests),'same GCP native run scope')
    values=[functional_fingerprint(m) for m in manifests]
    need(values[0]['sha256']==values[1]['sha256'],'dual variants differ in functional source/config/outcomes')
    return dict(status='MATCH_functional_role_only',functional_sha256=values[0]['sha256'],
                profiles=[m['cpu_profile'] for m in manifests],one_logical_claim_required=True,
                identity=values[0]['identity'],ignored_exact_controls=[v['ignored_exact_controls'] for v in values])

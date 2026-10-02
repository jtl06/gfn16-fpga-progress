"""Source-preserving Azure variant preparation/refresh before native claiming.

No provider calls, remote writes, lifecycle actions or dispatch. The caller
supplies a freshly captured, pinned provider JSON and a fresh native job ID.
An existing claimed native job must never be retried through this helper.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
PACKAGE_SHA='a8c42095d5d174b6bc622eb10774a0a581e6060b8366d981afabc39084ddcfdd'
VARIANTS_SHA='064b9948606f1b008de2cb73a63a250ed0029f50ab3b2713483941bebf2f7d5e'

def need(ok,why):
    if not ok:raise ValueError(why)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(name,pin):
    path=HERE/name;need(sha(path)==pin,'exact Azure refresh dependency')
    spec=importlib.util.spec_from_file_location('_refresh_'+path.stem,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def dump(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')

def repackage_variant(existing_package_dir,profile_id,new_native_id,provider_path,provider_sha256,output):
    package=load('native_class_package_v3.py',PACKAGE_SHA)
    variants=load('native_profile_variants_v2.py',VARIANTS_SHA)
    existing=Path(existing_package_dir);out=Path(output)
    need(existing.is_absolute() and existing.resolve()==existing and existing.is_dir(),'canonical prepared package root')
    need(out.is_absolute() and out.resolve()==out and not out.exists(),'fresh additive refresh output')
    ticket=json.loads((existing/'ticket.json').read_text());manifest=json.loads((existing/'manifest.json').read_text())
    need(sha(existing/'manifest.json')==ticket['manifest_sha256'],'old manifest/ticket binding')
    need(ticket['schema']=='shared-native-ticket-v1' and manifest['phase']=='run','finite native run template')
    need(new_native_id!=ticket['id'],'fresh native id; never replay original claim')
    need(not (existing/'queue-report.json').exists() and not (existing/'output/native').exists(),'unexecuted local package template only')
    root=existing/'capture/source/fpga'
    original_fingerprint=variants.functional_fingerprint(manifest,ticket.get('budget'),root)
    helper=package.worker({'provider':'local','host':'aethia','cloud_cost_usd':0})
    selected=helper.load('native_class_v2.py').profile(profile_id)
    need(selected['host'] in ('gfn16-azure-f16','gfn16-azure-sim-f32'),'only observed Azure target profiles')
    for name,pin in manifest['sources'].items():
        path=root/name;need(path.resolve()==path and path.is_file() and sha(path)==pin,'unchanged complete source template')
    role=json.loads(json.dumps(manifest));role['sources']=dict(manifest.get('budget_source_members',manifest['sources']))
    role.pop('budget_source_members',None)
    need(all(manifest['sources'].get(name)==pin for name,pin in role['sources'].items()),'original role closure preserved')
    provider=Path(provider_path)
    need(provider.is_absolute() and provider.resolve()==provider and sha(provider)==provider_sha256,'fresh actual provider capture pin')
    provider_relative=str(provider.relative_to(HERE.parent))
    budget=package.meter().make_budget(selected['host'],3715,provider_relative,provider_sha256,
                                     package.source_identity(role),selected['profile_sha256'])
    package.binding(budget,selected,role) # Live budget before any output side effect.
    out.mkdir(parents=True)
    try:
        source=out/'role/fpga';source.mkdir(parents=True)
        for name,pin in role['sources'].items():
            target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,target)
            need(sha(target)==pin,'copy preserves exact role source')
        dump(out/'role-manifest.json',role);dump(out/'budget.json',budget)
        prepared=package.prepare(out/'role-manifest.json',source,profile_id,new_native_id,'run',out/'packet',out/'budget.json')
        new_manifest=json.loads((out/'packet/manifest.json').read_text())
        new_fingerprint=variants.functional_fingerprint(new_manifest,budget,out/'packet/capture/source/fpga')
        need(original_fingerprint['sha256']==new_fingerprint['sha256'],'source/config/outcome preservation across refresh')
        need(all(sha(root/name)==pin for name,pin in manifest['sources'].items()),'template stable during refresh')
        result=dict(prepared,original_manifest_sha256=ticket['manifest_sha256'],
            original_ticket_sha256=sha(existing/'ticket.json'),functional_sha256=new_fingerprint['sha256'],
            new_native_id=new_native_id,profile=profile_id,provider_capture_sha256=provider_sha256,
            old_inputs_preserved=True,logical_claim_required=True)
        result['status']='prepared_refreshed_variant_not_executed'
        dump(out/'refresh-receipt.json',result);return result
    except BaseException as error:
        dump(out/'refresh-failure.json',dict(status='failed_refresh_preserved',error=repr(error)));raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('existing-package-dir','provider-path','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--profile',required=True);parser.add_argument('--id',required=True);parser.add_argument('--provider-sha256',required=True)
    args=parser.parse_args();print(json.dumps(repackage_variant(args.existing_package_dir.resolve(),args.profile,args.id,
        args.provider_path.resolve(),args.provider_sha256,args.output.resolve()),indent=2))

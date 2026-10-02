"""r50 interim automatic static variants; reuses existing finite packagers.

The dispatcher owns queue locks, provider captures, admission and launch. This
helper only prepares immutable missing variants; it never submits or executes.
No dynamic allocation, runtime-policy unification, or changed role contracts.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
PINS={
 'tools/native_azure_variant_refresh_v2.py':'2a4f120415693b65a4f42a504cf890adcde491e123adb30dd7efaeaff7b88c4c',
 'tools/native_profile_variants_v3.py':'575a31c4a06d44139a406623f939bc38a591edc42304527dab2af5efe6fb4727',
 'tools/native_class_package_v2.py':'03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604',
 'tools/native_class_v2.py':'5a3ab8b8306e74de9d6dd9fcbe26ee185a25dff95ac6a5e1b51503ce00e543c3',
 'cloud/host_hours_admit_v1.py':'6fd1904025f4d76557497dba2eac2a5514b419a799c8616b177bc696f051379a'}

def need(ok,why):
    if not ok:raise ValueError(why)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(name):
    path=ROOT/name;need(sha(path)==PINS[name],'exact auto-variant dependency')
    spec=importlib.util.spec_from_file_location('_auto_'+path.stem,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def dump(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
def package_list(ticket):return ticket.get('packages',ticket.get('package_variants',[ticket['package']] if ticket.get('package') else []))

def package_metadata(directory,host,profile,resources):
    ticket=json.loads((directory/'ticket.json').read_text());manifest=json.loads((directory/'manifest.json').read_text())
    azure=host['provider']=='azure';runner='tools/native_class_package_v4.py' if azure else 'tools/native_class_package_v2.py'
    stager=ROOT/('tools/native_package_v6.py' if azure else 'tools/native_package_v4.py')
    dependencies=[ROOT/'tools/native_package_v3.py',ROOT/'tools/native_package_v2.py']
    if azure:dependencies.insert(0,ROOT/'tools/native_package_v5.py')
    return dict(archive=str(directory/'package.tar.gz'),sha256=sha(directory/'package.tar.gz'),ticket_sha256=sha(directory/'ticket.json'),
        manifest_sha256=sha(directory/'manifest.json'),worker_id=ticket['id'],profile=profile,native_root=ticket['native_root'],
        runner=runner,runner_sha256=manifest['sources'][runner],stager=str(stager),stager_sha256=sha(stager),
        stager_dependencies=[dict(path=str(path),sha256=sha(path)) for path in dependencies],max_seconds=3700,
        tool_identity=host['tool_identity'],resources=resources,refreshable=azure)

def expand_variants(ticket,hosts,output,provider_capture_ref=None,*,provider_path=None,provider_sha256=None):
    """Return an enriched logical ticket; caller atomically installs it once.

    hosts are already-loaded dispatcher host descriptors including lanes and
    exact L3 receipts. Azure provider capture is fresh immutable input supplied
    by code, not an owner approval turn. Unsupported hosts become explicit
    notes without removing existing eligible variants.
    """
    if provider_capture_ref is not None:
        need(type(provider_capture_ref) is dict and set(provider_capture_ref)=={'path','sha256'} and provider_path is None and provider_sha256 is None,'one exact provider capture reference')
        provider_path=Path(provider_capture_ref['path']);provider_sha256=provider_capture_ref['sha256']
    original=copy.deepcopy(ticket);variants=copy.deepcopy(package_list(ticket));need(variants,'one existing immutable role variant')
    out=Path(output);need(out.is_absolute() and out.resolve()==out and not out.exists(),'fresh automatic variant output')
    template=Path(variants[0]['archive']).parent
    need(sha(variants[0]['archive'])==variants[0]['sha256'] and sha(template/'ticket.json')==variants[0]['ticket_sha256'],'immutable template package')
    old=json.loads((template/'manifest.json').read_text());native=json.loads((template/'ticket.json').read_text())
    need(sha(template/'manifest.json')==native['manifest_sha256'],'template manifest pin')
    checker=load('tools/native_profile_variants_v3.py')
    expected=checker.functional_fingerprint(old,native.get('budget'),template/'capture/source/fpga')['sha256']
    policy=load('tools/native_class_v2.py')
    eligible=[];notes=[]
    for host in hosts:
        if host.get('enabled') is not True or host.get('admission',{}).get('level')!='L3':continue
        proof=ROOT/host['admission']['reference_receipt'];need(sha(proof)==host['admission']['reference_receipt_sha256'],'actual L3 proof identity')
        for lane in host['lanes']:
            if any(p['profile'] in lane['profiles'] for p in variants):continue
            matches=[name for name in lane['profiles'] if name in policy.SELECTIONS]
            if not matches:notes.append(dict(host=host['name'],lane=lane['id'],reason='no current qualified static profile'));continue
            name=matches[0];selected=policy.profile(name)
            need(selected['host']==host['name'],'host/profile binding')
            required=ticket.get('minimum_ram_gib',ticket['resources']['ram_gib'])
            if required>selected['memory_bytes']/(1<<30):
                notes.append(dict(host=host['name'],lane=lane['id'],reason='declared minimum RAM exceeds profile cap'));continue
            if host['provider']=='azure' and (provider_path is None or provider_sha256 is None):
                notes.append(dict(host=host['name'],lane=lane['id'],reason='fresh source-bound provider capture required'));continue
            eligible.append((host,lane,name,selected))
    out.mkdir(parents=True)
    try:
        for index,(host,lane,name,selected) in enumerate(eligible):
            token=hashlib.sha256((ticket['id']+'|'+name+'|'+str(out)).encode()).hexdigest()[:16]
            worker_id='auto-'+ticket['id'][:35]+'-'+token
            target=out/(str(index)+'-'+name)
            try:
                if host['provider']=='azure':
                    load('tools/native_azure_variant_refresh_v2.py').repackage_variant(template,name,worker_id,Path(provider_path),provider_sha256,target)
                    directory=target/'packet'
                elif host['provider']=='gcp':
                    target.mkdir();source=target/'role/fpga';source.mkdir(parents=True)
                    role=copy.deepcopy(old);role['sources']=dict(old.get('budget_source_members',old['sources']));role.pop('budget_source_members',None)
                    for relative,pin in role['sources'].items():
                        src=template/'capture/source/fpga'/relative;need(sha(src)==pin,'exact role source')
                        dst=source/relative;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
                    dump(target/'role-manifest.json',role)
                    quote=load('cloud/host_hours_admit_v1.py').admit('gcp-c4d',3715);dump(target/'host-hours.json',quote)
                    budget=dict(provider='gcp',observed_at=quote['observed_at_utc'],total_allowance_usd=100,
                        planning_usd_per_hour=quote['hourly_rate_usd'],remaining_after_reserves_usd=quote['remaining_total_after_storage_usd'],
                        actual_billing=False,source_receipt_sha256=sha(target/'host-hours.json'))
                    dump(target/'budget.json',budget);directory=target/'packet'
                    load('tools/native_class_package_v2.py').prepare(target/'role-manifest.json',source,name,worker_id,'run',directory,target/'budget.json')
                else:raise ValueError('unsupported provider, no borrowed accounting')
                new=json.loads((directory/'manifest.json').read_text());nt=json.loads((directory/'ticket.json').read_text())
                need(checker.functional_fingerprint(new,nt['budget'],directory/'capture/source/fpga')['sha256']==expected,'functional role preserved')
                resources=dict(ticket['resources'],cores=2,threads=1,ram_gib=selected['memory_bytes']/(1<<30),scratch_gib=selected['scratch_reservation_bytes']/(1<<30))
                variants.append(package_metadata(directory,host,name,resources))
            except (ValueError,KeyError,OSError) as error:
                notes.append(dict(host=host['name'],lane=lane['id'],reason=str(error),failed_output_preserved=str(target)))
        result=copy.deepcopy(ticket);result.pop('package',None);result.pop('package_variants',None);result['packages']=variants
        receipt=dict(status='automatic_variants_prepared_not_submitted',logical_id=ticket['id'],functional_sha256=expected,
            original_variants=len(package_list(original)),prepared_variants=len(variants),notes=notes,one_logical_claim_required=True)
        dump(out/'ticket.json',result);dump(out/'variants-receipt.json',receipt)
        need(ticket==original,'caller logical ticket not mutated')
        return result,receipt
    except BaseException as error:
        dump(out/'failure.json',dict(status='auto_variants_failure_preserved',error=repr(error)));raise

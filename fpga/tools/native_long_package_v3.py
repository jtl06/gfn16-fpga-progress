"""Strict finite long package bound to the namespace-correct runtime successor."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import types
import tempfile

HERE = Path(__file__).resolve().parent
PARENT_SHA = '1e68060c89b8a013b42e87bb11ced3443b42dc74872e6f2dcbc3b3e39ecc7d06'
EXECUTOR_SHA = '0c0cfe425bf4b6b67ea35954b3d5fef7f43059ee7718ce25f4cd862728aa0ea5'


def module():
    raw = (HERE / 'native_long_package_v2.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError('frozen strict long package')
    text = raw.decode().replace('native_long_package_v2.py', 'native_long_package_v3.py')
    anchor = "    result = types.ModuleType('_strict_long_package'); result.__file__ = str(Path(__file__).resolve())"
    if text.count(anchor) != 1: raise ValueError('unique long runtime package anchor')
    text = text.replace(anchor,
        "    text = text.replace('native_long_class_v1.py','native_long_class_v2.py').replace('ed9c3bbc8796862effc9409beff9a440cb2d13cd4b4cb55f822925ab5ecf1c4f','" + EXECUTOR_SHA + "')\n" + anchor, 1)
    result = types.ModuleType('_long_namespace_package'); result.__file__ = str(Path(__file__).resolve())
    exec(compile(text, '[strict long namespace binding]', 'exec'), result.__dict__)
    return result


base = module()
long_budget_check = base.long_budget_check
runtime=base.base.load('native_long_class_v2.py',EXECUTOR_SHA)
duration = runtime.duration
base.base.duration=duration
prior_long_source=base.base.long_source
def long_source(text):
    text=prior_long_source(text)
    anchor='m=json.loads(json.dumps(original));m.update('
    if text.count(anchor)!=1:raise ValueError('one original role-source anchor')
    text=text.replace(anchor,"m=json.loads(json.dumps(original));m['budget_source_members']=dict(original['sources']);m.update(",1)
    anchor='max_seconds=10800,runtime_duration=duration_policy.SHAPE,'
    if text.count(anchor)!=1:raise ValueError('one immutable long ticket allocation anchor')
    text=text.replace(anchor,anchor+"**({'placement':profile['fixed_placement'],'fixed_execution':original['fixed_execution']} if 'fixed_placement' in profile else {}),",1)
    changes=[('profile=shared.profile(profile_id);budget_binding(budget,profile)',
              'profile=shared.selected_for(original,shared.profile(profile_id));budget_binding(budget,profile)'),
             ("profile=shared.profile(ticket['profile']);budget_binding(ticket['budget'],profile)",
              "profile=shared.selected_for(m,shared.profile(ticket['profile']));budget_binding(ticket['budget'],profile)"),
             ("shared.parent(ticket['profile']).check_sources(source,m['sources'])",
              "shared.parent(ticket['profile'],selected=profile).check_sources(source,m['sources'])")]
    for old,new in changes:
        if old not in text:raise ValueError('owned compile allocation package anchor')
        text=text.replace(old,new)
    return text
base.base.long_source=long_source
def bind_role(manifest_path, source_root, evidence_paths, output, host=None):
    """Bind the actual pilot host; the old GCP call signature stays valid."""
    report = json.loads(Path(evidence_paths['pilot_report']).read_text())
    host = report['host'] if host is None else host
    if host not in ('gfn16-pilot-c4d', 'gfn16-azure-sim-f32') or report['host'] != host:
        raise ValueError('exact admitted actual pilot host')
    original = base.bind_role
    constants = original.__code__.co_consts
    if constants.count('gfn16-pilot-c4d') != 1:
        raise ValueError('one frozen binding host constant shared by both checks')
    code = original.__code__.replace(co_consts=tuple(host if x == 'gfn16-pilot-c4d' else x for x in constants))
    manifest=json.loads(Path(manifest_path).read_text())
    policy=runtime.duration_for(runtime.phase.model_threads(manifest['build'],manifest['probe']['expected_json']))
    return types.FunctionType(code,dict(original.__globals__,duration=policy))(manifest_path, source_root, evidence_paths, output)

def source_identity(manifest):
    value={key:manifest[key] for key in ('build','probe','steps')}
    value['sources']=manifest.get('budget_source_members',manifest['sources'])
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def azure_binding(value,host,profile_pin=None,source_pin=None):
    if (value.get('schema')!='azure-host-hours-budget-v5' or value.get('kind')!='azure-host-hours-v5'
        or value.get('provider')!='azure' or value.get('host')!=host or host!='gfn16-azure-sim-f32'
        or type(value.get('max_seconds')) is not int or value['max_seconds']!=10815
        or value.get('checker_sha256')!='9c3d902e3da0969145c4148f06a51ec9ca22a322513068074f7b338cb8ddf137'):
        raise ValueError('exact source-bound serial Azure10815 descriptor')
    for pin in (value.get('source_sha256'), value.get('profile',{}).get('sha256')):
        if type(pin) is not str or len(pin)!=64 or any(x not in '0123456789abcdef' for x in pin):
            raise ValueError('exact source/profile digest')
    if profile_pin is not None and value['profile']['sha256']!=profile_pin:raise ValueError('long profile identity')
    if source_pin is not None and value['source_sha256']!=source_pin:raise ValueError('long role identity')


def worker(budget=None,count=1):
    base.base.duration=runtime.duration_for(count)
    value = base.worker(); value.PINS['native_long_package_v2.py'] = PARENT_SHA
    if count>1:
        # The immutable build key must retain the declared runtime count and
        # actual physical allocation, not the old serial identity facade.
        original_load=value.load
        def load(name):
            value=original_load('build_identity_v2.py' if name=='build_identity_v1.py' else name)
            return runtime.identity_module(value) if name=='build_identity_v1.py' else value
        value.load=load
    if budget and budget.get('provider')=='azure':
        azure_binding(budget,budget['host'])
        path=HERE.parent/'cloud/host_hours_azure_signed_v1.py'
        if hashlib.sha256(path.read_bytes()).hexdigest()!=budget['checker_sha256']:raise ValueError('signed meter source')
        spec=importlib.util.spec_from_file_location('_long_azure_source',path)
        meter=importlib.util.module_from_spec(spec);spec.loader.exec_module(meter)
        value.PINS.update(meter.evidence_pins(budget))
        value.budget_check=lambda descriptor,now=None:azure_binding(descriptor,descriptor['host'])
        value.budget_binding=lambda descriptor,selected:azure_binding(descriptor,selected['host'],selected.get('hardware_profile_sha256',selected['profile_sha256']))
    return value


def prepare(manifest, source_root, profile, job_id, phase, out, budget, compile_workers=None):
    if phase != 'run': raise ValueError('long profile is explicit run only')
    value=json.loads(Path(budget).read_text());m=json.loads(Path(manifest).read_text())
    count=runtime.phase.model_threads(m['build'],m['probe']['expected_json'])
    if value.get('provider')=='azure':azure_binding(value,'gfn16-azure-sim-f32',source_pin=source_identity(json.loads(Path(manifest).read_text())))
    if compile_workers is None:
        return worker(value,count).prepare(manifest, source_root, profile, job_id, phase, out, budget)
    if count==1:
        if type(compile_workers) is not int or compile_workers!=2:raise ValueError('existing two-core serial jobs remain j2')
        return worker(value,count).prepare(manifest, source_root, profile, job_id, phase, out, budget)
    # Assessment validates all pilot/source/forecast bindings before using its
    # compiler measurement. Only the new detached manifest gets the override.
    runtime.duration_for(count).validate(m,Path(source_root),runtime.profile(profile)['host'])
    item=m['runtime_duration']['evidence']['pilot_report']
    report=json.loads((Path(source_root)/item['path']).read_text())
    m['compile_allocation']=runtime.compilation_bound(m,report,compile_workers)
    m['fixed_execution']['runtime_allocation']['compile_workers']=compile_workers
    with tempfile.TemporaryDirectory(prefix='native-long-compile-metadata-') as temporary:
        updated=Path(temporary)/'manifest.json';updated.write_text(json.dumps(m,indent=2)+'\n')
        return worker(value,count).prepare(updated, source_root, profile, job_id, phase, out, budget)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    bind = sub.add_parser('bind')
    for name in ('manifest', 'source-root', 'output', 'forecast', 'pilot-manifest', 'pilot-report', 'pilot-gate'):
        bind.add_argument('--' + name, type=Path, required=True)
    bind.add_argument('--host', choices=['gfn16-pilot-c4d','gfn16-azure-sim-f32'])
    prep = sub.add_parser('prepare')
    for name in ('manifest', 'source-root', 'output', 'budget'): prep.add_argument('--' + name, type=Path, required=True)
    prep.add_argument('--profile', required=True); prep.add_argument('--id', required=True); prep.add_argument('--phase', choices=['run'], required=True)
    prep.add_argument('--compile-workers',type=int,help='Future packet only; bounded by owned physical cores and measured compiler RAM')
    run = sub.add_parser('run'); run.add_argument('--ticket', type=Path, required=True); run.add_argument('--ticket-sha256', required=True)
    args = parser.parse_args()
    if args.command == 'bind':
        result = bind_role(args.manifest, args.source_root, {key:getattr(args,key) for key in duration.EVIDENCE}, args.output, args.host)
    elif args.command == 'prepare':
        result = prepare(args.manifest, args.source_root, args.profile, args.id, args.phase, args.output, args.budget,args.compile_workers)
    else:
        if hashlib.sha256(args.ticket.read_bytes()).hexdigest()!=args.ticket_sha256:raise ValueError('ticket identity before descriptor parsing')
        ticket=json.loads(args.ticket.read_text())
        result = worker(ticket['budget'],ticket['runtime_duration']['model_threads']).run(args.ticket, args.ticket_sha256)
    print(json.dumps(result, indent=2))

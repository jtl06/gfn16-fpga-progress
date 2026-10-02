"""Standing immutable fit tickets, generated settings and frozen safety primitives.

Explicit operator --tick/--loop only; imports/submission never call a worker.
No VM lifecycle. Unknown observations retain exact physical-slot claims.
"""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import time
import types

HERE = Path(__file__).resolve().parent
FPGA = HERE/'fpga' if (HERE/'fpga').is_dir() else HERE.parent
QUEUE_SHA = 'be37f07ee5d725375498c6615a3883efb7c70b128a51be10d664b89261db1bc4'
RUNNER_SHA = '4433cf56b9ac641a19f3db977b8a00063f86c94c04328100514cf70b06cefd36'
END = datetime(2026, 10, 2, 16, tzinfo=timezone.utc)
WRAP_END = datetime(2026, 10, 3, 1, tzinfo=timezone.utc)
COLLECTION_MARGIN_SECONDS = 600
FIELD = dict(kind='field-fit-two-hour-v1', native_timeout_seconds=7200, outer_runtime_seconds=7200,
             timeout_stop_seconds=60, host_hours_horizon_seconds=7260)
SYNTHESIS = dict(kind='synthesis-resource-two-hour-v1', native_timeout_seconds=7200, outer_runtime_seconds=7200,
                timeout_stop_seconds=60, host_hours_horizon_seconds=7260)
PLACEMENT = dict(kind='placement-resource-two-hour-v1', native_timeout_seconds=7200, outer_runtime_seconds=7200,
                timeout_stop_seconds=60, host_hours_horizon_seconds=7260)
P8_FULL = dict(kind='whole-p8-full-three-hour-v1', native_timeout_seconds=10800, outer_runtime_seconds=10920,
               timeout_stop_seconds=60, host_hours_horizon_seconds=10980)
P16_FULL = dict(kind='whole-p16-full-four-hour-v1', native_timeout_seconds=14400, outer_runtime_seconds=14520,
                timeout_stop_seconds=60, host_hours_horizon_seconds=14580)
SYN_HELPER_SHA='60549face0b6f17ef8e39b25ab78c2862c3cbf96b52b6202636a99e73f5b6ceb'
PLACE_HELPER_SHA='f20130944b84609c730fc6ac3c0e5bddb7947377645db40731a4912d9b7e0e06'
SYN_TCL='''# Actual whole-resource synthesis screen only; no fit, STA or assembler.
load_package project
load_package flow
cd [file dirname [file normalize [info script]]]
project_open probe
if {[catch {
    execute_module -tool syn
} failure]} {
    catch {project_close}
    error $failure
}
catch {project_close}
'''
PLACE_TCL=SYN_TCL.replace('# Actual whole-resource synthesis screen only; no fit, STA or assembler.',
    '# Resource placement only: synthesis, plan, place. Never route, finalize, STA or assembler.').replace(
    '    execute_module -tool syn\n','    execute_module -tool syn\n    execute_module -tool fit -args "--plan"\n    execute_module -tool fit -args "--place"\n')


def need(ok, why):
    if not ok:
        raise ValueError(why)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(path, pin=None):
    path = Path(path)
    need(path.is_absolute() and path.resolve() == path and path.is_file() and path.stat().st_nlink == 1,
         'canonical regular source')
    raw = path.read_bytes()
    need(pin is None or digest(raw) == pin, 'source SHA drift')
    return raw


def reference(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=digest(regular(path)))


def read(ref):
    need(type(ref) is dict and set(ref) == {'path', 'sha256'}, 'closed file reference')
    return json.loads(regular(ref['path'], ref['sha256']))


def load(path, pin=None):
    regular(path, pin)
    spec = importlib.util.spec_from_file_location('_standing_'+Path(path).stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen_queue(synthesis=False):
    module = load(HERE/'plain_fit_queue_v6.py', QUEUE_SHA)
    if synthesis:
        source=regular(HERE/'plain_fit_queue_v6.py',QUEUE_SHA).decode()
        source=source.replace("('component_sizing_probe','constraint_seed_only')","('component_sizing_probe','constraint_seed_only','synthesis_only_resource_screen','place_only_resource_probe')")
        module=types.ModuleType('_syn_queue_binding');module.__file__=str(HERE/'plain_fit_queue_v6.py')
        exec(compile(source,'plain_fit_queue_v6.py[syn-only]','exec'),module.__dict__)
    module.FPGA = FPGA
    return module


def aws12_config(config):
    """One whole-host allocation on the existing twelve physical cores."""
    value=deepcopy(config)
    value.update(workers=12,memory=40<<30)
    value['slots']['a']=list(range(12))
    return value


def aws12_runner_source(source):
    for old,new in (("if config['workers']==6:","if config['workers']==12:"),
                    ('"manifest[\'compile_processors\']==6"','"manifest[\'compile_processors\']==12"'),
                    ('"assignment(\'NUM_PARALLEL_PROCESSORS\')==[\'6\']"','"assignment(\'NUM_PARALLEL_PROCESSORS\')==[\'12\']"')):
        need(source.count(old)==1,'exact whole-host worker adaptation')
        source=source.replace(old,new)
    return source


def aws12_runner(module):
    adapted=types.ModuleType('_standing_aws12_runner');adapted.__file__=module.__file__
    exec(compile(aws12_runner_source(regular(Path(module.__file__).resolve()).decode()),'plain_fit_v5.py[aws12]', 'exec'),adapted.__dict__)
    adapted.HOSTS['gfn16-aws-m8i']=aws12_config(adapted.HOSTS['gfn16-aws-m8i'])
    return adapted


def synthesis_summary(project):
    """Reuse the frozen synthesis report parser, never its legacy launcher."""
    helper=load(HERE/'aws_syn_v1.py' if (HERE/'aws_syn_v1.py').exists() else FPGA/'cloud/aws_syn_v1.py',SYN_HELPER_SHA)
    try:
        result=helper.summarize_synthesis(project)
        code=0 if result['synthesis_success'] else 2
    except (ValueError,OSError) as error:
        result=dict(status='synthesis_only_failed',error=str(error));code=2
    save(project.parent/(project.name+'-summary.json'),result)
    return types.SimpleNamespace(returncode=code,resources=result)


def placement_resources(project):
    helper=load(HERE/'staged_fit.py' if (HERE/'staged_fit.py').exists() else FPGA/'synthesis/staged_fit.py',PLACE_HELPER_SHA)
    result=helper.parse_reports(project)
    outputs=Path(project)/'output_files'
    need(not any(outputs.glob('probe.fit.route*')) and not any(outputs.glob('probe.fit.finalize*'))
         and not any(outputs.glob('probe.sta*')),'place-only forbids route/finalize/STA evidence')
    report=(outputs/'probe.fit.place.rpt').read_text() if (outputs/'probe.fit.place.rpt').exists() else ''
    result.update(status='placement_resources_only',placement_success=bool(result['place_report_observed']
        and 'Info (170137): Fitter placement was successful' in report
        and all(result['metrics'].get(k) is not None for k in ('alms_needed_packing_adjusted','alms_placed_raw','labs_used','labs_available'))),
        routed=False,timing_closure=False,promotion_allowed=False)
    return result


def placement_summary(project):
    try:
        result=placement_resources(project);code=0 if result['placement_success'] else 2
    except (ValueError,OSError) as error:
        result=dict(status='placement_only_failed',error=str(error),routed=False);code=2
    save(project.parent/(project.name+'-summary.json'),result)
    return types.SimpleNamespace(returncode=code,resources=result)


def synthesis_module(module,mode='synthesis_only'):
    """Narrow in-memory syn-only binding over unchanged physical guards."""
    need(mode in ('synthesis_only','place_only'),'finite stopped-stage mode')
    stages=['syn'] if mode=='synthesis_only' else ['syn','plan','place']
    original_read=module.regular
    def source(path,pin=None):
        raw=original_read(path,pin)
        if Path(path).name=='aws_fit_v6.py':
            text=raw.decode()
            old="manifest.get('allowed_stages')==['syn','fit','sta']"
            need(text.count(old)==1,'one stage policy anchor')
            text=text.replace(old,"manifest.get('allowed_stages')=="+repr(stages))
            start=text.index("        summary=subprocess.run(")
            stop=text.index("        with (project/'execution-result.json')",start)
            text=text[:start]+"        summary=STANDING_SYN_SUMMARY(project)\n"+text[stop:]
            text=text.replace("mode='physical'","mode="+repr(mode))
            text=text.replace("summarize_returncode=summary.returncode,context_sha256=",
                              "summarize_returncode=summary.returncode,mode="+repr(mode)+","+('resource_estimates' if mode=='synthesis_only' else 'placement_resources')+"=summary.resources,context_sha256=")
            text=text.replace('Placement/source evidence, not FPGA throughput or spending authorization.',
                              'Synthesis estimates only; no fit, STA, physical GO or promotion.' if mode=='synthesis_only' else 'Placement resources only; no route, STA, clock or promotion.')
            text=text.replace("str(project/'run.tcl'),'fit'","str(project/'run.tcl'),"+repr('syn' if mode=='synthesis_only' else 'place'))
            raw=text.encode()
        return raw
    module.regular=source
    original_runner=module.runner
    def runner(*args):
        result=original_runner(*args)
        result.STANDING_SYN_SUMMARY=synthesis_summary if mode=='synthesis_only' else placement_summary
        return result
    module.runner=runner
    module.FULL_TCL=SYN_TCL if mode=='synthesis_only' else PLACE_TCL
    return module


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False)+'\n')
        stream.flush()
        os.fsync(stream.fileno())


def paused():
    return (FPGA/'docs/briefs/PAUSE').exists()


def settings(period, seed, workers='auto', optimization_mode=None):
    need(type(period) in (str, int, float) and type(period) is not bool, 'literal period')
    period = Decimal(str(period))
    need(period.is_finite() and 1 <= period <= 100 and period*1000 == int(period*1000), 'period at exact ps resolution')
    need(type(seed) is int and 1 <= seed <= 2147483647, 'finite integer seed')
    need(workers == 'auto' or type(workers) is int and workers in (4, 6, 12), 'fixed physical worker shape')
    need(optimization_mode in (None,'High Performance Effort','Aggressive Area'),'supported explicit optimization mode')
    value=dict(period_ns=format(period, '.3f'), seed=seed, workers=workers, retain_snapshots=True)
    if optimization_mode is not None:value['optimization_mode']=optimization_mode
    return value


def profiles(ref):
    value = read(ref)
    need(set(value) == {'schema', 'shapes', 'non_fit_roles'} and value['schema'] == 'fit-host-profiles-v1', 'closed fit profiles')
    q = frozen_queue()
    need(set(value['shapes']) == {'azure4', 'aws6'} and value['non_fit_roles'] == ['gcp-c4d', 'azure-burst16'], 'existing fit roles only')
    for shape, config in value['shapes'].items():
        need(config['host'] in q.HOSTS and {k:v for k,v in config.items() if k != 'host'} == q.HOSTS[config['host']],
             'profile matches frozen physical/CPU/RAM/deadline contract')
    return value


def budget(ref):
    need(Path(ref['path']).is_relative_to(FPGA), 'owned policy path')
    module = load(FPGA/'cloud/fit_budget_policy.py')
    relative = dict(path=str(Path(ref['path']).relative_to(FPGA)), sha256=ref['sha256'])
    return module.PolicyBudget(relative, FPGA)


def snapshot(path):
    path = Path(path).resolve()
    need(path.is_relative_to(FPGA) and path.is_dir(), 'owned source design snapshot')
    forbidden = ('qdb', 'db', 'incremental_db', 'output_files', 'execution-context.json', 'execution-result.json')
    need(not any((path/name).exists() for name in forbidden), 'source snapshot only, never a running/completed project')
    files = {str(p.relative_to(path)):digest(regular(p)) for p in path.rglob('*') if p.is_file() or p.is_symlink()}
    need(files and len(files) <= 10000 and sum(p.stat().st_size for p in path.rglob('*') if p.is_file()) <= 128 << 20, 'bounded source snapshot')
    manifest = json.loads(regular(path/'manifest.json'))
    q = frozen_queue()
    host = next((h for h,c in q.HOSTS.items() if c['workers'] == manifest.get('compile_processors')), None)
    need(host is not None, 'source workers match an existing admitted shape')
    runner = q.module('snapshot_runner', 'cloud/plain_fit_v5.py')
    if manifest.get('allowed_stages') == ['syn']:
        need((path/'run.tcl').read_text()==SYN_TCL,'exact synthesis-only Tcl')
        runner=synthesis_module(runner)
    runner.runner(dict(runner.HOSTS[host], root=str(FPGA/'cloud')), host, False).verify_project(path)
    return dict(path=str(path), files=files, source_sha256=manifest['source_sha256'])


def validate_ticket(ticket, profile_ref):
    keys = {'schema', 'id', 'priority', 'track', 'purpose', 'scope', 'snapshot', 'settings', 'slot_shapes', 'source_contract', 'requires', 'after', 'after_collection_action'}
    need(type(ticket) is dict and keys <= set(ticket) and set(ticket) <= keys|{'mode','native_source_gate','runtime_profile','memory_gib','resource_basis','provisional_geometry'} and ticket['schema'] == 'standing-fit-ticket-v1', 'closed fit ticket')
    mode=ticket.get('mode','full')
    q = frozen_queue()
    need(mode in ('full','synthesis_only','place_only'),'explicit full, synthesis-only or placement-only mode')
    stages=json.loads(regular(Path(ticket['snapshot']['path'])/'manifest.json'))['allowed_stages']
    need(stages in (['syn'],['syn','fit','sta']) if mode=='place_only' else stages==(['syn'] if mode=='synthesis_only' else ['syn','fit','sta']),'ticket/project stage agreement')
    if mode in ('synthesis_only','place_only'):
        need(ticket['after_collection_action'] is None and ticket['native_source_gate'], 'syn-only source-native gate; never clock audit')
        q.name(ticket['native_source_gate'])
    q.name(ticket['id'])
    need(type(ticket['priority']) is int and ticket['scope'] in ('whole_core', 'component_probe'), 'typed scope/priority')
    need(ticket['track'] in ('S', 'A') and ticket['purpose'] in ('whole', 'sizing', 'two_context', 'p16_diet', 'clock_push', 'a10_pending'), 'explicit finite track/purpose')
    need(settings(ticket['settings']['period_ns'], ticket['settings']['seed'], ticket['settings']['workers'],ticket['settings'].get('optimization_mode')) == ticket['settings'], 'closed supported settings')
    configs = profiles(profile_ref)['shapes']
    need(ticket['slot_shapes'] and set(ticket['slot_shapes']) <= set(configs), 'fixed allowed slot shapes')
    for shape, slots in ticket['slot_shapes'].items():
        config = configs[shape]
        need(type(slots) is list and slots and len(slots) == len(set(slots)) and all(s in config['slots'] for s in slots), 'fixed unique allowed slots')
        whole_host=ticket.get('memory_gib')==40 and shape=='aws6' and slots==['a'] and ticket['settings']['workers']==12
        need(ticket['settings']['workers'] in ('auto', config['workers']) or whole_host, 'requested workers equal reserved physical cores')
    source = ticket['snapshot']
    need(set(source) == {'path', 'files', 'source_sha256'}, 'closed immutable snapshot')
    q.closed_tree(source['path'], source['files'])
    need(snapshot(source['path']) == source, 'exact source snapshot identity')
    contract = ticket['source_contract']
    need(type(contract) is dict and set(contract) in ({'exemption'}, {'structural_spec'}), 'one source contract')
    if 'exemption' in contract:
        need(contract['exemption'] in ('constraint_seed_only', 'component_sizing_probe','synthesis_only_resource_screen','place_only_resource_probe'), 'explicit source exemption')
        need((contract['exemption']=='synthesis_only_resource_screen') == (mode=='synthesis_only'),'synthesis screen exemption never full fit')
        need((contract['exemption']=='place_only_resource_probe') == (mode=='place_only'),'placement screen exemption never full fit')
        need(contract['exemption'] != 'component_sizing_probe' or ticket['scope'] == 'component_probe', 'field exemption never whole')
    else:
        read(contract['structural_spec'])
    runtime_contract(ticket)
    if ticket.get('provisional_geometry') is not None:
        need(runtime_contract(ticket)==P16_FULL and set(ticket['slot_shapes'])=={'azure4'}
             and ticket.get('memory_gib')==32,'explicit provisional whole-P16 Azure allocation')
        geometry_contract(ticket)
    if ticket.get('memory_gib') is not None:
        need(type(ticket['memory_gib']) is int and ticket['memory_gib'] in (32,40) and runtime_contract(ticket) in (P16_FULL,PLACEMENT)
             and set(ticket['slot_shapes']) <= {'azure4','aws6'},'explicit existing whole-P16 32GiB request')
        if ticket['memory_gib']==40:
            need(runtime_contract(ticket)==P16_FULL and ticket['slot_shapes']=={'aws6':['a']} and ticket['settings']['workers']==12,'AWS whole-host twelve-core40GiB only')
    need(ticket['settings']['workers']!=12 or ticket.get('memory_gib')==40,'twelve workers require whole-host40GiB')
    if mode=='place_only':
        parameters=json.loads(regular(Path(source['path'])/'manifest.json')).get('core_parameters',{})
        need(ticket['scope']=='whole_core' and parameters.get('AW')==16 and parameters.get('P')==16
             and ticket.get('memory_gib')==32 and set(ticket['slot_shapes'])=={'azure4'},'bounded existing Azure32 whole-P16 placement screen')
    if ticket.get('resource_basis') is not None:
        basis=read(ticket['resource_basis'])
        need(basis.get('status')=='CONDITIONAL_TIMING_PLACEMENT_EXPERIMENT' and basis.get('promotion_allowed') is False,'bounded source resource basis, not measured successor GO')
    need(type(ticket['requires']) is list and type(ticket['after']) is list, 'typed prerequisite lists')
    for gate in ticket['requires']:
        need(set(gate) == {'path', 'sha256', 'fields'} and type(gate['fields']) is dict and gate['fields'], 'pinned typed native prerequisite')
    for dependency in ticket['after']:
        need(set(dependency) == {'job', 'outcome'} and dependency['outcome'] in ('native_fit_success', 'native_fit_failure','native_synthesis_success','native_synthesis_failure'), 'typed predecessor')
    action = ticket['after_collection_action']
    need(action is None or type(action) is dict and set(action) == {'kind', 'max_selected'} and action == dict(kind='timing_audit_search', max_selected=8), 'bounded registered post-fit action')
    return ticket


def runtime_contract(ticket):
    selected=ticket.get('runtime_profile')
    if selected is not None:
        contracts={p['kind']:p for p in (P8_FULL,P16_FULL)}
        need(selected in contracts,'supported explicit runtime profile')
        profile=contracts[selected]
        lanes=8 if profile==P8_FULL else 16
        manifest=json.loads(regular(Path(ticket['snapshot']['path'])/'manifest.json'))
        parameters=manifest.get('core_parameters') or {}
        need(ticket.get('mode','full')=='full' and ticket['scope']=='whole_core'
             and ticket['track']=='S' and 'structural_spec' in ticket['source_contract']
             and manifest.get('scope')=='whole_core' and parameters.get('P')==lanes
             and parameters.get('AW')==16 and manifest.get('allowed_stages')==['syn','fit','sta']
             and ticket.get('native_source_gate'),'bounded whole profile requires matching source-gated structural AW16 lane count and full flow')
        return profile
    if ticket.get('mode')=='synthesis_only':return SYNTHESIS
    if ticket.get('mode')=='place_only':return PLACEMENT
    if ticket['source_contract'].get('exemption')=='component_sizing_probe':return FIELD
    return None


def join_native_sources(project_sources, report_sources):
    """Join immutable flattened project names to unambiguous captured RTL paths."""
    matched={}
    for name,pin in project_sources.items():
        need(Path(name).name==name,'flat synthesis source basename')
        paths=[key for key in report_sources if isinstance(key,str) and key.startswith('rtl/')
               and '..' not in Path(key).parts and Path(key).name==name]
        need(len(paths)==1 and report_sources[paths[0]]==pin,
             'every synthesis RTL source matches one unambiguous actual normal report path: '+name)
        matched[name]=paths[0]
    return matched


def geometry_contract(ticket):
    proof=read(ticket['provisional_geometry'])
    need(set(proof)=={'schema','generator','kwargs','native_n','fit_n'}
         and proof['schema']=='fit-provisional-aw8-geometry-v1'
         and type(proof['native_n']) is int and proof['native_n']==256
         and type(proof['fit_n']) is int and proof['fit_n']==65536,'closed provisional AW8-to-AW16 geometry')
    path=Path(proof['generator']['path'])
    need(path.parent==FPGA/'reference' and re.fullmatch(r'[a-z][a-z0-9_]*\.py',path.name),
         'existing pure reference prepare module, not arbitrary callback')
    regular(path,proof['generator']['sha256'])
    kwargs=proof['kwargs']
    need(type(kwargs) is dict and kwargs.get('p')==16 and kwargs.get('contexts')==2
         and 'n' not in kwargs and all(re.fullmatch(r'[a-z][a-z0-9_]*',k) and type(v) in (int,bool) for k,v in kwargs.items()),
         'same literal C2/P16 generator flags; geometry is only changed input')
    return proof


def regenerate_geometries(proof):
    """Pure source generation only, in a fresh process to avoid stale imports."""
    module='fpga.reference.'+Path(proof['generator']['path']).stem
    script='''import hashlib,importlib,json,sys
sys.path.insert(0,sys.argv[1])
prepare=importlib.import_module(sys.argv[2]).prepare
kwargs=json.loads(sys.argv[3]);result=[]
for n in (256,65536):
 b=prepare(n=n,**kwargs)
 result.append(dict(parameters=b['parameters'],top=b['top'],source_sha256=b['source_sha256'],
  files={k:hashlib.sha256(v.encode()).hexdigest() for k,v in b['files'].items()}))
print(json.dumps(result,sort_keys=True))
'''
    result=subprocess.run([sys.executable,'-B','-c',script,str(FPGA.parent),module,json.dumps(proof['kwargs'])],
                          capture_output=True,text=True,timeout=120)
    need(result.returncode==0,'provisional pure source regeneration failed: '+result.stderr[-1500:])
    return json.loads(result.stdout)


def provisional_geometry_join(ticket,report):
    proof=geometry_contract(ticket)
    def captured(relative,pin):
        need(type(relative) is str and not Path(relative).is_absolute() and '..' not in Path(relative).parts,'closed generator dependency path')
        keys=[k for k in (relative,'lineage/'+relative) if k in report['sources']]
        need(keys and all(report['sources'][k]==pin for k in keys),'generator dependency bound to actual AW8 report: '+relative)
        regular(FPGA/relative,pin)
    captured(str(Path(proof['generator']['path']).relative_to(FPGA)),proof['generator']['sha256'])
    bundles=regenerate_geometries(proof)
    need(type(bundles) is list and len(bundles)==2,'two regenerated geometries')
    for aw,bundle in zip((8,16),bundles):
        need(bundle['parameters'].get('AW')==aw and bundle['parameters'].get('P')==16,'regenerated exact AW/P')
        need(bundle['source_sha256'],'nonempty captured generator closure')
        for relative,pin in bundle['source_sha256'].items():captured(relative,pin)
    small,full=bundles
    need({k:v for k,v in small['parameters'].items() if k!='AW'}=={k:v for k,v in full['parameters'].items() if k!='AW'}
         and small['parameters'].get('CONTEXTS')==2,'identical non-address-width design parameters')
    paths=join_native_sources(small['files'],report['sources'])
    need(full['files']==ticket['snapshot']['source_sha256'],'every fitted RTL byte equals regenerated full geometry')
    manifest=json.loads(regular(Path(ticket['snapshot']['path'])/'manifest.json'))
    need(manifest['top']==full['top'] and manifest['core_parameters']==full['parameters'],'full generated top/parameters match frozen project')
    return dict(derivation=ticket['provisional_geometry'],qualification_scope='provisional_AW8_normal_only_full_size_pending',
                actual_native_n=256,fitted_n=65536,full_size_native_pass=False,promotion_allowed=False,
                native_source_paths=paths,native_generated_sha256=small['files'],full_generated_sha256=full['files'],
                generator_source_sha256=full['source_sha256'])


def native_source_gate(ticket):
    identifier=ticket.get('native_source_gate')
    if not identifier:return None
    directory=FPGA/'queue/evidence'/identifier
    gate_path=directory/'gate-receipt.json'
    if not gate_path.exists():return None
    gate=read(reference(gate_path))
    need(gate.get('schema')=='gfn16-native-gate-receipt-v1' and gate.get('id')==identifier
         and gate.get('status')=='PASS_expected_contracts','actual normal gate must PASS')
    reports=list(directory.glob('attempt-*/collected/output/native/*report.json'))
    matched=[p for p in reports if digest(regular(p))==gate['report_sha256']]
    need(len(matched)==1,'one actual gate-bound native report')
    report=read(reference(matched[0]))
    if ticket.get('provisional_geometry') is not None:
        return dict(gate=reference(gate_path),report=reference(matched[0]),source_sha256=ticket['snapshot']['source_sha256'],
                    provisional_geometry=provisional_geometry_join(ticket,report))
    paths=join_native_sources(ticket['snapshot']['source_sha256'],report['sources'])
    return dict(gate=reference(gate_path),report=reference(matched[0]),source_sha256=ticket['snapshot']['source_sha256'],source_paths=paths)


def design_lanes(record):
    if 'ticket' in record:
        ticket=read(record['ticket'])
        manifest=json.loads(regular(Path(ticket['snapshot']['path'])/'manifest.json'))
        return ((manifest.get('core_parameters') or {}).get('P') or (manifest.get('field_parameters') or {}).get('P'))
    parent=record.get('action',{}).get('parent_handle',{})
    return read(parent['request'])['project']['qsf_parameters'].get('P') if parent.get('request') else None


def normalize_parent_qsf(raw, expected_sha256):
    """Remove only the known vendor append, recording both immutable identities."""
    need(digest(raw)==expected_sha256,'parent QSF source identity')
    marker=b'LAST_QUARTUS_VERSION'
    suffix=b'set_global_assignment -name LAST_QUARTUS_VERSION "26.1.0 Pro Edition"\n'
    if marker not in raw:return raw,None
    need(raw.count(marker)==1 and raw.endswith(suffix),'only exact terminal Quartus26.1 metadata append')
    normalized=raw[:-len(suffix)]
    return normalized,dict(original_sha256=expected_sha256,normalized_sha256=digest(normalized),
                           removed_suffix=suffix.decode(),reason='vendor metadata only; no design setting change')


def generate(ticket, destination, workers):
    """Private settings only; source snapshot bytes are never changed."""
    q = frozen_queue()
    source = ticket['snapshot']
    q.closed_tree(source['path'], source['files'])
    shutil.copytree(source['path'], destination)
    destination = Path(destination)
    def replace(text, pattern, replacement):
        matches = re.findall(pattern, text, re.M)
        need(len(matches) == 1, 'one literal generated setting: '+pattern)
        return re.sub(pattern, lambda _:replacement, text, flags=re.M)
    raw_qsf,normalization=normalize_parent_qsf(regular(destination/'probe.qsf'),source['files']['probe.qsf'])
    qsf = raw_qsf.decode()
    qsf = replace(qsf, r'^set_global_assignment -name NUM_PARALLEL_PROCESSORS .+$', 'set_global_assignment -name NUM_PARALLEL_PROCESSORS '+str(workers))
    qsf = replace(qsf, r'^set_global_assignment -name SEED .+$', 'set_global_assignment -name SEED '+str(ticket['settings']['seed']))
    if ticket['settings'].get('optimization_mode'):
        lines=re.findall(r'^set_global_assignment -name OPTIMIZATION_MODE .+$',qsf,re.M)
        need(len(lines)<=1,'unique optimization mode')
        line='set_global_assignment -name OPTIMIZATION_MODE "'+ticket['settings']['optimization_mode']+'"'
        qsf=replace(qsf,r'^set_global_assignment -name OPTIMIZATION_MODE .+$',line) if lines else qsf+line+'\n'
    snapshot_lines = re.findall(r'^set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS .+$', qsf, re.M)
    need(len(snapshot_lines) <= 1, 'unique snapshot retention setting')
    if snapshot_lines:
        qsf = replace(qsf, r'^set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS .+$', 'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS on')
    else:
        qsf += 'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS on\n'
    (destination/'probe.qsf').write_text(qsf)
    sdc = (destination/'probe.sdc').read_text()
    clocks = re.findall(r'^\s*create_clock\b.*$', sdc, re.M)
    need(len(clocks) == 1 and len(re.findall(r'-period\s+[0-9.]+', clocks[0])) == 1 and '-waveform' not in clocks[0], 'one literal clock, no unknown waveform selector')
    sdc = sdc.replace(clocks[0], re.sub(r'-period\s+[0-9.]+', '-period '+ticket['settings']['period_ns'], clocks[0]))
    (destination/'probe.sdc').write_text(sdc)
    (destination/'run.tcl').write_text(PLACE_TCL if ticket.get('mode')=='place_only' else SYN_TCL if ticket.get('mode')=='synthesis_only' else q.module('generated_runner', 'cloud/plain_fit_v5.py').FULL_TCL)
    manifest = json.loads((destination/'manifest.json').read_text())
    need(manifest['source_sha256'] == source['source_sha256'], 'RTL unchanged during settings generation')
    manifest.update(clock_period_ns=float(ticket['settings']['period_ns']), seed=ticket['settings']['seed'], compile_processors=workers)
    if ticket.get('mode')=='place_only':
        manifest['allowed_stages']=['syn','plan','place']
        manifest['native_normal_id']=ticket['native_source_gate']
    manifest['control_sha256'] = {name:digest(regular(destination/name)) for name in ('probe.qsf', 'probe.qpf', 'probe.sdc', 'run.tcl')}
    manifest['standing_settings'] = ticket['settings']
    if normalization:manifest['parent_control_normalization']=normalization
    (destination/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    q.closed_tree(source['path'], source['files'])
    for name,pin in source['source_sha256'].items():
        regular(destination/'rtl'/name, pin)
    return destination


class Journal:
    def __init__(self, directory, queue):
        self.path = Path(directory)/'events.jsonl'
        self.rows = []
        self.identity = digest(canonical(dict(schema='standing-fit-journal-v1', queue=str(queue))))
        # Tools evolve in place (r66); existing journal identity and chain do not.
        legacy = digest(canonical(dict(schema='standing-fit-journal-v1', queue=str(queue), code='51595d8cae4bb4f272208064629bc631384e8bc5f94ca59886c86e68915ee8a7')))
        previous = '0'*64
        if self.path.exists():
            for line in regular(self.path).splitlines():
                row = json.loads(line)
                claimed = row.pop('sha256')
                if not self.rows:
                    need(row['identity'] in (self.identity, legacy), 'standing journal queue identity')
                    self.identity = row['identity']
                need(row['sequence'] == len(self.rows) and row['previous'] == previous and row['identity'] == self.identity and digest(canonical(row)) == claimed, 'standing journal corruption/source drift')
                row['sha256'] = claimed
                self.rows.append(row)
                previous = claimed

    def append(self, event, job, **value):
        row = dict(sequence=len(self.rows), previous=self.rows[-1]['sha256'] if self.rows else '0'*64, identity=self.identity,
                   at_utc=datetime.now(timezone.utc).isoformat(), event=event, job=job, **value)
        row['sha256'] = digest(canonical(row))
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            need(os.fstat(fd).st_nlink == 1, 'canonical standing journal')
            raw = canonical(row)+b'\n'
            need(os.write(fd, raw) == len(raw), 'complete journal append')
            os.fsync(fd)
        finally:
            os.close(fd)
        self.rows.append(row)

    def current(self):
        result = {}
        for row in self.rows:
            key = row['job']
            if row['event'] in ('ticket', 'action'):
                result[key] = dict(row, phase='queued',submitted_ticket=row.get('ticket'))
            elif row['event']=='ticket_amendment':
                need(result[key]['phase']=='queued' and 'handle' not in result[key],'amendment never changes launched work')
                result[key]['ticket']=row['ticket']
            elif row['event'] in ('intent', 'adopt_intent'):
                result[key] = dict(result.get(key, {}), handle=row['handle'], phase=row['event'], prepared=row.get('prepared'))
            elif row['event'] in ('stage_attempt', 'stage_complete', 'launch_attempt', 'started'):
                result[key]['phase'] = row['event']
                result[key]['handle'].update(row.get('handle_delta', {}))
            elif row['event'] == 'terminal':
                result[key].update(phase='terminal', outcome=row['outcome'], bundle=row['bundle'])
            elif row['event'] == 'operator_retry_pre_native':
                result[key]=dict(ticket=result[key]['ticket'],submitted_ticket=result[key].get('submitted_ticket',result[key]['ticket']),phase='queued',execution_id=row['execution_id'])
            elif row['event'] == 'callback_complete':
                result[key]['callback_complete'] = True
            elif row['event']=='audit_callback_configured':
                need(result[key]['phase']=='terminal' and result[key]['outcome']=='native_fit_success','audit callback requires successful collected fit')
                result[key]['handle']['after_collection_action']=dict(kind='timing_audit_search',max_selected=8)
        return result


class SSHBackend:
    def __init__(self, directory, end=END, audits=None):
        self.q = frozen_queue()
        self.fit = self.q.SSHBackend(directory, end)
        self.audits = audits
        original_call = self.fit.call
        def call(host, payload, binary=False):
            # Only native launch entry changes; all fixed caps/resource checks
            # and collector operations are otherwise the frozen implementation.
            if payload['op'] != 'launch' and not (payload['op']=='preflight' and payload.get('memory_bytes')):
                return original_call(host, payload, binary)
            source = regular(HERE/'plain_fit_queue_v6.py', QUEUE_SHA).decode()
            old = "str(helpers/'plain_fit_v5.py'),str(request)"
            need(source.count(old) == 1, 'one native entry anchor')
            source = source.replace(old, "str(helpers/'fit_dispatch.py'),'--worker-run',str(request)")
            request = read(payload['handle']['request']) if payload['op']=='launch' else {}
            memory=request.get('memory_bytes',payload.get('memory_bytes'))
            if memory is not None:
                need(host in ('gfn16-azure-f16','gfn16-aws-m8i') and (memory==32<<30 or host=='gfn16-aws-m8i' and memory==40<<30),'explicit existing native service/preflight allocation')
                source+="\nHOSTS["+repr(host)+"]['memory']="+str(memory)+"\n"
                if memory==40<<30:
                    source+="\nHOSTS['gfn16-aws-m8i']['workers']=12\nHOSTS['gfn16-aws-m8i']['slots']['a']=list(range(12))\n"
            profile=request.get('runtime_contract')
            if profile in (FIELD,SYNTHESIS,PLACEMENT,P8_FULL,P16_FULL):
                source = source.replace("'--property=RuntimeMaxSec=21720'", repr('--property=RuntimeMaxSec='+str(profile['outer_runtime_seconds'])))
            script = 'ns={"__name__":"_standing_remote","__file__":'+repr(str(HERE/'plain_fit_queue_v6.py'))+'}\nexec('+repr(source)+',ns)\nprint(ns["json"].dumps(ns["worker"]('+repr(payload)+'),allow_nan=False))\n'
            result = subprocess.run(self.q.SSH[host]+['/usr/bin/python3 -I -B -'], input=script.encode(), capture_output=True, timeout=self.fit.timeout(240))
            need(result.returncode == 0, 'uncertain native launch: '+result.stderr.decode(errors='replace')[-2000:])
            return json.loads(result.stdout)
        self.fit.call = call

    def preflight(self, host, slot, memory_bytes=None):
        if memory_bytes is not None:
            return self.fit.call(host,dict(op='preflight',host=host,slot=slot,memory_bytes=memory_bytes))
        return self.fit.preflight(host, slot)

    def stage(self, handle, archive):
        return self.audits.stage(handle, archive) if handle.get('kind') == 'audit' else self.fit.stage(handle, archive)

    def launch(self, handle, helpers):
        return self.audits.launch(handle, helpers) if handle.get('kind') == 'audit' else self.fit.launch(handle, helpers)

    def observe(self, handle):
        return self.audits.observe(handle) if handle.get('kind') == 'audit' else self.fit.observe(handle)

    def collect(self, handle):
        return self.audits.collect(handle) if handle.get('kind') == 'audit' else self.fit.collect(handle)

    def verify_terminal(self, handle, bundle):
        if handle.get('kind') == 'audit':
            return self.audits.verify_terminal(handle, bundle)
        request = read(handle['request'])
        if not (Path(bundle['evidence'])/'project/execution-result.json').exists():
            source=regular(HERE/'plain_fit_queue_v6.py',QUEUE_SHA).decode()
            anchor="    need(assessment['findings']==[] and assessment['native_result'] is not None,"
            need(source.count(anchor)==1,'one collected assessment anchor')
            source=source.replace(anchor,"    interrupted=INTERRUPTED_TERMINAL(root,request,proof,assessment)\n    if interrupted: return interrupted\n"+anchor)
            module=types.ModuleType('_pre_native_terminal');module.__file__=str(HERE/'plain_fit_queue_v6.py')
            exec(compile(source,'q6[pre-native-rejection]','exec'),module.__dict__)
            module.FPGA=FPGA;module.INTERRUPTED_TERMINAL=interrupted_terminal
            return module.verify_terminal(handle,bundle)
        profile=request.get('runtime_contract')
        if profile in (FIELD,SYNTHESIS,PLACEMENT,P8_FULL,P16_FULL):
            source = regular(HERE/'plain_fit_queue_v6.py', QUEUE_SHA).decode()
            module = types.ModuleType('_field_terminal')
            module.__file__ = str(HERE/'plain_fit_queue_v6.py')
            exec(compile(source.replace("context['timeout_seconds']==21600", "context['timeout_seconds']=="+str(profile['native_timeout_seconds'])), 'q6[bounded-terminal]', 'exec'), module.__dict__)
            module.FPGA = FPGA
            if request.get('memory_bytes'):module.HOSTS[handle['host']]['memory']=request['memory_bytes']
            if request.get('memory_bytes')==40<<30:module.HOSTS[handle['host']]=aws12_config(module.HOSTS[handle['host']])
            outcome = module.verify_terminal(handle, bundle)
            context = json.loads(regular(Path(bundle['evidence'])/'project/execution-context.json'))
            need(context.get('runtime_kind') == profile['kind'] and context.get('outer_runtime_max_seconds') == profile['outer_runtime_seconds'] and context.get('outer_timeout_stop_seconds') == 60,
                 'actual explicit stage/runtime metadata')
            receipt=read(dict(path=bundle['receipt'],sha256=bundle['receipt_sha256']))
            need(receipt['native_journal_proof']['manager_elapsed_seconds']<=profile['host_hours_horizon_seconds'],'actual bounded stage duration')
        else:
            outcome=self.q.verify_terminal(handle, bundle)
        if request.get('mode')=='synthesis_only':
            project=Path(bundle['evidence'])/'project'
            context=json.loads(regular(project/'execution-context.json'))
            need(context['mode']=='synthesis_only' and (project/'run.tcl').read_text()==SYN_TCL
                 and json.loads(regular(project/'manifest.json'))['allowed_stages']==['syn'],'collected synthesis-only execution contract')
            need(not any((project/'output_files').glob('probe.fit*')) and not any((project/'output_files').glob('probe.sta*')),'no fitter or STA output')
            if outcome=='native_fit_success':
                helper=load(FPGA/'cloud/aws_syn_v1.py',SYN_HELPER_SHA)
                estimates=helper.summarize_synthesis(project)
                result=json.loads(regular(project/'execution-result.json'))
                need(estimates['synthesis_success'] and result.get('mode')=='synthesis_only'
                     and result.get('resource_estimates')==estimates,'actual synthesis estimates in single collected result')
            return 'native_synthesis_success' if outcome=='native_fit_success' else 'native_synthesis_failure'
        if request.get('mode')=='place_only':
            project=Path(bundle['evidence'])/'project'
            context=json.loads(regular(project/'execution-context.json'))
            need(context['mode']=='place_only' and (project/'run.tcl').read_text()==PLACE_TCL
                 and json.loads(regular(project/'manifest.json'))['allowed_stages']==['syn','plan','place'],'collected placement-only stage boundary')
            observations=placement_resources(project)
            result=json.loads(regular(project/'execution-result.json'))
            if outcome=='native_fit_success':
                need(observations['placement_success'] and result.get('mode')=='place_only'
                     and result.get('placement_resources')==observations,'actual placement resources, never routed timing')
            return 'native_placement_success' if outcome=='native_fit_success' else 'native_placement_failure'
        return outcome


def pre_native_rejection(root,request,proof,assessment):
    """Narrow proven preparation defect, never turn unknown vendor work into terminal."""
    expected={'missing_execution-context.json','missing_execution-result.json','missing_plain-final-source-guard.json','missing_database-inventory-final.json'}
    if set(assessment['findings'])!=expected or assessment['native_result'] is not None:return False
    if proof['terminal_kind']!='failed' or proof['manager_elapsed_seconds']>=5:return False
    if request.get('runtime_contract')!=P8_FULL or request['project']['qsf_parameters'].get('P')!=16:return False
    if request['mode']!='full' or request['scope']!='whole_core':return False
    project=root/'project'
    if any((project/'output_files').glob('*')) or any((root/'root').glob('*')):return False
    for prefix,mapping in (('rtl',request['project']['source_sha256']),('',request['project']['control_sha256'])):
        for name,pin in mapping.items():regular(project/prefix/name,pin)
    rows=[json.loads(line) for line in regular(root/'collection/native-journal.jsonl').splitlines()]
    messages=[r.get('MESSAGE','') for r in rows if r.get('_SYSTEMD_INVOCATION_ID')==proof['invocation_id']]
    return any(m=='ValueError: actual source-gated whole runtime lane count' for m in messages)


def interrupted_terminal(root,request,proof,assessment):
    if pre_native_rejection(root,request,proof,assessment):return 'native_prelaunch_failure'
    expected={'missing_execution-result.json','missing_plain-final-source-guard.json','missing_database-inventory-final.json'}
    if set(assessment['findings'])!=expected or assessment['native_result'] is not None:return None
    if proof['terminal_kind']!='failed' or proof['manager_terminal_message']!=request['unit']+": Failed with result 'oom-kill'.":return None
    context=json.loads(regular(root/'project/execution-context.json'));config=dict(frozen_queue().HOSTS[request['host']])
    if request.get('memory_bytes'):config['memory']=request['memory_bytes']
    if request.get('memory_bytes')==40<<30:config=aws12_config(config)
    profile=request.get('runtime_contract');timeout=profile['native_timeout_seconds'] if profile else 21600
    need(context['affinity']==config['slots'][request['slot']] and context['quartus_workers']==config['workers']
         and context['memory_max']==str(config['memory']) and context['swap_max']=='0'
         and context['timeout_seconds']==timeout,'OOM original admitted native resources')
    need(context['cpu_max'].split()[0]==str(config['workers']*int(context['cpu_max'].split()[1])),'OOM original CPU quota')
    need(any(int(r.get('MEMORY_PEAK','0'))>0 and r.get('MEMORY_SWAP_PEAK')=='0' for r in proof['resource_journal']),'actual OOM resource observation')
    # The normal collector has already rechecked every retained source/control
    # against the native context; missing end markers remain explicit failures.
    return 'native_fit_failure'


def native_run(path, pin):
    need(sys.platform == 'linux' and os.geteuid() != 0, 'native worker entry only; never Mac/root')
    request = read(dict(path=str(path), sha256=pin))
    need(request['standing_dispatch_sha256'] == digest(regular(Path(__file__).resolve())), 'native standing entry source')
    profile = request.get('runtime_contract')
    if profile is not None:
        field=profile==FIELD and request['scope']=='component_probe' and request.get('exemption')=='component_sizing_probe' and request['mode']=='full' and 'structural_spec' not in request
        syn=profile==SYNTHESIS and request['mode']=='synthesis_only' and request.get('exemption')=='synthesis_only_resource_screen'
        place=profile==PLACEMENT and request['mode']=='place_only' and request.get('exemption')=='place_only_resource_probe'
        whole=profile in (P8_FULL,P16_FULL) and request['mode']=='full' and request['scope']=='whole_core' and 'structural_spec' in request
        if whole:
            parameters=request['project'].get('qsf_parameters') or {}
            need(parameters.get('P')==(8 if profile==P8_FULL else 16) and parameters.get('AW')==16
                 and request['native_gate_evidence']['source_sha256']==request['project']['source_sha256'], 'actual source-gated whole runtime lane count')
        need(field or syn or place or whole,'explicit bounded field, synthesis, placement or whole runtime')
    horizon = profile['host_hours_horizon_seconds'] if profile else 21780
    module = load(FPGA/'cloud/fit_budget_policy.py', request['budget_policy_helper_sha256'])
    policy = module.PolicyBudget(request['budget_policy'], FPGA)
    source = regular(HERE/'plain_fit_v5.py', RUNNER_SHA).decode()
    synthesis=request.get('mode') in ('synthesis_only','place_only')
    if synthesis:
        need(((profile == SYNTHESIS and request.get('exemption')=='synthesis_only_resource_screen')
              or (profile==PLACEMENT and request.get('exemption')=='place_only_resource_probe'))
             and request['native_gate_evidence']['source_sha256']==request['project']['source_sha256'], 'source-bound whole synthesis-only request')
        source=source.replace("('full','saved_syn')","('full','saved_syn','synthesis_only','place_only')")
        source=source.replace("('constraint_seed_only','component_sizing_probe')","('constraint_seed_only','component_sizing_probe','synthesis_only_resource_screen','place_only_resource_probe')")
    begin = source.index(' meter_path=')
    end = source.index(" need(budget['status']", begin)
    if 'hourly_provider_status' in request:
        source = source[:begin]+" budget=STANDING_BUDGET.launch_status(approved['hourly_provider_status'], 'azure' if host=='gfn16-azure-f16' else 'aws')\n"+source[end:]
    else:
        source = source[:begin]+" budget=STANDING_BUDGET.validate_budget(approved['host_hours_budget'],'gfn16-azure-f16',STANDING_HORIZON,source_sha256=approved['project']['manifest_sha256']) if host=='gfn16-azure-f16' else STANDING_BUDGET.admit('aws-m8azn',STANDING_HORIZON)\n"+source[end:]
    if profile:
        duration='3h 2min' if profile==P8_FULL else '4h 2min' if profile==P16_FULL else '2h'
        for old,new in (('m.TIMEOUT=21600', 'm.TIMEOUT='+str(profile['native_timeout_seconds'])), ("RuntimeMaxUSec='6h 2min'", "RuntimeMaxUSec="+repr(duration)), ('timestamp()+21780<', 'timestamp()+'+str(horizon)+'<')):
            need(source.count(old) == 1, 'one field runtime anchor')
            source = source.replace(old, new)
    if request.get('memory_bytes')==40<<30:source=aws12_runner_source(source)
    native = types.ModuleType('_standing_native_runner')
    native.__file__ = str(Path(__file__).resolve())
    exec(compile(source, 'plain_fit_v5.py[standing-budget-data]', 'exec'), native.__dict__)
    if synthesis:native=synthesis_module(native,request['mode'])
    native.STANDING_BUDGET = policy
    native.STANDING_HORIZON = horizon
    if request.get('memory_bytes') is not None:
        need(request['host'] in ('gfn16-azure-f16','gfn16-aws-m8i') and request['memory_bytes'] in (32<<30,40<<30) and profile in (P16_FULL,PLACEMENT)
             and request['project']['qsf_parameters'].get('P')==16,'native source-bound existing32GiB whole P16')
        if request['memory_bytes']==40<<30:
            need(request['host']=='gfn16-aws-m8i' and request['slot']=='a' and profile==P16_FULL,'native AWS twelve-core whole-only')
            native.HOSTS[request['host']]=aws12_config(native.HOSTS[request['host']])
        need(profile!=PLACEMENT or request['host']=='gfn16-azure-f16','place-only remains Azure32')
        native.HOSTS[request['host']]['memory']=request['memory_bytes']
    if profile:
        base = native.runner
        def field_runner(*args):
            runner = base(*args)
            original = runner.live_limits
            def limits():
                value = original()
                cpuset = (Path(value['cgroup_path'])/'cpuset.cpus.effective').read_text().strip()
                cpus = []
                for part in cpuset.split(','):
                    ends = list(map(int, part.split('-')))
                    cpus.extend(range(ends[0], ends[-1]+1))
                need(sorted(cpus) == sorted(os.sched_getaffinity(0)), 'field effective cpuset confinement')
                return dict(value, runtime_kind=profile['kind'], outer_runtime_max_seconds=profile['outer_runtime_seconds'], outer_timeout_stop_seconds=60, allowed_cpus=sorted(cpus))
            runner.live_limits = limits
            return runner
        native.runner = field_runner
    return native.launch(Path(path), pin)


class Controller:
    def __init__(self, queue, directory, policy_ref, profile_ref, backend, prepare=None):
        self.queue = Path(queue).resolve()
        self.directory = Path(directory).resolve()
        need(self.queue.is_relative_to(FPGA) and self.directory.is_relative_to(FPGA), 'owned standing queue/state')
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.queue/'tickets').mkdir(parents=True, exist_ok=True)
        self.policy_ref, self.profile_ref = policy_ref, profile_ref
        self.money = budget(policy_ref)
        self.configs = profiles(profile_ref)['shapes']
        self.end = datetime.fromisoformat(self.money.policy['until_utc'].replace('Z', '+00:00'))
        self.backend = backend
        self.prepare = prepare or self.prepare_fit
        self.journal = Journal(self.directory, self.queue)

    def retry_pre_native(self,key):
        record=self.journal.current()[key]
        need(record['phase']=='terminal' and record['outcome']=='native_prelaunch_failure','only proven pre-vendor failure may be explicitly retried')
        need(self.backend.verify_terminal(record['handle'],record['bundle'])=='native_prelaunch_failure','replayed original pre-native rejection')
        count=sum(r['event']=='operator_retry_pre_native' and r['job']==key for r in self.journal.rows)+1
        execution_id=key+'-retry'+str(count);self.backend.q.name(execution_id)
        self.journal.append('operator_retry_pre_native',key,execution_id=execution_id,previous_bundle=record['bundle'],previous_handle=record['handle'])

    def amend_pending(self,key,changes):
        record=self.journal.current()[key]
        need(record['phase']=='queued' and 'handle' not in record,'only unstarted unclaimed ticket amendment')
        need(set(changes)<= {'slot_shapes','memory_gib','resource_basis','requires'},'only explicit resource/prerequisite amendment')
        old=read(record['ticket']);ticket=dict(old,**changes);validate_ticket(ticket,self.profile_ref)
        path=self.queue/'amendments'/(key+'-'+digest(canonical(ticket))[:16]+'.json')
        if not path.exists():save(path,ticket)
        need(read(reference(path))==ticket,'immutable amendment')
        self.journal.append('ticket_amendment',key,ticket=reference(path),previous_ticket=record['ticket'],changed_fields=sorted(changes))
        return reference(path)

    def configure_collected_audit(self,key,initial_period_ns):
        record=self.journal.current()[key];audits=self.backend.audits
        need(record['phase']=='terminal' and record['outcome']=='native_fit_success' and audits is not None,'successful fit and qualified audit backend')
        need(not record.get('callback_complete') and not record['handle'].get('after_collection_action'),'new requested callback; never duplicate existing search')
        audits.search.ps(initial_period_ns)
        action=audits.next(record['handle'],record['bundle'],[])
        need(action and action['kind']=='audit' and action['id'] not in self.journal.current(),'fresh same-layout audit sequence')
        action.update(parent_id=key,selected_period_ns=initial_period_ns,selection_reason='Explicit requested frequency test; original routed clock baseline retained')
        self.journal.append('audit_callback_configured',key,initial_period_ns=initial_period_ns)
        self.journal.append('action',action['id'],action=action)
        return action

    def prepare_fit(self, ticket, host, slot, directory, topology, now):
        shape = next(c for c in self.configs.values() if c['host'] == host)
        whole_host=ticket.get('memory_gib')==40
        if whole_host:shape=aws12_config(shape)
        directory = Path(directory)
        directory.mkdir()
        generated = generate(ticket, directory/'generated', shape['workers'])
        synthesis=ticket.get('mode') in ('synthesis_only','place_only')
        q = frozen_queue(synthesis)
        runner = q.module('new_run_source', 'cloud/plain_fit_v5.py')
        if whole_host:
            runner=aws12_runner(runner)
            q.HOSTS[host]=aws12_config(q.HOSTS[host])
        if synthesis:runner=synthesis_module(runner,ticket['mode'])
        context = runner.runner(dict(runner.HOSTS[host], root=str(FPGA/'cloud')), host, False).verify_project(generated)
        variant = dict(path=str(generated), files={str(p.relative_to(generated)):digest(regular(p)) for p in generated.rglob('*') if p.is_file()}, project=context)
        contract = ticket['source_contract']
        if 'structural_spec' in contract:
            spec = deepcopy(read(contract['structural_spec']))
            spec['settings'] = {name:digest(regular(generated/name)) for name in spec['settings']}
            spec['identity'].update(clock_period_ns=float(ticket['settings']['period_ns']), seed=ticket['settings']['seed'])
            target = directory/'structural-inventory.json'
            save(target, spec)
            variant['structural_spec'] = reference(target)
        else:
            variant.update(contract)
        job = dict(id=ticket['id'], project_name='fit-'+ticket['id'], unit='gfn16-fit-'+ticket['id']+'.service', scope=ticket['scope'], variants={host:variant})
        field = ticket['scope'] == 'component_probe' and contract.get('exemption') == 'component_sizing_probe'
        profile=runtime_contract(ticket)
        q.HORIZON = profile['host_hours_horizon_seconds'] if profile else 21780
        original_module = q.module
        hourly = self.money.hourly_meter('azure' if host == 'gfn16-azure-f16' else 'aws')
        q.module = lambda name,relative:hourly if relative in ('cloud/host_hours_azure_v5.py', 'cloud/host_hours_admit_v2.py') else runner if (synthesis or whole_host) and relative=='cloud/plain_fit_v5.py' else original_module(name, relative)
        handle, _, archive = q.prepare(job, host, slot, directory/'package', topology, now)
        tools = Path(handle['request']['path']).parent
        for source in (Path(__file__).resolve(), HERE/'plain_fit_queue_v6.py'):
            shutil.copy2(source, tools/source.name)
        if synthesis:
            regular(FPGA/'cloud/aws_syn_v1.py',SYN_HELPER_SHA)
            shutil.copy2(FPGA/'cloud/aws_syn_v1.py',tools/'aws_syn_v1.py')
            if ticket['mode']=='place_only':
                regular(FPGA/'synthesis/staged_fit.py',PLACE_HELPER_SHA)
                shutil.copy2(FPGA/'synthesis/staged_fit.py',tools/'staged_fit.py')
        request_path = Path(handle['request']['path'])
        request = json.loads(request_path.read_text())
        request.update(scope=ticket['scope'], standing_dispatch_sha256=digest(regular(Path(__file__).resolve())), budget_policy=self.money.reference,
                       budget_policy_helper_sha256=digest(regular(FPGA/'cloud/fit_budget_policy.py')), hourly_provider_status=hourly.status)
        if ticket.get('memory_gib'):request['memory_bytes']=ticket['memory_gib']<<30
        if ticket.get('resource_basis'):
            request['resource_basis_evidence']=dict(reference=ticket['resource_basis'],basis=read(ticket['resource_basis']))
        if field:
            request['runtime_contract'] = FIELD
        if synthesis:
            evidence=native_source_gate(ticket)
            need(evidence is not None,'actual native normal prerequisite pending')
            request.update(mode=ticket['mode'],native_gate_evidence=evidence,runtime_contract=profile)
        if profile in (P8_FULL,P16_FULL):
            evidence=native_source_gate(ticket)
            need(evidence is not None,'actual native normal prerequisite pending')
            request.update(native_gate_evidence=evidence,runtime_contract=profile)
        request_path.write_text(json.dumps(request, indent=2)+'\n')
        handle.update(request=reference(request_path), request_sha256=digest(regular(request_path)), kind='placement' if ticket.get('mode')=='place_only' else 'synthesis' if synthesis else 'fit', horizon_seconds=q.HORIZON,
                      after_collection_action=ticket['after_collection_action'], track=ticket['track'], purpose=ticket['purpose'])
        handle['memory_bytes']=request.get('memory_bytes',shape['memory'])
        helpers = {str(p.relative_to(tools)):digest(regular(p)) for p in tools.rglob('*') if p.is_file()}
        # Rewrite ONLY this fresh, never-staged local archive after the request
        # is finalized. Old prepared packages/running projects are untouched.
        archive.unlink()
        with tarfile.open(archive, 'w:gz') as stream:
            stream.add(Path(archive).parent/job['project_name'], arcname=job['project_name'])
            stream.add(tools, arcname=tools.name)
        handle['package_sha256'] = digest(regular(archive))
        save(directory/'prepared.json', dict(handle=handle, helpers=helpers, archive=str(archive)))
        return handle, helpers, archive

    def adopt(self, legacy_queue_ref, legacy_journal_ref, controller_ref, callbacks=None):
        """Import immutable original claims; actual observe proof precedes adoption."""
        queue = read(legacy_queue_ref)
        regular(controller_ref['path'], controller_ref['sha256'])
        rows, previous = [], '0'*64
        for line in regular(legacy_journal_ref['path'], legacy_journal_ref['sha256']).splitlines():
            row = json.loads(line)
            pin = row.pop('sha256')
            need(row['sequence'] == len(rows) and row['previous'] == previous and row['queue_sha256'] == digest(canonical(queue))
                 and row['controller_sha256'] == controller_ref['sha256'] and digest(canonical(row)) == pin, 'original legacy journal chain')
            row['sha256'] = pin
            rows.append(row)
            previous = pin
        current = frozen_queue().Journal.current(types.SimpleNamespace(rows=rows))
        known = self.journal.current()
        for key, handle in current.items():
            if handle['phase'] == 'terminal' or key in known:
                continue
            original = read(handle['request'])
            need(handle['request_sha256'] == handle['request']['sha256'] and all(handle[k] == original[k] for k in ('host', 'slot', 'unit', 'project_name')), 'original adopted request')
            need(type(handle.get('invocation_id')) is str and re.fullmatch('[0-9a-f]{32}', handle['invocation_id']), 'actual original invocation required')
            handle = dict(handle, kind='fit', after_collection_action=(callbacks or {}).get(key))
            occupied = {(v['handle']['host'], v['handle']['slot']) for v in self.journal.current().values() if v['phase'] != 'terminal' and 'handle' in v}
            need((handle['host'], handle['slot']) not in occupied, 'unique adopted physical claim')
            self.journal.append('adopt_intent', key, handle=handle)
            try:
                self.observation(handle, self.backend.observe(handle))
                self.journal.append('started', key)
            except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
                self.journal.append('unresolved', key, reason=str(error))

    def observation(self, handle, observation):
        need(type(observation) is dict and type(observation.get('state')) is dict, 'typed native observation')
        need(observation['request_sha256'] == handle['request_sha256'], 'exact observed request')
        inv = observation.get('invocation_id')
        need(type(inv) is str and re.fullmatch('[0-9a-f]{32}', inv), 'typed actual native invocation')
        need(not handle.get('invocation_id') or handle['invocation_id'] == inv, 'original invocation drift')
        return inv

    def adopt_audit(self, handle):
        """Observe an already-started exact audit, never stage/start it again."""
        need(handle.get('kind') == 'audit' and handle.get('parent_id') in self.journal.current(), 'existing audit parent required')
        parent = self.journal.current()[handle['parent_id']]['handle']
        need(handle['original_invocation'] == parent['invocation_id'] and handle['host'] in frozen_queue().HOSTS
             and handle['slot'] in frozen_queue().HOSTS[handle['host']]['slots'], 'exact original audit identity/slot')
        known = self.journal.current()
        if handle['id'] in known and known[handle['id']]['phase'] != 'queued':
            need(known[handle['id']]['handle']['unit'] == handle['unit'], 'existing audit cannot change unit')
            return
        occupied = {(v['handle']['host'], v['handle']['slot']) for v in known.values() if v['phase'] != 'terminal' and 'handle' in v}
        need((handle['host'], handle['slot']) not in occupied, 'audit slot already claimed')
        self.journal.append('adopt_intent', handle['id'], handle=handle)
        try:
            inv = self.observation(handle, self.backend.observe(handle))
            self.journal.append('started', handle['id'], handle_delta={'invocation_id':inv})
        except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
            self.journal.append('unresolved', handle['id'], reason=str(error))

    def start(self, key, handle, helpers, archive, now):
        self.journal.append('stage_attempt', key)
        delta = self.backend.stage(handle, archive)
        if delta is not None:
            need(type(delta) is dict and all(delta[k] == handle[k] for k in ('id', 'host', 'slot', 'unit')), 'same staged action identity')
            handle.update(delta)
        self.journal.append('stage_complete', key, handle_delta=handle)
        self.launch_ready(key, handle, helpers, now)

    def launch_ready(self, key, handle, helpers, now):
        need(not paused() and datetime.now(timezone.utc) < self.end, 'PAUSE/absolute intake cutoff before launch')
        need(datetime.now(timezone.utc).timestamp()+handle.get('horizon_seconds',21780)+COLLECTION_MARGIN_SECONDS <= WRAP_END.timestamp(),
             'finite native completion and collection before wrap end')
        self.money.recheck()
        if handle.get('kind') not in ('audit','synthesis','placement') and handle.get('scope')=='whole_core':
            request=read(handle['request'])
            need(request.get('project',{}).get('qsf_parameters',{}).get('P') not in self.money.policy['priorities'].get('hold_whole_lanes',[]) or key in self.money.policy['priorities'].get('allowed_whole_ids',[]),'whole-P16 area/LAB gate holds unstarted fits')
        self.journal.append('launch_attempt', key)
        observed = self.backend.launch(handle, helpers)
        inv = self.observation(handle, observed)
        self.journal.append('started', key, handle_delta={'invocation_id':inv})

    def tick(self, now=None):
        now = now or datetime.now(timezone.utc)
        need(now.tzinfo is not None and now.utcoffset().total_seconds() == 0, 'UTC tick')
        for ticket_path in sorted((self.queue/'tickets').glob('*.json')):
            ticket = {}
            try:
                ref = reference(ticket_path)
                ticket = read(ref)
                known = self.journal.current()
                if ticket['id'] not in known:
                    validate_ticket(ticket, self.profile_ref)
                    self.journal.append('ticket', ticket['id'], ticket=ref)
                elif known[ticket['id']].get('ticket'):
                    need(known[ticket['id']].get('submitted_ticket',known[ticket['id']]['ticket']) == ref, 'immutable queued ticket')
            except (ValueError, KeyError, OSError) as error:
                self.journal.append('blocked', str(ticket.get('id', ticket_path.stem)), reason=str(error))
        for key, record in self.journal.current().items():
            if record['phase'] in ('queued', 'terminal'):
                continue
            handle = record['handle']
            try:
                if record['phase'] == 'stage_complete':
                    prepared = read(record['prepared'])
                    self.launch_ready(key, handle, prepared['helpers'], now)
                    continue
                if record['phase'] in ('intent', 'stage_attempt'):
                    # Audit stage() can recover an existing source-bound native
                    # preparation without repeating inventory. Fits need an
                    # explicit read-only stage reconciliation, never extraction.
                    if handle.get('kind') == 'audit':
                        prepared = read(record['prepared'])
                        self.start(key, handle, prepared['helpers'], Path(prepared['archive']), now)
                    continue
                observed = self.backend.observe(handle)
                inv = self.observation(handle, observed)
                if not handle.get('invocation_id'):
                    handle = dict(handle, invocation_id=inv)
                    self.journal.append('started', key, handle_delta={'invocation_id':inv})
                state = observed['state']
                if state.get('MainPID') != '0' or state.get('ActiveState') not in ('inactive', 'failed'):
                    continue
                bundle = self.backend.collect(handle)
                outcome = self.backend.verify_terminal(handle, bundle)
                allowed = ('audit_timing_pass', 'audit_timing_violation','audit_native_failure') if handle.get('kind') == 'audit' else ('native_placement_success','native_placement_failure') if handle.get('kind')=='placement' else ('native_synthesis_success','native_synthesis_failure') if handle.get('kind')=='synthesis' else ('native_fit_success', 'native_fit_failure','native_prelaunch_failure')
                need(outcome in allowed, 'typed collected terminal')
                self.journal.append('terminal', key, outcome=outcome, bundle=bundle)
                if handle.get('scope')=='whole_core' and handle.get('kind') not in ('synthesis','placement') or handle.get('kind')=='audit':
                    self.postfit_summary(handle,bundle)
            except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
                self.journal.append('unresolved', key, reason=str(error))
        current = self.journal.current()
        audits = getattr(self.backend, 'audits', None)
        for key, record in current.items():
            if record['phase'] != 'terminal' or record.get('callback_complete') or not record['handle'].get('after_collection_action') or audits is None:
                continue
            prior = [v['bundle'] for v in current.values() if v['phase'] == 'terminal' and v.get('handle', {}).get('parent_id') == key]
            if any(v['phase'] != 'terminal' and v.get('handle', {}).get('parent_id') == key for v in current.values()):
                continue
            try:
                action = audits.next(record['handle'], record['bundle'], prior)
                if action is None or action.get('kind') == 'audit_search_result':
                    self.journal.append('callback_complete', key, result=action)
                else:
                    need(action.get('kind') == 'audit' and action['parent_id'] == key and action['host'] in frozen_queue().HOSTS, 'registered bounded audit action')
                    frozen_queue().name(action['id'])
                    if action['id'] not in self.journal.current():
                        self.journal.append('action', action['id'], action=action)
            except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
                self.journal.append('unresolved', key, reason='audit callback: '+str(error))
        if paused() or now >= self.end:
            return self.journal.current()
        self.money.recheck()
        current = self.journal.current()
        occupied = {(v['handle']['host'], v['handle']['slot']) for v in current.values() if v['phase'] != 'terminal' and 'handle' in v}
        def order(pair):
            try:
                priorities=self.money.policy['priorities']
                focus=0 if priorities.get('preferred_lanes') is not None and design_lanes(pair[1])==priorities['preferred_lanes'] else 1
                if 'ticket' not in pair[1]:return (0,focus,1,-1,pair[0])
                ticket = read(pair[1]['ticket'])
                track = priorities['tracks'].index(ticket['track'])
                purpose = priorities['s_purposes'].index(ticket['purpose']) if ticket['track'] == 'S' else 0
                if priorities.get('field_probes_first') and ticket['scope']=='component_probe':purpose=-1
                return (track,focus,purpose,ticket['priority'],pair[0])
            except (ValueError, KeyError, OSError):
                return (99,99,99,99,pair[0])
        queued = sorted(((k,v) for k,v in current.items() if v['phase'] == 'queued'), key=order)
        preferred_waiting=set()
        for key, record in queued:
            try:
                action = record.get('action')
                priority=self.money.policy['priorities'];lanes=design_lanes(record)
                if not action and key in priority.get('superseded_unstarted_ids',[]):continue
                secondary_key=action['parent_handle'].get('id',action.get('parent_id')) if action else key
                if lanes in priority.get('parked_lanes',[]) and secondary_key not in priority.get('allowed_secondary_ids',[]):continue
                if lanes in priority.get('parked_lanes',[]) and preferred_waiting:continue
                if not action and lanes in priority.get('hold_whole_lanes',[]) and read(record['ticket'])['scope']=='whole_core' and read(record['ticket']).get('mode') not in ('synthesis_only','place_only') and key not in priority.get('allowed_whole_ids',[]):continue
                if action:
                    horizon = 2280
                    slots=next(c['slots'] for c in self.configs.values() if c['host']==action['host'])
                    preferred=action['parent_handle']['slot']
                    options=[(action['host'],s) for s in [preferred,*[s for s in slots if s!=preferred]]]
                    prepare = lambda h,s,d,t,n:audits.prepare(dict(action,slot=s), d, t, n)
                else:
                    ticket = validate_ticket(read(record['ticket']), self.profile_ref)
                    if ticket.get('native_source_gate') and native_source_gate(ticket) is None:
                        continue
                    priority = self.money.policy['priorities']
                    if ticket['track'] == 'A':
                        if ticket['purpose'] != 'a10_pending' or key not in priority['allowed_a_ids']:
                            continue
                        if sum(v.get('handle', {}).get('track') == 'A' and v['phase'] != 'terminal' for v in current.values()) >= priority['max_new_a_slots']:
                            continue
                    dependencies = [current.get(d['job']) for d in ticket['after']]
                    if any(v is None or v['phase'] != 'terminal' or v['outcome'] != d['outcome'] for v,d in zip(dependencies, ticket['after'])):
                        continue
                    for gate in ticket['requires']:
                        value = read({'path':gate['path'], 'sha256':gate['sha256']})
                        need(all(type(value.get(k)) is type(wanted) and value.get(k) == wanted for k,wanted in gate['fields'].items()), 'typed native prerequisite')
                    profile=runtime_contract(ticket)
                    horizon = profile['host_hours_horizon_seconds'] if profile else 21780
                    options = [(self.configs[shape]['host'], slot) for shape,slots in ticket['slot_shapes'].items() for slot in slots]
                    critical=ticket['id'] in priority.get('aws_first_ids',[]) or ticket['purpose'] in priority.get('aws_first_purposes',[])
                    if critical:
                        options.sort(key=lambda hs:hs[0]!='gfn16-aws-m8i')
                    execution_ticket=dict(ticket,id=record.get('execution_id',ticket['id']))
                    prepare = lambda h,s,d,t,n:self.prepare(execution_ticket, h, s, d, t, n)
                if now >= self.end or now.timestamp()+horizon+COLLECTION_MARGIN_SECONDS > WRAP_END.timestamp():
                    continue
                if priority.get('preferred_lanes') is not None and lanes==priority['preferred_lanes']:preferred_waiting.add(key)
                failed_hosts=set()
                for host,slot in options:
                    if lanes==16 and not action and ticket['scope']=='whole_core' and ticket.get('mode') not in ('synthesis_only','place_only') and host in priority.get('whole_p16_blocked_hosts',[]) and ticket.get('memory_gib') not in (32,40):
                        continue
                    if (host, slot) in occupied:
                        continue
                    if host in failed_hosts:
                        continue
                    requested_memory=(ticket.get('memory_gib',0)<<30) if not action and ticket.get('memory_gib') else next(c['memory'] for c in self.configs.values() if c['host']==host)
                    reserved=sum(v['handle'].get('memory_bytes',next(c['memory'] for c in self.configs.values() if c['host']==host))
                                 for v in current.values() if v['phase']!='terminal' and v.get('handle',{}).get('host')==host)
                    ceiling=(96 if host=='gfn16-azure-f16' else 40)<<30
                    if reserved+requested_memory>ceiling:continue
                    try:
                        topology = self.backend.preflight(host, slot,requested_memory) if not action and ticket.get('memory_gib') else self.backend.preflight(host, slot)
                        attempt = sum(r['event'] == 'blocked' and r['job'] == key for r in self.journal.rows)
                        directory = self.directory/'prepared'/(record.get('execution_id',key)+'-attempt'+str(attempt))
                        directory.parent.mkdir(parents=True, exist_ok=True)
                        handle, helpers, archive = prepare(host, slot, directory, topology, now)
                    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
                        self.journal.append('blocked',key,reason=str(error),host=host,slot=slot)
                        failed_hosts.add(host)
                        continue
                    handle['horizon_seconds'] = horizon
                    prepared_path = directory/'dispatch-prepared.json'
                    save(prepared_path, dict(handle=handle, helpers=helpers, archive=str(archive)))
                    self.journal.append('intent', key, handle=handle, prepared=reference(prepared_path))
                    occupied.add((host, slot))
                    current[key]=dict(phase='intent',handle=handle)
                    self.start(key, handle, helpers, archive, now)
                    preferred_waiting.discard(key)
                    break
            except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
                self.journal.append('blocked', key, reason=str(error))
        return self.journal.current()

    def postfit_summary(self,handle,bundle):
        target=Path(bundle['receipt']).parent/'setup-class-summary.json'
        if not target.is_absolute() or not target.is_relative_to(self.directory):return
        if target.exists():return
        try:
            parser=load(HERE/'summarize_setup_classes.py',digest(regular(HERE/'summarize_setup_classes.py')))
            if handle.get('kind')=='audit':
                value={phase:parser.analyze(Path(bundle['receipt']),Path(bundle['archive']),phase)
                       for phase in (('baseline','selected') if handle.get('selected_period_ns') is not None else ('baseline',))}
            else:value=parser.analyze_verified_fit(Path(bundle['receipt']),Path(bundle['evidence']))
        except Exception as error:
            value=dict(status='diagnostic_unavailable',reason=str(error),scope=handle.get('scope'),source_receipt=bundle['receipt'])
        save(target,value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker-run', nargs=2, metavar=('REQUEST', 'SHA256'))
    parser.add_argument('--queue', type=Path)
    parser.add_argument('--state', type=Path)
    parser.add_argument('--policy', type=Path, default=FPGA/'cloud/fit-policy-v1.json')
    parser.add_argument('--profiles', type=Path, default=FPGA/'cloud/fit-host-profiles-v1.json')
    parser.add_argument('--policy-sha256')
    parser.add_argument('--profiles-sha256')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--tick', action='store_true')
    group.add_argument('--loop', action='store_true')
    group.add_argument('--status', action='store_true')
    group.add_argument('--adopt', type=Path, help='immutable list of legacy_queue,legacy_journal,controller refs and optional callbacks')
    group.add_argument('--retry-pre-native',help='Explicit operator recovery only after exact typed pre-vendor rejection; fresh namespace, original retained')
    parser.add_argument('--adopt-sha256')
    parser.add_argument('--audit-backend', type=Path)
    parser.add_argument('--audit-backend-sha256')
    args = parser.parse_args()
    if args.worker_run:
        raise SystemExit(native_run(Path(args.worker_run[0]), args.worker_run[1]))
    need(args.queue is not None and args.state is not None and any((args.tick, args.loop, args.status, args.adopt,args.retry_pre_native)), 'explicit standing queue action')
    p = reference(args.policy)
    h = reference(args.profiles)
    need(args.policy_sha256 is None or p['sha256'] == args.policy_sha256, 'policy pin')
    need(args.profiles_sha256 is None or h['sha256'] == args.profiles_sha256, 'profile pin')
    q = frozen_queue()
    with q.controller_lock(args.state.resolve()):
        audits = load(args.audit_backend, args.audit_backend_sha256).AuditBackend(args.state.resolve(), END) if args.audit_backend else None
        controller = Controller(args.queue, args.state, p, h, SSHBackend(args.state.resolve(), END, audits))
        if args.retry_pre_native:
            controller.retry_pre_native(args.retry_pre_native)
            print(json.dumps(controller.journal.current()[args.retry_pre_native]));return
        if args.adopt:
            for item in read(dict(path=str(args.adopt.resolve()), sha256=args.adopt_sha256)):
                if 'audit_handle' in item:
                    controller.adopt_audit(read(item['audit_handle']))
                else:
                    controller.adopt(item['legacy_queue'], item['legacy_journal'], item['controller'], item.get('callbacks'))
        while True:
            if not (args.status or args.adopt):
                # Shared cached checks refresh once per provider hour, even
                # with no queued fits. Native jobs never repeat the arithmetic.
                for provider in ('azure', 'aws'):
                    controller.money.hourly(provider)
            value = controller.journal.current() if args.status or args.adopt else controller.tick()
            print(json.dumps(value, allow_nan=False), flush=True)
            if not args.loop or datetime.now(timezone.utc) >= controller.end:
                break
            time.sleep(30)


if __name__ == '__main__':
    main()

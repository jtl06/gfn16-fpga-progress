"""r75 field normals: source-only coordinator, independent NTT on worker.

The shared timing compiler is stream_core-owned. This helper only compiles a
bounded native comparator/lease contract and packages immutable normal roles.
No full-N numeric transform or HDL execution occurs during preparation.
"""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import importlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_timing_field_native.py'
API='reference/stream27_timing_flags.py'
API_BY_P={8:API,16:'reference/stream27_p16_timing_flags.py'}
CPP='rtl/tb/stream27_timing_field_normal.cpp'
HEADER='rtl/tb/s4_full_config_v1.h'
REFERENCE='rtl/tb/stream27_shared_reference_ntt_v1.h'
REFERENCE_PIN='c7837ba92829293131efda704dfdde347708641bf9aff46dccbcb87b825ba390'
FLAGS=dict(boundary_inputreg=1,quarantine_replicas=1,final_gs_inputreg=1)
NATIVE_WRAPPER_READY='2026-10-01T23:33:46Z'

def field_flags(p):
    # P16 owns its composed-diet donor and the qualified payload-only term
    # selector. Captured P8 roles keep their original three timing flags.
    return dict(FLAGS,term_select_token=1) if p==16 else dict(FLAGS)

def role_version(p):return 2 if p==16 else 1

def need(ok,why):
    if not ok:raise ValueError(why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def dump(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2);f.write('\n')

def preflight(manifest,files):
    names=[step['name'] for step in manifest['steps']]
    need(names and len(names)==len(set(names)) and all(re.fullmatch('[a-z][a-z0-9-]*',name)
        and name not in ('build','probe','verilator-version','compiler-version') for name in names),'R75_FIELD_NATIVE_STEP_GRAMMAR')
    build=manifest['build']
    need(len(build['sv_sources'])==len(set(build['sv_sources'])) and all(type(value) is int for value in build['parameters'].values()),'R75_FIELD_TYPED_UNIQUE_BUILD')
    for name in build['sv_sources']+[build['cpp_source']]:
        need(name in files and manifest['sources'][name]==sha(files[name]),'R75_FIELD_CLOSED_COMPILED_SOURCE')
    for name,pin in manifest['rtl_readiness']['source_snapshot'].items():
        need(name.endswith('.sv') and manifest['sources'].get(name)==pin,'R75_FIELD_DESIGN_READINESS')
    return manifest,files

def field_bundle(aw,p,field,api_sha256):
    need(type(aw) is int and aw in (8,16) and type(p) is int and p in (8,16) and type(field) is int and field in (0,1,2),'R75_FIELD_GEOMETRY')
    api=API_BY_P[p]
    need(re.fullmatch('[0-9a-f]{64}',api_sha256) and sha((ROOT/api).read_bytes())==api_sha256,'R75_FROZEN_SHARED_API')
    core=importlib.import_module('fpga.reference.'+Path(api).stem)
    b=core.prepare_field(1<<aw,p,field,mode='warm',contexts=1,allow_full_constants=aw==16,**field_flags(p))
    need(b['parameters']['AW']==aw and b['parameters']['P']==p and b['parameters'].get('CONTEXTS',1)==1,'R75_FIELD_PARAMETER_JOIN')
    need(b['geometry']['n']==1<<aw and b['geometry']['rows']==(1<<aw)//p,'R75_FIELD_CALENDAR_JOIN')
    need(api in b['source_dependencies'] and b['source_sha256'][api]==api_sha256,'R75_FIELD_API_LINEAGE')
    if p==16:
        need(all(b['parameters'].get(key)==value for key,value in
            dict(CORR_SERIAL_BFS=2,COMM_STAGE_SHARED_MLAB=1,MONT_FACTORED=1,TERM_SELECT_TOKEN=1).items()),'R75_P16_EXACT_DIET_SELECTOR')
    return b

def native_wrapper_bundle(bundle,field):
    """Short simulation top only; every production file remains byte exact.

    Verilator 5.032 shortens >128-character module names before its explicit
    top lookup. A short transparent top avoids that CLI seam without editing
    the captured production declaration, parameters, ports or source.
    """
    b=deepcopy(bundle);old=b['top'];parent=b['files'][old+'.sv']
    begin=parent.index('module '+old+' #(');end=parent.index(');',begin)+2
    header=parent[begin:end]
    match=re.fullmatch(r'module '+re.escape(old)+r' #\(parameter int ([^\n()]*)\) \(\n(.*)\);',header,re.S)
    need(match is not None,'R75_NATIVE_WRAPPER_EXACT_HEADER')
    parameters=[]
    for item in match.group(1).split(','):
        entry=re.fullmatch(r'([A-Za-z_]\w*)=([0-9]+)',item)
        need(entry is not None,'R75_NATIVE_WRAPPER_LITERAL_PARAMETERS')
        parameters.append(entry.group(1))
    need(len(parameters)==len(set(parameters)) and set(parameters)==set(b['parameters'])-{'FIELD'},'R75_NATIVE_WRAPPER_PARAMETER_JOIN')
    top=f'genefer_s4_r75_field_normal_aw{b["parameters"]["AW"]}_p{b["parameters"]["P"]}_f{field}_v2'
    wrapper_header=header.replace('module '+old+' #(','module '+top+' #(',1)
    wrapper=wrapper_header+'\n '+old+' #(\n  '+',\n  '.join('.'+name+'('+name+')' for name in parameters)+'\n ) candidate (.*);\nendmodule\n'
    # Exact construction/reversal: no added state or logic. Port declaration
    # text is copied, not reinterpreted or narrowed by the native fixture.
    need(wrapper_header.replace('module '+top+' #(','module '+old+' #(',1)==header,'R75_NATIVE_WRAPPER_HEADER_REVERSE')
    need(not re.search(r'\b(always|always_ff|always_comb|initial|assign)\b',wrapper),'R75_NATIVE_WRAPPER_ZERO_EDGE')
    b['files'][top+'.sv']=wrapper;b['top']=top
    b['rtl_sources'].append(top+'.sv');b['generated_sha256'][top+'.sv']=sha(wrapper.encode())
    need(all(b['files'][name]==text for name,text in bundle['files'].items()),'R75_NATIVE_WRAPPER_PRODUCTION_BYTES')
    b['native_wrapper']=dict(production_top=old,production_header_sha256=sha(header.encode()),
        production_top_sha256=sha(parent.encode()),wrapper_top=top,wrapper_sha256=sha(wrapper.encode()),
        parameter_names=parameters,ports_exact=True,all_production_bytes_exact=True,
        added_edges=0,scope='Native-only short transparent top; no production generator or mathematical/calendar edit.')
    return b

def compile_normal(b,field):
    from fpga.reference.stream27_shared_warm_full_native_v1 import compile_bench
    from fpga.reference.stream27_p8_warm_native_v2 import lease_ledger
    g=b['geometry'];aw=b['parameters']['AW'];p=b['parameters']['P'];rows=g['rows'];interval=g['warm_interval']
    groups=([0],[0,interval],[0,interval+16])
    ledgers=[lease_ledger(starts,g['sink_accept'],rows) for starts in groups]
    need(all(not item['rejected'] for item in ledgers),'R75_FIELD_NORMAL_LEASE')
    text,header=compile_bench(b,field)
    marker=f'S4_R75_FIELD_PASS aw={aw} p={p} field={field}'
    need(text.count('S4_SHARED_AW16_PASS')==1,'R75_FIELD_MARKER')
    text=text.replace('S4_SHARED_AW16_PASS',marker)
    anchor='counts.peak=std::max(counts.peak,unsigned(d.owner_count));'
    need(text.count(anchor)==1,'R75_FIELD_LEASE_BENCH_ANCHOR')
    text=text.replace(anchor,'''unsigned expected_owners=0;
        for(const auto& f:frames)expected_owners+=tick>=f.start && tick<f.start+SINK+T-1;
        need(unsigned(d.owner_count)==expected_owners,"R75_FIELD_OWNER_EDGE tick="+std::to_string(tick));
        counts.peak=std::max(counts.peak,unsigned(d.owner_count));''')
    counts=dict(cases=9,frames=9,physical_rows=9*rows,physical_words=9*g['n'],
        eligible_rows=7*rows,commits=7*rows,peak_owners=max(item['peak'] for item in ledgers))
    footer=marker+' '+' '.join(f'{key}={value}' for key,value in counts.items())+'\n'
    return text,header,counts,ledgers,footer

def role(aw,p,field,api_sha256,rtl_ready_at_utc,*,bundle=None):
    need(sha((ROOT/REFERENCE).read_bytes())==REFERENCE_PIN,'R75_FROZEN_INDEPENDENT_NTT_REFERENCE')
    b=field_bundle(aw,p,field,api_sha256) if bundle is None else deepcopy(bundle)
    need(b['parameters']['AW']==aw and b['parameters']['P']==p and b['parameters']['FIELD']==field
        and b['source_sha256'].get(API_BY_P[p])==api_sha256,'R75_FIELD_EXPLICIT_BUNDLE_JOIN')
    if p==16:b=native_wrapper_bundle(b,field)
    text,header,counts,ledgers,footer=compile_normal(b,field)
    from fpga.reference.stream27_shared_warm_full_native_v1 import BENCH
    files={'rtl/'+name:value.encode() for name,value in b['files'].items()}
    files.update({CPP:text.encode(),HEADER:header.encode(),REFERENCE:(ROOT/REFERENCE).read_bytes()})
    lineage=list(dict.fromkeys(b['source_dependencies']+[SELF,'reference/stream27_shared_warm_full_native_v1.py',
        'reference/stream27_p8_warm_native_v2.py',BENCH]))
    for name in lineage:files['lineage/'+name]=(ROOT/name).read_bytes()
    changed={'rtl/'+name:pin for name,pin in b['generated_sha256'].items() if name.endswith('.sv')}
    ready=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=f's4-r75-field-aw{aw}-p{p}-f{field}-v{role_version(p)}',
        candidate_source_sha256=sha(canonical(changed)),rtl_ready_at_utc=NATIVE_WRAPPER_READY if p==16 else rtl_ready_at_utc,source_snapshot=changed)
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/not-a-dispatch-path/r75-field/fpga',output_parent='/not-a-dispatch-path/r75-field/output',
        sources={name:sha(raw) for name,raw in files.items()},
        build=dict(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],cpp_source=CPP,
            parameters={name:value for name,value in b['parameters'].items() if name!='FIELD'},
            cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='normal-r75-shared-field-numeric-tags-all-lease-edges',argv=['{exe}'],
            expected_returncode=0,expected_stdout=footer,expected_stderr='')],
        test_role='normal',rtl_readiness=ready,
        r75_field=dict(flags=field_flags(p),api=API_BY_P[p],api_sha256=api_sha256,geometry=b['geometry'],counts=counts,lease_ledger=ledgers,
            production_rtl_ready_at_utc=rtl_ready_at_utc,native_wrapper=b.get('native_wrapper'),
            source_sha256=b['source_sha256'],generated_sha256=b['generated_sha256'],
            reference='Frozen independent iterative twist/cyclic-square/untwist; worker N256 signed schoolbook selfcheck.',
            scope='One combined-r75 warm field only, actual full-size roots/normalization and exact lease/tag calendar. No CRT/carry/host/publication/PRP/whole clock claim.',
            full_N_numeric_locally_performed=False))
    return preflight(manifest,files)

def prepare(output,aw,p,field,budget,api_sha256,rtl_ready_at_utc,*,role_builder=None,family='s4-r75-field',version=None,prerequisites=()):
    from fpga.tools import native_class_package_v2 as package
    output=Path(output).resolve()
    need(output.is_relative_to(ROOT) and not output.exists() and not any((ROOT/path).exists() for path in ('docs/briefs/PAUSE','queue/PAUSE')),'R75_FIELD_FRESH_PAUSE')
    m,files=(role if role_builder is None else role_builder)(aw,p,field,api_sha256,rtl_ready_at_utc)
    version=role_version(p) if version is None else version
    need(re.fullmatch('[a-z][a-z0-9-]*',family) and type(version) is int and version>=1,'R75_FIELD_ROLE_NAMESPACE')
    source=output/'input/source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as f:f.write(raw)
    manifest=output/'input/manifest.json';dump(manifest,m);variants=[]
    for pair in ('01','23'):
        profile=f'gcp-c4d-static{pair}-v1';worker=f'{family}-aw{aw}-p{p}-f{field}-{pair}-v{version}';packet=output/('packet-'+pair)
        result=package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve())
        variants.append(dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),native_root=result['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v3.py'),stager_sha256=sha((ROOT/'tools/native_package_v3.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/'tools/native_package_v2.py'),sha256=sha((ROOT/'tools/native_package_v2.py').read_bytes()))],max_seconds=3700))
    qid=f'{family}-aw{aw}-p{p}-f{field}-normal-q1-v{version}'
    ticket=dict(schema='gfn16-global-ticket-v1',id=qid,owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=8 if aw==16 else 4,
        minimum_ram_rationale='FullN8GiB unchanged; small bounded field4GiB exploratory cap, not measured peak.',
        est_minutes=10,promotion_bound=False,test_role='normal',packages=variants,rtl_readiness=m['rtl_readiness'])
    after=list(prerequisites)
    if aw==16:after += [f'{family}-aw8-p{p}-f{f}-normal-q1-v{version}' for f in range(3)]
    if after:ticket.update(after=list(dict.fromkeys(after)),on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',ticket)
    dump(output/'preparation.json',dict(status='source_prepared_not_native',id=qid,geometry=m['r75_field']['geometry'],
        source_sha256=m['r75_field']['source_sha256'],generated_sha256=m['r75_field']['generated_sha256']))
    return dict(id=qid,ticket=str(output/'global-ticket-v1.json'))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--aw',type=int,choices=(8,16),required=True)
    parser.add_argument('--p',type=int,choices=(8,16),default=8);parser.add_argument('--field',type=int,choices=(0,1,2),required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=Path,required=True)
    parser.add_argument('--api-sha256',required=True);parser.add_argument('--rtl-ready-at-utc',required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.output,args.aw,args.p,args.field,args.budget,args.api_sha256,args.rtl_ready_at_utc),indent=2))

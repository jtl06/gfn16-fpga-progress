"""Private L3b normal-first field roles and matched component projects.

Only source/ROM constants are generated locally. Native independent NTT and
actual RTL comparisons execute on the admitted worker, never on the Mac.
"""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
from . import stream27_l3b_ct_bind as binding
from . import stream27_shared_field_flags as core
from . import stream27_timing_field_native as harness

ROOT=binding.ROOT
SELF='reference/stream27_l3b_ct_field_native.py'
CPP='rtl/tb/stream27_l3b_ct_field_normal.cpp'
HEADER='rtl/tb/s4_full_config_v1.h'
REFERENCE=harness.REFERENCE
FAULT='reference/stream27_l3b_ct_fault.py'
FAMILY='s4-l3b-ct-field'


def need(ok,label):
    if not ok:raise ValueError('L3B_FIELD_'+label)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def dump(path,value):
    with Path(path).open('x') as out:json.dump(value,out,indent=2);out.write('\n')
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def field_bundle(aw=8,field=0,*,enabled=1):
    need(type(aw) is int and aw in (8,16) and type(field) is int and field in (0,1,2),'GEOMETRY')
    b=core.prepare(1<<aw,16,field,mode='warm',contexts=1,allow_full_constants=aw==16,
        corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1)
    return binding.bind(b,enabled=enabled)


def role(aw=8,field=0,*,enabled=1,mutant=False,ready_at=None):
    need(type(mutant) is bool and (not mutant or (aw,field,enabled)==(8,0,1)),'EXACT_MUTANT_ROLE')
    need(sha((ROOT/REFERENCE).read_bytes())==harness.REFERENCE_PIN,'FROZEN_INDEPENDENT_REFERENCE')
    b=field_bundle(aw,field,enabled=enabled);production=deepcopy(b)
    if mutant:
        name=Path(binding.NEW).name;text=b['files'][name]
        old="y0<=gs_pipe[4] ? prefix_pipe[4] : 28'(ct_sum<0 ? ct_sum+P29 : ct_sum);"
        need(text.count(old)==1,'ONE_MUTANT_OUTPUT_SITE')
        b['files'][name]=text.replace(old,"y0<=28'b0;")
        b['generated_sha256'][name]=sha(b['files'][name].encode())
    b=harness.native_wrapper_bundle(b,field)
    oldtop=b['top'];kind='zero' if mutant else ('ct' if enabled else 'parent')
    top=f'genefer_s4_l3b_{kind}_normal_aw{aw}_p16_f{field}_v1'
    b['files'][top+'.sv']=b['files'].pop(oldtop+'.sv').replace(oldtop,top)
    b['top']=top;b['rtl_sources']=[top+'.sv' if name==oldtop+'.sv' else name for name in b['rtl_sources']]
    text,header,counts,ledgers,footer=harness.compile_normal(b,field)
    marker=f'S4_L3B_{kind.upper()}_FIELD_PASS aw={aw} p=16 field={field}'
    text=text.replace(f'S4_R75_FIELD_PASS aw={aw} p=16 field={field}',marker)
    footer=footer.replace(f'S4_R75_FIELD_PASS aw={aw} p=16 field={field}',marker)
    files={'rtl/'+name:value.encode() for name,value in b['files'].items()}
    files.update({CPP:text.encode(),HEADER:header.encode(),REFERENCE:(ROOT/REFERENCE).read_bytes(),SELF:(ROOT/SELF).read_bytes()})
    if mutant:files[FAULT]=(ROOT/FAULT).read_bytes()
    from .stream27_shared_warm_full_native_v1 import BENCH
    for name in dict.fromkeys(b['source_dependencies']+[SELF,harness.SELF,
        'reference/stream27_shared_warm_full_native_v1.py','reference/stream27_p8_warm_native_v2.py',BENCH]):
        files['lineage/'+name]=(ROOT/name).read_bytes()
    ready_at=ready_at or datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    changed={name:sha(raw) for name,raw in files.items() if name.endswith('.sv')}
    ready=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=f'{FAMILY}-{kind}-aw{aw}-f{field}-v1',
        candidate_source_sha256=sha(canonical(changed)),rtl_ready_at_utc=ready_at,source_snapshot=changed)
    step=dict(name='l3b-'+kind+'-warm-field',argv=['{exe}'],expected_returncode=1 if mutant else 0)
    if mutant:step['validator']=dict(source=FAULT,function='validate',
        config=dict(aw=8,p=16,field=0,mutant='zero-ct-sum'),assets={})
    else:step.update(expected_stdout=footer,expected_stderr='')
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/not-a-dispatch-path/l3b/fpga',output_parent='/not-a-dispatch-path/l3b/output',
        sources={name:sha(raw) for name,raw in files.items()},
        build=dict(top=top,sv_sources=['rtl/'+name for name in b['rtl_sources']],cpp_source=CPP,
            parameters={key:value for key,value in b['parameters'].items() if key!='FIELD'},
            cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[step],test_role='deliberate_fault' if mutant else 'normal',rtl_readiness=ready,
        l3b_field=dict(enabled=enabled,mutant=mutant,geometry=b['geometry'],counts=counts,lease_ledger=ledgers,
            binding=production.get('l3b_ct_fused'),production_top=production['top'],
            production_generated_sha256=production['generated_sha256'],
            source_sha256=b['source_sha256'],scope='One composed P16 field only; no scalar-times-count area, whole clock or promotion inference.',
            full_N_numeric_locally_performed=False))
    return harness.preflight(manifest,files)


def prepare(output,aw=8,field=0,*,enabled=1,mutant=False):
    from fpga.tools import native_class_package_v2 as package
    from fpga.tools.candidate_ladder import budget_from_hourly
    output=Path(output).resolve()
    need(output.is_relative_to(ROOT) and not output.exists() and not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),'FRESH_PAUSE')
    m,files=role(aw,field,enabled=enabled,mutant=mutant)
    source=output/'input/source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as out:out.write(raw)
    manifest=output/'input/manifest.json';dump(manifest,m)
    budget=output/'host-hours.json';dump(budget,budget_from_hourly());variants=[]
    kind='zero' if mutant else ('ct' if enabled else 'parent')
    qid=f'{FAMILY}-{kind}-aw{aw}-p16-f{field}-q1-v1'
    for pair in ('01','23'):
        profile=f'gcp-c4d-static{pair}-v1';worker=f'l3b-{kind}-aw{aw}-f{field}-{pair}-v1';packet=output/('packet-'+pair)
        result=package.prepare(manifest,source,profile,worker,'run',packet,budget)
        variants.append(dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),
            sha256=result['archive_sha256'],ticket_sha256=result['ticket_sha256'],
            manifest_sha256=sha((packet/'manifest.json').read_bytes()),native_root=result['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/name),sha256=sha((ROOT/name).read_bytes()))
                for name in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    after=[]
    if mutant:after=[f'{FAMILY}-ct-aw8-p16-f0-q1-v1']
    elif aw==16 and enabled:after=[f'{FAMILY}-ct-aw8-p16-f{f}-q1-v1' for f in range(3)]
    ticket=dict(schema='gfn16-global-ticket-v1',id=qid,owner='independent-review',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=8 if aw==16 else 4,minimum_ram_rationale='Current fullN field8GiB; bounded small field4GiB, no measured peak inference.',
        est_minutes=10,promotion_bound=False,test_role=m['test_role'],packages=variants,rtl_readiness=m['rtl_readiness'])
    if after:ticket.update(after=after,on='PASS_expected_contracts')
    path=output/'global-ticket.json';dump(path,ticket)
    return dict(id=qid,ticket=str(path),status='source_prepared_not_native',rtl_ready_at=m['rtl_readiness']['rtl_ready_at_utc'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--aw',type=int,choices=(8,16),default=8);parser.add_argument('--field',type=int,choices=(0,1,2),default=0)
    parser.add_argument('--parent',action='store_true');parser.add_argument('--mutant',action='store_true')
    args=parser.parse_args();print(json.dumps(prepare(args.output,args.aw,args.field,enabled=0 if args.parent else 1,mutant=args.mutant),indent=2))

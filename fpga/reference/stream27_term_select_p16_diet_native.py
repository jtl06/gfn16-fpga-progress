"""Normal-first actual private-diet field selector gate; no shared writes."""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
import re
from . import stream27_host_chain_diet_qualification as donor
from . import stream27_term_select_p16_diet_bind as binding
from . import stream27_term_select_native as qualified

ROOT=qualified.ROOT
SELF='reference/stream27_term_select_p16_diet_native.py'
CPP='rtl/tb/stream27_term_select_p16_diet_normal.cpp'
need,sha,dump=qualified.need,qualified.sha,qualified.dump
RTL_READY='2026-10-01T23:29:19Z'


def field_bundle(aw=8,field=1):
    need(aw in (8,16) and field in (0,1,2),'P16_DIET_TERM_NORMAL_GEOMETRY')
    whole=donor.prepare(1<<aw,16,paired=False,contexts=1,canonical_pipe_stages=1,corr_serial_bfs=2,
                       comm_stage_shared_mlab=1,mont_factored=1,allow_full_constants=aw==16)
    roots=[name for name in whole['files'] if name.startswith('genefer_stream27_shared_warm_') and f'_f{field}_' in name]
    need(len(roots)==1,'P16_DIET_TERM_NORMAL_EXACT_FIELD');view=deepcopy(whole)
    view['top']=roots[0][:-3];view['mode']='warm_signed'
    return binding.bind(view)


def role(aw=8,field=1):
    b=field_bundle(aw,field);m,files,_=qualified.role(aw,16,field,corr_serial_bfs=2)
    need(b['geometry']==m['term_select']['geometry'],'P16_DIET_TERM_NORMAL_NO_HIDDEN_CALENDAR_CHANGE')
    files={name:raw for name,raw in files.items() if not(name.startswith('rtl/') and name.endswith('.sv'))}
    files.update({'rtl/'+name:text.encode() for name,text in b['files'].items()})
    production=b['top'];alias=f'genefer_stream27_p16_diet_term_field_aw{aw}_f{field}_r2'
    source=b['files'][production+'.sv'];declaration=source.split(') (',1)[0]
    allowed=set(re.findall(r'\b([A-Z][A-Z0-9_]*)=',declaration))
    params={key:value for key,value in b['parameters'].items() if key in allowed}
    ports=source.split(') (',1)[1].split(');',1)[0]
    paramtext=declaration.split('#(',1)[1]
    wrapper='module '+alias+' #('+paramtext+') ('+ports+');\n '+production+' #('+', '.join('.'+key+'('+key+')' for key in params)+') actual_field (.*);\nendmodule\n'
    # Native-only transparent alias avoids Verilator's internal long-name
    # hashing at --top-module. Production source stays byte-identical.
    need('always' not in wrapper and 'assign' not in wrapper,'P16_DIET_TERM_NATIVE_ALIAS_TRANSPARENT')
    b['files'][alias+'.sv']=wrapper;b['rtl_sources'].append(alias+'.sv')
    b['generated_sha256'][alias+'.sv']=sha(wrapper.encode());files['rtl/'+alias+'.sv']=wrapper.encode()
    bench=deepcopy(b);bench['top']=alias
    cpp,header=qualified.compile_bench(bench,field);label=f'S4_P16_DIET_TERM_SELECT_NORMAL aw={aw} p=16 field={field}'
    cpp=qualified.binding.once(cpp,'S4_SHARED_AW16_PASS',label)
    files.pop(qualified.CPP);files[CPP]=cpp.encode();files[qualified.HEADER]=header.encode()
    for name in b['source_dependencies']+[SELF]:files['lineage/'+name]=(ROOT/name).read_bytes()
    need(params.get('MONT_FACTORED')==1 and params.get('TERM_SELECT_TOKEN')==1,'P16_DIET_TERM_NORMAL_ACTUAL_PARAMS')
    counts=m['term_select']['counts'];footer=label+' '+' '.join(f'{k}={v}' for k,v in counts.items())+'\n'
    m.update(sources={name:sha(raw) for name,raw in files.items()},
        build=dict(top=alias,sv_sources=['rtl/'+name for name in b['rtl_sources']],cpp_source=CPP,parameters=params,
                   cflags=['-std=c++17','-O2','-Werror=return-type']),
        steps=[dict(name='private-p16-diet-term-selector-normal',argv=['{exe}'],expected_returncode=0,expected_stdout=footer,expected_stderr='')],
        term_select=dict(binding=b['term_select'],geometry=b['geometry'],counts=counts,native_alias=alias,production_root=production,
            scope='Actual private whole-diet field root/Mont/comm/corr2 plus selector, independent NTT/calendar; not sevenflag/whole/clock qualification.'))
    return m,files,{'rtl/'+name:pin for name,pin in b['generated_sha256'].items()}


def prepare(output,aw,field,budget):
    from fpga.tools import native_class_package_v2 as package
    output=Path(output).resolve()
    need(not output.exists() and not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),'P16_DIET_TERM_NORMAL_FRESH_PAUSE')
    m,files,snapshot=role(aw,field);source=output/'input/source/fpga';source.mkdir(parents=True)
    m['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=f's4-p16-diet-term-select-aw{aw}-f{field}-v1',
        candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),rtl_ready_at_utc=RTL_READY,source_snapshot=snapshot)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    manifest=output/'input/manifest.json';dump(manifest,m)
    qid=f's4-p16-diet-term-select-aw{aw}-f{field}-normal-q1-r2';profile='gcp-c4d-static01-v1';worker=qid+'-01';packet=output/'packet-01'
    r=package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve())
    variant=dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
        manifest_sha256=sha((packet/'manifest.json').read_bytes()),native_root=r['native_root'],runner='tools/native_class_package_v2.py',
        runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),stager=str(ROOT/'tools/native_package_v3.py'),
        stager_sha256=sha((ROOT/'tools/native_package_v3.py').read_bytes()),stager_dependencies=[dict(path=str(ROOT/'tools/native_package_v2.py'),sha256=sha((ROOT/'tools/native_package_v2.py').read_bytes()))],max_seconds=3700)
    ticket=dict(schema='gfn16-global-ticket-v1',id=qid,owner='term-select',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=8 if aw==16 else 4,minimum_ram_rationale='Existing bounded4GiB/fullN8GiB envelopes; no measured peak claim.',est_minutes=10,
        promotion_bound=False,test_role='normal',packages=[variant],rtl_readiness=m['rtl_readiness'])
    if aw==16:ticket.update(after=[f's4-p16-diet-term-select-aw8-f{field}-normal-q1-r2'],on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',ticket)
    return dict(status='normal_source_prepared_not_submitted',id=qid,ticket=str(output/'global-ticket-v1.json'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--budget',type=Path,required=True)
    p.add_argument('--aw',type=int,choices=(8,16),default=8);p.add_argument('--field',type=int,choices=(0,1,2),default=1)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.aw,a.field,a.budget),indent=2))

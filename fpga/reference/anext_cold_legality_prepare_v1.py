"""Source-closed cold legality normal/fault ladders; queue owns all execution."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from fpga.reference import anext_cold_legality_v1 as s
from fpga.reference import anext_cold_legality_fault_v1 as fault
from fpga.reference import anext_writeback_output_v1 as normal
from fpga.reference import anext_field_reset_prepare_v1 as shared

ROOT=s.ROOT
SELF='reference/anext_cold_legality_prepare_v1.py'
TEST='tests/test_anext_cold_legality_prepare_v1.py'
CPP='rtl/tb/track_anext_coldleg_core_v1.cpp'
OUTPUT='reference/anext_cold_legality_output_v1.py'
READY='results/throughput-20260929/anext-cold-legality-source-v1/rtl-ready.json'
ROLES={5:'427d71082ef57518da15820e3e8f4020ec285fe5d10e10165c1e46e9a0e480d5',
       8:'7895430da88f2706cccdef01d5d4a37fe0adf2b199151b7e40880309e08d7a2e'}

def dump(path,v):
    with path.open('x') as f:json.dump(v,f,indent=2);f.write('\n')

def normal_cpp():
    role=ROOT/'artifacts/anext-writeback-aw5-role-v1';m=json.loads((role/'manifest.json').read_text())
    s.need(s.sha((role/'manifest.json').read_bytes())==ROLES[5],'COLDLEG_NORMAL_PARENT_ROLE')
    raw=(role/'source/fpga'/m['build']['cpp_source']).read_bytes()
    s.need(s.sha(raw)==m['sources'][m['build']['cpp_source']],'COLDLEG_NORMAL_PARENT_CPP')
    t=raw.decode();old='genefer_anext_writeback_core_v1';new='genefer_anext_coldleg_core_v1'
    s.need(t.count(old)==2,'COLDLEG_TWO_NORMAL_BINDINGS')
    result=t.replace(old,new);s.need(result.replace(new,old)==t,'COLDLEG_NORMAL_NO_ORACLE_CHANGE');return result

def validate_normal(stdout,stderr,rc,config,assets):
    result=normal.validate(stdout,stderr,rc,config,assets)
    result.update(candidate='A-next-cold-source-legality-v1',normal_cycle_delta=0,new_numeric_fault_ABI=True)
    return result

def role(aw,kind):
    s.need(aw in ROLES and kind in ('normal','fault'),'COLDLEG_FINITE_ROLE');s.verify();fault.verify()
    s.need((ROOT/CPP).read_text()==normal_cpp(),'COLDLEG_EXACT_NORMAL_CPP')
    parent=ROOT/f'artifacts/anext-writeback-aw{aw}-role-v1'
    s.need(s.sha((parent/'manifest.json').read_bytes())==ROLES[aw],'COLDLEG_FROZEN_F3_ROLE')
    m=json.loads((parent/'manifest.json').read_text());files={}
    for name,pin in m['sources'].items():
        raw=(parent/'source/fpga'/name).read_bytes();s.need(s.sha(raw)==pin,'COLDLEG_PARENT_CLOSURE '+name);files[name]=raw
    for name in (*s.expected(),*fault.expected(),fault.CPP,CPP,SELF,TEST,OUTPUT,
       'reference/anext_cold_legality_v1.py','reference/anext_cold_legality_fault_v1.py','tests/test_anext_cold_legality_v1.py',READY):
        files[name]=(ROOT/name).read_bytes()
    repl={s.PARENT:s.TARGET,s.BACKEND_PARENT:s.BACKEND,s.CORE_PARENT:s.CORE}
    m['build']['sv_sources']=[repl.get(n,n) for n in m['build']['sv_sources']]
    m['build'].update(top='genefer_anext_coldleg_core_v1',cpp_source=CPP)
    if kind=='normal':
        for step in m['steps']:
            step['name']=f'coldleg-normal-aw{aw}';step['validator']['source']=OUTPUT;step['validator']['function']='validate'
    else:
        m['build'].update(top=fault.TOP,cpp_source=fault.CPP,cflags=['-std=c++17','-Werror=return-type',f'-DCOLDLEG_AW={aw}'])
        m['build']['sv_sources']=[fault.SV if n==s.CORE else fault.BACK if n==s.BACKEND else n for n in m['build']['sv_sources']]
        m['steps']=[dict(name='coldleg-'+case,argv=['{exe}',case],expected_returncode=int(case=='negative-edge'),
            validator=dict(source='reference/anext_cold_legality_fault_v1.py',function='validate',config=dict(aw=aw,case=case),assets={}))
            for case in (*fault.CASES,'negative-edge')]
    m.update(sources={n:s.sha(raw) for n,raw in files.items()},status='prepared_not_executed',
      cold_legality=dict(contract=s.contract(),rtl_readiness=json.loads((ROOT/READY).read_text()),
       raw_error_contract='Metadata/image/transfer/cancel stay immediate; full33 numeric check before destination/reduction. Valid earlier prefixes speculative until complete publication.',
       native_only_fixture=(kind=='fault'),whole_timing_proven=False,promotion_allowed=False))
    s.need(set(m['build']['sv_sources']+[m['build']['cpp_source']])<=files.keys(),'COLDLEG_COMPILED_CLOSURE')
    return m,files

def prepare(output,aw,kind,budget):
    output=Path(output).resolve();s.need(not output.exists(),'COLDLEG_FRESH_PACKET')
    s.need(not any((ROOT/n).exists() for n in ('docs/briefs/PAUSE','queue/PAUSE')),'COLDLEG_PAUSE')
    m,files=role(aw,kind);source=output/'input/source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    manifest=output/'input/manifest.json';dump(manifest,m);variants=[]
    for pair in ('01','23'):
        profile=f'gcp-c4d-static{pair}-v1';worker=f'anext-coldleg-{kind}-aw{aw}-{pair}-v2';packet=output/('packet-'+pair)
        r=shared.package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve())
        variants.append(dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],
          ticket_sha256=r['ticket_sha256'],manifest_sha256=s.sha((packet/'manifest.json').read_bytes()),native_root=r['native_root'],
          runner='tools/native_class_package_v2.py',runner_sha256=shared.PACKAGE_SHA,stager=str(ROOT/shared.STAGER),
          stager_sha256=shared.STAGER_SHA,stager_dependencies=[dict(path=str(ROOT/shared.COMPANION),sha256=shared.COMPANION_SHA)],max_seconds=3700))
    ticket=dict(schema='gfn16-global-ticket-v1',id=f'anext-coldleg-{kind}-aw{aw}-q1-v1',owner='merged-ntt-model',
      created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
      tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
      minimum_ram_gib=8,minimum_ram_rationale='Preserve passed F3 whole AW5/AW8 8GiB envelope; no inferred lower-cap claim.',
      est_minutes=5,promotion_bound=False,packages=variants,rtl_readiness=m['cold_legality']['rtl_readiness'])
    if aw==8:ticket.update(after=[f'anext-coldleg-{kind}-aw5-q1-v1'],on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',ticket);dump(output/'preparation.json',dict(aw=aw,kind=kind,source_files=len(files),native_executed=False,contract=s.contract()))
    return dict(id=ticket['id'],source_files=len(files),ticket=str(output/'global-ticket-v1.json'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--aw',type=int,choices=(5,8));p.add_argument('--kind',choices=('normal','fault'))
    p.add_argument('--output',type=Path);p.add_argument('--budget',type=Path);p.add_argument('--write-normal-cpp',action='store_true');a=p.parse_args()
    if a.write_normal_cpp:
        s.need(not (ROOT/CPP).exists(),'COLDLEG_NORMAL_CPP_FRESH')
        with (ROOT/CPP).open('x') as f:f.write(normal_cpp())
        print(s.sha((ROOT/CPP).read_bytes()))
    else:print(json.dumps(prepare(a.output,a.aw,a.kind,a.budget),indent=2))

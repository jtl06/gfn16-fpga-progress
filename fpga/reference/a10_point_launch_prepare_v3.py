"""Finite point-launch component qualification; no whole-core/fit dispatch."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from fpga.reference import a10_native_batch_prepare_v1 as batch
from fpga.reference import a10_point_launch_generate_v3 as gen

ROOT=gen.ROOT;CPP='rtl/tb/a10_point_launch_geometry_v3.cpp'
SELF='reference/a10_point_launch_prepare_v3.py';TEST='tests/test_a10_point_launch_prepare_v3.py'
PINS={gen.TARGET:'087bb158c0f493e22ed8e49372e233928979ed2161eff11f21f4510d2888c646',
      CPP:'527ea82a6fd8eb9b313e3687aca5fe0ebf35b628d4b437fe3eccd5a61f4b181d',
      'reference/a10_point_launch_generate_v3.py':'d77e514da011a0a4c1a4711a714fc173415a9d1728654bf86ffbde1643cd22c8'}


def verify():
    gen.parent.need((ROOT/gen.TARGET).read_text()==gen.source(),'A10_POINT_GENERATED_SOURCE')
    for name,pin in PINS.items():gen.parent.need(gen.sha((ROOT/name).read_bytes())==pin,'A10_POINT_SOURCE_DRIFT '+name)


def role(aw,field):
    gen.parent.need(type(aw) is int and aw in (5,8) and type(field) is int and field in (0,1,2),'A10_POINT_FINITE_ROLE')
    verify();m,files=batch.donor();f=batch.old.math.FIELDS[field]
    if aw==8:
        binding=batch.old.gen.lookup_binding(256,64)
        normal='\n'.join(x['source'] for x in binding['compiled'])+'\n'+binding['source']
        lookup='rtl/kernel/a10_packed_lookup_aw8_lint_bound_v2.sv';files[lookup]=batch.repair.repair_lookup(normal,8).encode()
        m['build']['sv_sources']=[lookup if x.endswith('/a10_packed_lookup_aw5_lint_bound_v2.sv') else x for x in m['build']['sv_sources']]
    for name in (*PINS,SELF,TEST,'tests/test_a10_point_launch_generate_v3.py',gen.LEDGER,gen.FITTED):files[name]=(ROOT/name).read_bytes()
    m['build']['sv_sources']=[gen.TARGET if x==batch.repair.ENGINE_V2 else x for x in m['build']['sv_sources']]
    m['build']['parameters'].update(AW=aw,P=f.p,Q=f.q);m['build']['cpp_source']=CPP
    m['build']['cflags']=['-std=c++17','-Werror=return-type',f'-DA10_AW={aw}',f'-DA10_P={f.p}',f'-DA10_G={f.generator}']
    counts=gen.ledger(aw)
    positive=f'A10_POINT_ENGINE_PASS aw={aw} field={f.p} cases=5 operations=15 residues={counts["residues"]} cycles={counts["engine_work_cycles"]} profile_words=4\n'
    m['steps']=[dict(name='point-launch-normal',argv=['{exe}'],expected_returncode=0,expected_stdout=positive,expected_stderr=''),
                dict(name='point-launch-negative-counter',argv=['{exe}','--negative-counter'],expected_returncode=1,
                     expected_stdout='',expected_stderr='A10_POINT_COUNTER_NEGATIVE_REJECT\n')]
    m['sources']={name:gen.sha(raw) for name,raw in files.items()};m.pop('lint_baseline',None)
    m['source_root']='/not-a-dispatch-path/a10-point-launch/fpga';m['output_parent']='/not-a-dispatch-path/a10-point-launch/output'
    m['scope']='Pointwise-only RAM launch successor, canonical A10 component; BF/root/profile/host ABI unchanged; not whole A-next/fit/clock/promotion.'
    m['point_launch']=dict(source_pins=PINS,measured_parent_ledger_sha256=gen.LEDGER_SHA,
        source_only_ledger=counts,change='Point operand/valid/row+half tags+1 edge; payload32bit canonical domain unchanged',
        unchanged='All frozen arithmetic, root constants/domain/order/form, profile3, BF timing and external host/read ABI.',
        current_A_next_engine_not_changed=True,native_executed=False,full_N_numeric_locally_performed=False)
    gen.parent.need(set(m['build']['sv_sources']+[CPP])<=files.keys(),'A10_POINT_COMPILED_CLOSURE')
    return m,files


def prepare(output,aw,field,budget):
    gen.parent.need(not any((ROOT/n).exists() for n in ('docs/briefs/PAUSE','queue/PAUSE')),'A10_POINT_PAUSE')
    output=Path(output).resolve();gen.parent.need(not output.exists(),'A10_POINT_FRESH_OUTPUT')
    m,files=role(aw,field);source=output/'input/source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    def dump(path,value):
        with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    manifest=output/'input/manifest.json';dump(manifest,m);variants=[]
    for pair in ('01','23'):
        profile=f'gcp-c4d-static{pair}-v1';worker=f'a10-point-aw{aw}-f{field}-{pair}-v3';packet=output/('packet-'+pair)
        result=batch.package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve())
        variants.append(dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'],manifest_sha256=gen.sha((packet/'manifest.json').read_bytes()),
            native_root=result['native_root'],runner='tools/native_class_package_v2.py',runner_sha256=batch.PACKAGE_SHA,
            stager=str(ROOT/'tools/native_package_v3.py'),stager_sha256='5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9',
            stager_dependencies=[dict(path=str(ROOT/'tools/native_package_v2.py'),sha256='3f2186fa5aac8129ac1ad5a161de39cf221925ee95d5de6364a941b199e7279a')],max_seconds=3700))
    qid=f'a10-point-aw{aw}-f{field}-q1-v3';ticket=dict(schema='gfn16-global-ticket-v1',id=qid,owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=4,minimum_ram_rationale='Explicit bounded4GiB exploration for N<=256 unchanged passedA10 arithmetic+one32bitpointlaunchregister perlane; not a measured requirement. Preserve failures/no automaticretry; desired8GiB.',
        est_minutes=5,promotion_bound=False,packages=variants)
    if aw==8:ticket.update(after=[f'a10-point-aw5-f{i}-q1-v3' for i in (0,1,2)],on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',ticket)
    summary=dict(schema='a10-point-launch-preparation-v3',status='source_ready_not_dispatched',aw=aw,field=field,
        source_files=len(files),source_pins=PINS,variants=variants,HDL_or_native_executed=False,promotion_allowed=False)
    dump(output/'preparation.json',summary);verify();return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aw',type=int,choices=(5,8),required=True);parser.add_argument('--field',type=int,choices=(0,1,2),required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.output,args.aw,args.field,args.budget),indent=2))

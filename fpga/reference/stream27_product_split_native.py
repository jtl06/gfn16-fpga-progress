"""Normal-first split/parent canonical+lazy scalar comparison on workers."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from . import stream27_product_split as s
from . import stream27_l3_factored_native_v1 as donor

ROOT=s.ROOT
SELF='reference/stream27_product_split_native.py'
TOP='genefer_stream27_product_split_pair_v1'
PAIR='rtl/tb/'+TOP+'.sv'
CPP='rtl/tb/stream27_product_split_pair_v1.cpp'
FAMILY='s4-product-split'

def pair():
    text=donor.PAIR_TEXT.replace(donor.TOP,TOP)
    text=text.replace('genefer_stream27_montgomery28x27_factored_v1 #','genefer_stream27_product_split_lazy_v1 #',1)
    text=text.replace('genefer_stream27_montgomery_factored_v1 #','genefer_stream27_product_split_v1 #',1)
    text=text.replace('genefer_montgomery_mul28x27_sparse_pipe_v2 #','genefer_stream27_montgomery28x27_factored_v1 #')
    text=text.replace('genefer_montgomery_mul27_sparse_pipe #','genefer_stream27_montgomery_factored_v1 #')
    return text

def cpp():
    return donor.cpp().replace(donor.TOP,TOP).replace('PASS_L3_FACTORED','PASS_PRODUCT_SPLIT')

def dump(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2);f.write('\n')

def role(field=0,*,mutant=False):
    s.need(type(field) is int and field in (0,1,2),'FIELD');proof=s.verify_source()
    s.need(type(mutant) is bool and (not mutant or field==0),'MUTANT_FIELD')
    p=list(s.model.FIELDS)[field]
    files={PAIR:pair().encode(),CPP:cpp().encode(),s.RTL:(ROOT/s.RTL).read_bytes(),
        s.PARENT:(ROOT/s.PARENT).read_bytes(),SELF:(ROOT/SELF).read_bytes(),s.SELF:(ROOT/s.SELF).read_bytes(),
        'reference/stream27_l3_factored_model_v1.py':(ROOT/'reference/stream27_l3_factored_model_v1.py').read_bytes()}
    if mutant:
        text=files[s.RTL].decode();old="23'(overlap_sum[5])"
        s.need(text.count(old)==1,'ONE_CARRY_FAULT_SITE');files[s.RTL]=text.replace(old,"23'b0").encode()
    ready=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=f'{FAMILY}-f{field}-v1',
        rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        source_snapshot={n:s.sha(raw) for n,raw in files.items() if n.endswith('.sv')})
    ready['candidate_source_sha256']=s.sha(json.dumps(ready['source_snapshot'],sort_keys=True,separators=(',',':')).encode())
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/not-a-dispatch-path/product-split/fpga',output_parent='/not-a-dispatch-path/product-split/output',
        sources={n:s.sha(raw) for n,raw in files.items()},
        build=dict(top=TOP,sv_sources=[PAIR,s.RTL,s.PARENT],cpp_source=CPP,
            parameters=dict(P=p,Q=(2-p)%(1<<32)),cflags=['-std=c++17','-Werror=return-type',f'-DTEST_P={p}']),
        probe=dict(argv=['{exe}','--thread-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='split-carry-zero-fault' if mutant else 'split-parent-four-cell-normal',argv=['{exe}'],
            expected_returncode=1 if mutant else 0,
            expected_stderr='MONT28_ARITHMETIC_MISMATCH edge=35\n' if mutant else '',
            expected_stdout='' if mutant else f'PASS_PRODUCT_SPLIT P={p} checked=16925 canceled=224 holds=3166 high_inputs={donor.HIGH[p]} edges=20091 outputs=4\n')],
        test_role='deliberate_fault' if mutant else 'normal',rtl_readiness=ready,product_split=dict(field=field,proof=proof,mutant=mutant,
            independent_checks=67700,latency=3,II=1,scope='Scalar normal arithmetic, bubbles/reset/holds; not field area or clock.'))
    return m,files

def prepare(output,field=0,*,mutant=False):
    from fpga.tools import native_class_package_v2 as package
    from fpga.tools.candidate_ladder import budget_from_hourly
    output=Path(output).resolve();s.need(output.is_relative_to(ROOT) and not output.exists(),'FRESH_OUTPUT')
    s.need(not any((ROOT/n).exists() for n in ('docs/briefs/PAUSE','queue/PAUSE')),'PAUSE')
    m,files=role(field,mutant=mutant);source=output/'input/source/fpga';source.mkdir(parents=True)
    for n,raw in files.items():
        path=source/n;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as f:f.write(raw)
    manifest=output/'input/manifest.json';dump(manifest,m)
    budget=output/'host-hours.json';dump(budget,budget_from_hourly());variants=[]
    for lane in ('01','23'):
        profile=f'gcp-c4d-static{lane}-v1';worker=f'product-split-f{field}-'+('carryzero-' if mutant else '')+f'{lane}-v1';packet=output/('packet-'+lane)
        result=package.prepare(manifest,source,profile,worker,'run',packet,budget)
        variants.append(dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'],manifest_sha256=s.sha((packet/'manifest.json').read_bytes()),native_root=result['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=s.sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=s.sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/n),sha256=s.sha((ROOT/n).read_bytes()))
                for n in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    ticket=dict(schema='gfn16-global-ticket-v1',id=f'{FAMILY}-f{field}-'+('carryzero' if mutant else 'normal')+'-q1-v1',owner='independent-review',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=4,minimum_ram_rationale='Bounded four-scalar-cell comparison, no fullN or measured peak extrapolation.',
        est_minutes=2,promotion_bound=False,test_role=m['test_role'],packages=variants,rtl_readiness=m['rtl_readiness'])
    if mutant:ticket.update(after=[f'{FAMILY}-f0-normal-q1-v1'],on='PASS_expected_contracts')
    path=output/'global-ticket.json';dump(path,ticket)
    return dict(id=ticket['id'],ticket=str(path),status='prepared_not_executed')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--field',type=int,choices=(0,1,2),default=0);p.add_argument('--mutant',action='store_true')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.field,mutant=a.mutant),indent=2))

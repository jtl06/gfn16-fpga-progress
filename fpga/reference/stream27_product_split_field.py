"""One private lazy-only composed P16 field normal/fault; native math only."""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
from . import stream27_product_split as s
from . import stream27_shared_field_flags as core
from . import stream27_timing_field_native as harness

ROOT=s.ROOT
SELF='reference/stream27_product_split_field.py'
CPP='rtl/tb/stream27_product_split_field.cpp'
HEADER='rtl/tb/s4_full_config_v1.h'
FAMILY='s4-product-split-field'

def bundle(aw=8):
    s.need(type(aw) is int and aw in (8,16),'FIELD_AW')
    return s.bind(core.prepare(1<<aw,16,0,mode='warm',contexts=1,allow_full_constants=aw==16,
        corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1),enabled=1)

def dump(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2);f.write('\n')

def role(aw=8,*,mutant=False):
    s.need(type(mutant) is bool and (not mutant or aw==8),'FIELD_FAULT_SCOPE')
    s.need(s.sha((ROOT/harness.REFERENCE).read_bytes())==harness.REFERENCE_PIN,'FROZEN_REFERENCE')
    b=bundle(aw);production=deepcopy(b)
    if mutant:
        name=Path(s.RTL).name;old="23'(overlap_sum[5])";s.need(b['files'][name].count(old)==1,'FIELD_ONE_FAULT')
        b['files'][name]=b['files'][name].replace(old,"23'b0");b['generated_sha256'][name]=s.sha(b['files'][name].encode())
    b=harness.native_wrapper_bundle(b,0);oldtop=b['top'];kind='carryzero' if mutant else 'normal'
    top=f'genefer_product_split_field_{kind}_aw{aw}_p16_f0_v1'
    b['files'][top+'.sv']=b['files'].pop(oldtop+'.sv').replace(oldtop,top);b['top']=top
    b['rtl_sources']=[top+'.sv' if n==oldtop+'.sv' else n for n in b['rtl_sources']]
    text,header,counts,ledgers,footer=harness.compile_normal(b,0)
    marker=f'S4_PRODUCT_SPLIT_FIELD_PASS aw={aw} p=16 field=0'
    text=text.replace(f'S4_R75_FIELD_PASS aw={aw} p=16 field=0',marker)
    footer=footer.replace(f'S4_R75_FIELD_PASS aw={aw} p=16 field=0',marker)
    files={'rtl/'+n:t.encode() for n,t in b['files'].items()}
    files.update({CPP:text.encode(),HEADER:header.encode(),harness.REFERENCE:(ROOT/harness.REFERENCE).read_bytes(),SELF:(ROOT/SELF).read_bytes()})
    from .stream27_shared_warm_full_native_v1 import BENCH
    for n in dict.fromkeys(b['source_dependencies']+[SELF,harness.SELF,
        'reference/stream27_shared_warm_full_native_v1.py','reference/stream27_p8_warm_native_v2.py',BENCH]):
        files['lineage/'+n]=(ROOT/n).read_bytes()
    if mutant:files['reference/stream27_product_split_field_fault.py']=(ROOT/'reference/stream27_product_split_field_fault.py').read_bytes()
    snapshot={n:s.sha(raw) for n,raw in files.items() if n.endswith('.sv')}
    ready=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=f'{FAMILY}-{kind}-aw{aw}-v1',
        candidate_source_sha256=s.sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
        rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),source_snapshot=snapshot)
    step=dict(name='product-split-field-'+kind,argv=['{exe}'],expected_returncode=1 if mutant else 0)
    if mutant:step['validator']=dict(source='reference/stream27_product_split_field_fault.py',function='validate',config={},assets={})
    else:step.update(expected_stdout=footer,expected_stderr='')
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/not-a-dispatch-path/product-split-field/fpga',output_parent='/not-a-dispatch-path/product-split-field/output',
        sources={n:s.sha(raw) for n,raw in files.items()},build=dict(top=top,sv_sources=['rtl/'+n for n in b['rtl_sources']],
            cpp_source=CPP,parameters={k:v for k,v in b['parameters'].items() if k!='FIELD'},cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[step],test_role='deliberate_fault' if mutant else 'normal',rtl_readiness=ready,
        product_split_field=dict(mutant=mutant,geometry=b['geometry'],counts=counts,lease_ledger=ledgers,
            binding=production['product_split'],production_top=production['top'],production_generated_sha256=production['generated_sha256'],
            full_N_numeric_locally_performed=False,scope='One F0 P16 field, lazy-only product mapping. No CRT/carry/host/whole claim.'))
    return harness.preflight(m,files)

def prepare(output,aw=8,*,mutant=False):
    from fpga.tools import native_class_package_v2 as package
    from fpga.tools.candidate_ladder import budget_from_hourly
    output=Path(output).resolve();s.need(output.is_relative_to(ROOT) and not output.exists(),'FIELD_FRESH')
    s.need(not any((ROOT/n).exists() for n in ('docs/briefs/PAUSE','queue/PAUSE')),'PAUSE')
    m,files=role(aw,mutant=mutant);source=output/'input/source/fpga';source.mkdir(parents=True)
    for n,raw in files.items():
        p=source/n;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    manifest=output/'input/manifest.json';dump(manifest,m);budget=output/'host-hours.json';dump(budget,budget_from_hourly());variants=[]
    kind='carryzero' if mutant else 'normal';qid=f'{FAMILY}-aw{aw}-f0-{kind}-q1-v1'
    for lane in ('01','23'):
        profile=f'gcp-c4d-static{lane}-v1';worker=f'product-split-field-aw{aw}-{kind}-{lane}-v1';packet=output/('packet-'+lane)
        r=package.prepare(manifest,source,profile,worker,'run',packet,budget)
        variants.append(dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],
            ticket_sha256=r['ticket_sha256'],manifest_sha256=s.sha((packet/'manifest.json').read_bytes()),native_root=r['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=s.sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=s.sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/n),sha256=s.sha((ROOT/n).read_bytes())) for n in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    ticket=dict(schema='gfn16-global-ticket-v1',id=qid,owner='independent-review',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8 if aw==16 else 4,
        minimum_ram_rationale='One fullN field8GiB; bounded N2564GiB, no whole memory extrapolation.',
        est_minutes=10,promotion_bound=False,test_role=m['test_role'],packages=variants,rtl_readiness=m['rtl_readiness'])
    if aw==16 or mutant:ticket.update(after=[f'{FAMILY}-aw8-f0-normal-q1-v1'],on='PASS_expected_contracts')
    path=output/'global-ticket.json';dump(path,ticket);return dict(id=qid,ticket=str(path))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--aw',type=int,choices=(8,16),default=8);p.add_argument('--mutant',action='store_true')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.aw,mutant=a.mutant),indent=2))

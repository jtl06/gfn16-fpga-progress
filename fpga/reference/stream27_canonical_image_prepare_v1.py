"""Prepare minimal immutable AW5/AW8 P8/P16 barrier jobs; never dispatch."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

from fpga.reference import stream27_canonical_image_native_v1 as native
from fpga.tools import native_class_package_v2 as package
from fpga.tools import native_class_v1 as executor

ROOT=native.ROOT
SELF='reference/stream27_canonical_image_prepare_v1.py'
NATIVE='reference/stream27_canonical_image_native_v1.py'
TESTS=('tests/test_stream27_canonical_image_model_v1.py','tests/test_stream27_canonical_image_prepare_v1.py')
PACKAGE_SHA='03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604'
STAGER='tools/native_package_v3.py'
STAGER_SHA='5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'
COMPANION='tools/native_package_v2.py'
COMPANION_SHA='3f2186fa5aac8129ac1ad5a161de39cf221925ee95d5de6364a941b199e7279a'


def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':')).encode()


def role(aw,p):
    native.verify();native.contracts(aw,p)
    names=(*native.PINS,NATIVE,SELF,*TESTS)
    files={name:(ROOT/name).read_bytes() for name in names}
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/not-a-dispatch-path/canonical/fpga',output_parent='/not-a-dispatch-path/canonical/output',
        sources={name:native.sha(raw) for name,raw in files.items()},
        build=dict(top=native.TOP,sv_sources=[native.RAM,native.SV],cpp_source=native.CPP,
            parameters=dict(AW=aw,P=p),cflags=['-std=c++17','-Werror=return-type',f'-DCANON_AW={aw}',f'-DCANON_P={p}']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[],scope='Materialized canonical-image readback barrier only; outside warm recurrence; not whole-core/physical/promotion.',
        canonical_image=dict(geometry=native.model.geometry(aw,p),ledger=native.model.protocol_ledger(aw,p),
            source_pins=native.PINS,oracle='native independent whole-X cpp_int modulo b^N+1',
            native_executed=False,full_N_numeric_locally_performed=False))
    for negative in (False,True):
        m['steps'].append(dict(name='canonical-negative-oracle' if negative else 'canonical-normal',
            argv=['{exe}']+(['--negative-oracle'] if negative else []),expected_returncode=int(negative),
            validator=dict(source=NATIVE,function='validate',config=dict(aw=aw,p=p,negative=negative),assets={})))
    return m,files


def dump(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def prepare(output,aw,p,budget):
    native.model.need(not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),'CANON_PAUSE')
    for name,pin in (('tools/native_class_package_v2.py',PACKAGE_SHA),(STAGER,STAGER_SHA),(COMPANION,COMPANION_SHA)):
        native.model.need(native.sha((ROOT/name).read_bytes())==pin,'CANON_SHARED_TOOL_DRIFT '+name)
    output=Path(output).resolve();native.model.need(not output.exists(),'CANON_FRESH_OUTPUT')
    m,files=role(aw,p);source=output/'input/source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    manifest=output/'input/manifest.json';dump(manifest,m)
    variants=[]
    for pair in ('01','23'):
        profile=f'gcp-c4d-static{pair}-v1';worker=f's4-canonical-aw{aw}-p{p}-{pair}-v1';packet=output/('packet-'+pair)
        prepared=package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve())
        variants.append(dict(profile=profile,worker_id=worker,packet=str(packet),archive=str(packet/'package.tar.gz'),
            sha256=prepared['archive_sha256'],ticket_sha256=prepared['ticket_sha256'],
            manifest_sha256=native.sha((packet/'manifest.json').read_bytes()),native_root=prepared['native_root'],
            build_key=prepared['build_key'],archive_bytes=prepared['archive_bytes'],
            resource_profile_sha256=native.sha(canonical(executor.profile(profile))),
            runner='tools/native_class_package_v2.py',runner_sha256=PACKAGE_SHA,
            stager=str(ROOT/STAGER),stager_sha256=STAGER_SHA,
            stager_dependencies=[dict(path=str(ROOT/COMPANION),sha256=COMPANION_SHA)],max_seconds=3700))
    a,b=[json.loads((Path(v['packet'])/'manifest.json').read_text()) for v in variants]
    native.model.need(all(a[k]==b[k] for k in ('sources','build','probe','steps')),'CANON_DUAL_IDENTITY')
    result=dict(schema='s4-canonical-image-dual-v1',status='source_ready_not_dispatched',aw=aw,p=p,
        variants=variants,source_files=len(a['sources']),source_pins=native.PINS,
        source_map_sha256=native.sha(canonical(a['sources'])),select_exactly_one=True,
        promotion_allowed=False,HDL_or_native_executed=False,full_N_numeric_locally_performed=False)
    dump(output/'preparation.json',result)
    qid=f's4-canonical-aw{aw}-p{p}-q1-v1'
    ticket=dict(schema='gfn16-global-ticket-v1',id=qid,owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
        minimum_ram_rationale='Explicit bounded exploratory4GiB allowance for two-RTL standalone barrier N<=256 with native-only bigint oracle; not measured requirement. Preserve failure, no automatic retry. Desired8GiB unchanged.',
        est_minutes=5,promotion_bound=False,packages=variants)
    if aw==8:ticket.update(after=[f's4-canonical-aw5-p{p}-q1-v1'],on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',ticket);native.verify()
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aw',type=int,choices=(5,8),required=True)
    parser.add_argument('--p',type=int,choices=(8,16),required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.output,args.aw,args.p,args.budget),indent=2))

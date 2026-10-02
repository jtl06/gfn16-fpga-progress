"""Immutable paired-P16 -> signed-P8 small arithmetic packets; no local HDL."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from . import stream27_threefield_carry_param_native_v1 as native
from . import stream27_threefield_carry_param_v1 as compiler
from . import stream27_threefield_carry_v1 as old_compiler
from fpga.tools import native_class_package_v2 as package
from fpga.tools import native_class_v1 as executor

ROOT=native.ROOT
SELF='reference/stream27_threefield_carry_param_prepare_v1.py'
NATIVE='reference/stream27_threefield_carry_param_native_v1.py'
REPLAY='reference/stream27_threefield_carry_param_replay_v1.py'
TESTS=('tests/test_stream27_threefield_carry_param_v1.py','tests/test_stream27_threefield_carry_param_replay_v1.py')
PACKAGE_SHA='03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604'
STAGER='tools/native_package_v3.py'
STAGER_SHA='5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'
COMPANION='tools/native_package_v2.py'
COMPANION_SHA='3f2186fa5aac8129ac1ad5a161de39cf221925ee95d5de6364a941b199e7279a'

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def identifier(aw,p):
    native.arguments(aw,p);return f's4-param-carry-aw{aw}-p{p}-q1-v1'

def role(aw,p):
    n=native.arguments(aw,p);native.verify()
    b=compiler.prepare(n,p,mode='warm_signed' if p==8 else 'warm');old=old_compiler.prepare(n) if p==16 else None
    files={'rtl/'+name:text.encode() for name,text in b['files'].items()}
    if old:
        for name,text in old['files'].items():
            key='rtl/'+name;native.need(key not in files or files[key]==text.encode(),'S4_PARAM_PAIRED_SOURCE_COLLISION');files[key]=text.encode()
    cpp,header=native.compile_bench(b);files[native.CPP]=cpp.encode();files[native.HEADER]=header.encode()
    files['rtl/'+native.PROBE+'.sv']=native.probe_source(b,old).encode()
    for name in dict.fromkeys(b['source_dependencies']+(old['source_dependencies'] if old else [])+[native.BENCH,*native.PINS]):
        files['lineage/'+name]=(ROOT/name).read_bytes()
    for name in (SELF,NATIVE,REPLAY,*TESTS):files[name]=(ROOT/name).read_bytes()
    generated={name.removeprefix('rtl/'):native.sha(raw) for name,raw in files.items() if name.startswith('rtl/') and name.endswith('.sv')}
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/not-a-dispatch-path/param-carry/fpga',output_parent='/not-a-dispatch-path/param-carry/output',
        sources={name:native.sha(raw) for name,raw in files.items()},
        build=dict(top=native.PROBE,sv_sources=['rtl/'+name for name in generated],cpp_source=native.CPP,
            parameters=dict(AW=aw,P=p,CONTEXTS=1),cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),steps=[],
        carry_param=dict(aw=aw,p=p,counts=native.counts(aw,p),geometry=b['geometry'],generated_sha256=generated,
            core_generated_sha256=b['generated_sha256'],source_sha256=b['source_sha256'],mode=b['mode'],
            paired_P16=bool(old),native_executed=False,full_N_numeric_locally_performed=False,
            oracle='Independent signed128 negacyclic schoolbook + SERIAL Euclidean block carry; actual digit/correction feedback.',
            ownership='Independent post-edge lease count starts through sink+T-2; pre-edge admission and last-sink release semantics. All3 fields must agree.',
            scope='Intermediate component gate; monitor wrapper exposes existing owner signals, and P16 additionally compares frozen full arithmetic parent. No host/canonical/PRP/clock promise.'))
    for mode,flag in (('normal',None),('minimum','--minimum'),('oracle','--negative-oracle'),('owner','--negative-owner')):
        manifest['steps'].append(dict(name='param-carry-'+mode,argv=['{exe}']+([flag] if flag else []),
            expected_returncode=int(mode in ('oracle','owner')),validator=dict(source=NATIVE,function='validate',config=dict(aw=aw,p=p,mode=mode),assets={})))
    return manifest,files

def dump(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')

def prepare(output,aw,p,budget):
    native.need(not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),'S4_PARAM_PAUSE')
    for name,pin in (('tools/native_class_package_v2.py',PACKAGE_SHA),(STAGER,STAGER_SHA),(COMPANION,COMPANION_SHA)):
        native.need(native.sha((ROOT/name).read_bytes())==pin,'S4_PARAM_SHARED_TOOL_DRIFT '+name)
    output=Path(output).resolve();native.need(not output.exists(),'S4_PARAM_FRESH_OUTPUT');manifest,files=role(aw,p)
    source=output/'input/source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    path=output/'input/manifest.json';dump(path,manifest);variants=[]
    for pair in ('01','23'):
        profile=f'gcp-c4d-static{pair}-v1';worker=f's4-param-carry-aw{aw}-p{p}-{pair}-v1';packet=output/('packet-'+pair)
        prepared=package.prepare(path,source,profile,worker,'run',packet,Path(budget).resolve())
        variants.append(dict(profile=profile,worker_id=worker,packet=str(packet),archive=str(packet/'package.tar.gz'),
            sha256=prepared['archive_sha256'],ticket_sha256=prepared['ticket_sha256'],manifest_sha256=native.sha((packet/'manifest.json').read_bytes()),
            native_root=prepared['native_root'],build_key=prepared['build_key'],archive_bytes=prepared['archive_bytes'],
            resource_profile_sha256=native.sha(canonical(executor.profile(profile))),runner='tools/native_class_package_v2.py',runner_sha256=PACKAGE_SHA,
            stager=str(ROOT/STAGER),stager_sha256=STAGER_SHA,stager_dependencies=[dict(path=str(ROOT/COMPANION),sha256=COMPANION_SHA)],max_seconds=3700))
    first,second=[json.loads((Path(item['packet'])/'manifest.json').read_text()) for item in variants]
    native.need(all(first[k]==second[k] for k in ('sources','build','probe','steps')),'S4_PARAM_DUAL_IDENTITY')
    result=dict(schema='s4-param-carry-dual-v1',status='source_ready_not_dispatched',aw=aw,p=p,variants=variants,
        source_files=len(first['sources']),source_map_sha256=native.sha(canonical(first['sources'])),
        generated_sha256=manifest['carry_param']['generated_sha256'],geometry=manifest['carry_param']['geometry'],
        select_exactly_one=True,promotion_allowed=False,HDL_or_native_executed=False,full_N_numeric_locally_performed=False)
    dump(output/'preparation.json',result)
    ticket=dict(schema='gfn16-global-ticket-v1',id=identifier(aw,p),owner='canonical-native-bench',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
        minimum_ram_rationale='Finite AW5/AW8 only, exploratory4GiB permitted, desired8GiB retained; source-pinned actual memory failure is preserved.',
        est_minutes=5,promotion_bound=False,packages=variants)
    dependencies=[]
    if p==8:dependencies.append(identifier(aw,16))
    if aw==8:dependencies.append(identifier(5,p))
    if dependencies:ticket.update(after=dependencies,on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',ticket);native.verify();return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--aw',type=int,choices=(5,8),required=True)
    parser.add_argument('--p',type=int,choices=(8,16),required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.output,args.aw,args.p,args.budget),indent=2))

"""Two immutable host-pair roles AW5→AW8; global dispatcher alone launches."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from fpga.reference import anext_cancel_native_v1 as native
from fpga.tools import native_class_package_v2 as package

ROOT=native.ROOT
SELF='reference/anext_cancel_prepare_v1.py'
NATIVE='reference/anext_cancel_native_v1.py'
REPLAY='reference/anext_cancel_replay_v1.py'
TESTS=('tests/test_anext_cancel_distribution_v1.py','tests/test_anext_cancel_prepare_v1.py',
       'tests/test_anext_cancel_host_pair_v1.py')
PACKAGE_SHA='03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604'
STAGER='tools/native_package_v3.py'
STAGER_SHA='5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'
COMPANION='tools/native_package_v2.py'
COMPANION_SHA='3f2186fa5aac8129ac1ad5a161de39cf221925ee95d5de6364a941b199e7279a'


def role(aw):
    native.counts(aw);native.verify()
    names=(*native.PINS,NATIVE,SELF,REPLAY,*TESTS,'reference/__init__.py',
           native.gen.MEASURED+'/receipt.json')
    files={name:(ROOT/name).read_bytes() for name in names}
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/not-a-dispatch-path/anext-cancel/fpga',output_parent='/not-a-dispatch-path/anext-cancel/output',
        sources={name:native.gen.sha(raw) for name,raw in files.items()},
        build=dict(top=native.TOP,sv_sources=native.SV_SOURCES,cpp_source=native.CPP,parameters=dict(AW=aw),
            cflags=['-std=c++17','-Werror=return-type',f'-DANEXT_CANCEL_AW={aw}']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[],scope='Isolated measured upper host cancel-payload successor paired against real frozen host/RAM. External square disabled; source cycle-neutral, recovery untouched, no whole clock/promotion.',
        cancel_distribution=dict(source_pins=native.PINS,ledger=native.gen.ledger(),source_derived_counts=native.counts(aw),
            independent_oracle='Ordinary int64 Euclidean signed-image/base normalization plus direct actual RAM checks; no control/scheduler or field arithmetic reused.',
            fault_scope='Four actual host/canonical overlap/fault/held-response seams; seven standalone atomic faults/eight cancel transactions; reset retention/reload. Same-edge kill, not rollback.',
            native_executed=False,numeric_full_N_locally_performed=False))
    for negative in (False,True):
        manifest['steps'].append(dict(name='cancel-negative-oracle' if negative else 'cancel-host-normal',
            argv=['{exe}']+(['--negative-oracle'] if negative else []),expected_returncode=int(negative),
            validator=dict(source=NATIVE,function='validate',config=dict(aw=aw,negative=negative),assets={})))
    native.gen.need(set(native.SV_SOURCES+[native.CPP])<=files.keys(),'ANEXT_CANCEL_CLOSED_COMPILED_SOURCES')
    return manifest,files


def dump(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def prepare(output,aw,budget):
    native.gen.need(not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),'ANEXT_CANCEL_PAUSE')
    for name,pin in (('tools/native_class_package_v2.py',PACKAGE_SHA),(STAGER,STAGER_SHA),(COMPANION,COMPANION_SHA)):
        native.gen.need(native.gen.sha((ROOT/name).read_bytes())==pin,'ANEXT_CANCEL_SHARED_TOOL '+name)
    output=Path(output).resolve();native.gen.need(not output.exists(),'ANEXT_CANCEL_FRESH_OUTPUT')
    manifest,files=role(aw);source=output/'input/source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    path=output/'input/manifest.json';dump(path,manifest);variants=[]
    for pair in ('01','23'):
        profile=f'gcp-c4d-static{pair}-v1';worker=f'anext-cancel-host-aw{aw}-{pair}-v1';packet=output/('packet-'+pair)
        result=package.prepare(path,source,profile,worker,'run',packet,Path(budget).resolve())
        variants.append(dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),
            sha256=result['archive_sha256'],ticket_sha256=result['ticket_sha256'],
            manifest_sha256=native.gen.sha((packet/'manifest.json').read_bytes()),native_root=result['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=PACKAGE_SHA,
            stager=str(ROOT/STAGER),stager_sha256=STAGER_SHA,
            stager_dependencies=[dict(path=str(ROOT/COMPANION),sha256=COMPANION_SHA)],max_seconds=3700))
    left,right=[json.loads((Path(v['archive']).parent/'manifest.json').read_text()) for v in variants]
    native.gen.need(all(left[k]==right[k] for k in ('sources','build','probe','steps')),'ANEXT_CANCEL_DUAL_ROLE_IDENTITY')
    identifier=f'anext-cancel-host-aw{aw}-q1-v1'
    ticket=dict(schema='gfn16-global-ticket-v1',id=identifier,owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=4,minimum_ram_rationale='Explicit bounded exploratory4GiB allowance for paired AW<=8 host/setup/canonical/RAM only; desired8 remains, preserve failure/no automaticretry.',
        est_minutes=5,promotion_bound=False,packages=variants)
    if aw==8:ticket.update(after=['anext-cancel-host-aw5-q1-v1'],on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',ticket)
    summary=dict(schema='anext-cancel-host-preparation-v1',status='source_ready_not_dispatched',aw=aw,
        source_files=len(files),source_pins=native.PINS,variants=variants,counts=native.counts(aw),
        cycle_delta=0,recovery_reset_changed=False,HDL_or_native_executed=False,promotion_allowed=False)
    dump(output/'preparation.json',summary);native.verify();return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--aw',type=int,choices=(5,8),required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.output,args.aw,args.budget),indent=2))

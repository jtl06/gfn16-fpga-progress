"""Bounded reset helper AW5→AW8 source packets; dispatcher alone executes."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from fpga.reference import anext_field_reset_native_v1 as native
from fpga.tools import native_class_package_v2 as package

ROOT=native.ROOT
SELF='reference/anext_field_reset_prepare_v1.py'
REPLAY='reference/anext_field_reset_replay_v1.py'
TESTS=('tests/test_anext_field_reset_release_v1.py','tests/test_anext_field_reset_prepare_v1.py')
PACKAGE_SHA='03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604'
STAGER='tools/native_package_v3.py'
STAGER_SHA='5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'
COMPANION='tools/native_package_v2.py'
COMPANION_SHA='3f2186fa5aac8129ac1ad5a161de39cf221925ee95d5de6364a941b199e7279a'


def role(aw):
    native.verify();r=native.probe.role_config(aw)
    names=(*native.PINS,native.SELF,SELF,REPLAY,*TESTS,'reference/__init__.py')
    files={name:(ROOT/name).read_bytes() for name in names}
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/not-a-dispatch-path/anext-field-reset/fpga',output_parent='/not-a-dispatch-path/anext-field-reset/output',
        sources={name:native.model.sha(raw) for name,raw in files.items()},
        build={k:v for k,v in r['build'].items() if k!='threads'},
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[],scope='One isolated field-local reset-release component with actual leaves, no sequencer clone/fullN/wholeclock/fit claim.',
        field_reset=dict(source_pins=native.PINS,contract=native.model.ledger(),role=r,
            whole_cancel_scope='Registered full-clock cancel/steadyFAILED only. Missedsubcyclepulse can stall real seqcache/header and is NOT wholequalified. Probependingreadpulse mustgenuinelyquarantine.',
            phase_boundary='CallerE0→fieldRAM E2→visibleafterE4/consumerE5; directleaf onlythirdeligiblereleaseedge. Preserve allleaf resets/raw finalaccept kills. No directbegin/start drop.',
            metadata_scope='ProbeROMcollector is observer only, not realengineheader/cache proof. EngineBF/MUL finalRAM acceptance and globalfault/cache/quarantine require integrator gates iflaterselected.',
            parent_priority='Finishboundednativecomponent only; currentF3recoverypasses. No wholeintegration/fit request solelyoldupperfailure.',native_executed=False,promotion_allowed=False))
    m['build']['cflags'].append('-Werror=return-type')
    for row in r['cases']:
        m['steps'].append(dict(name='reset-'+row['name'],argv=['{exe}']+row['args'],expected_returncode=row['expected_exit'],
            validator=dict(source=native.SELF,function='validate',config=dict(aw=aw,case=row['name']),assets={})))
    native.model.need(set(m['build']['sv_sources']+[m['build']['cpp_source']])<=files.keys(),'ANEXT_RESET_CLOSED_COMPILED_SOURCE')
    return m,files


def dump(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def prepare(output,aw,budget):
    native.model.need(not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),'ANEXT_RESET_PAUSE')
    for name,pin in (('tools/native_class_package_v2.py',PACKAGE_SHA),(STAGER,STAGER_SHA),(COMPANION,COMPANION_SHA)):
        native.model.need(native.model.sha((ROOT/name).read_bytes())==pin,'ANEXT_RESET_SHARED_TOOL '+name)
    output=Path(output).resolve();native.model.need(not output.exists(),'ANEXT_RESET_FRESH_OUTPUT')
    manifest,files=role(aw);source=output/'input/source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    path=output/'input/manifest.json';dump(path,manifest);variants=[]
    for pair in ('01','23'):
        profile=f'gcp-c4d-static{pair}-v1';worker=f'anext-field-reset-aw{aw}-{pair}-v1';packet=output/('packet-'+pair)
        r=package.prepare(path,source,profile,worker,'run',packet,Path(budget).resolve())
        variants.append(dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],
            ticket_sha256=r['ticket_sha256'],manifest_sha256=native.model.sha((packet/'manifest.json').read_bytes()),native_root=r['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=PACKAGE_SHA,stager=str(ROOT/STAGER),stager_sha256=STAGER_SHA,
            stager_dependencies=[dict(path=str(ROOT/COMPANION),sha256=COMPANION_SHA)],max_seconds=3700))
    left,right=[json.loads((Path(v['archive']).parent/'manifest.json').read_text()) for v in variants]
    native.model.need(all(left[k]==right[k] for k in ('sources','build','probe','steps')),'ANEXT_RESET_DUAL_ROLE_IDENTITY')
    ticket=dict(schema='gfn16-global-ticket-v1',id=f'anext-field-reset-aw{aw}-q1-v1',owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P2',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=4,minimum_ram_rationale='Explicitbounded4GiB exploration for AW<=8 actualleaf resetprobe, no completeNTT/wholecore. Desired8 retained; preservefailure/noautomaticretry.',
        est_minutes=5,promotion_bound=False,packages=variants)
    if aw==8:ticket.update(after=['anext-field-reset-aw5-q1-v1'],on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',ticket)
    summary=dict(schema='anext-field-reset-preparation-v1',status='source_ready_not_dispatched',aw=aw,
        source_files=len(files),source_pins=native.PINS,variants=variants,role=manifest['field_reset']['role'],native_executed=False,
        whole_integration_requested=False,fit_requested=False,promotion_allowed=False)
    dump(output/'preparation.json',summary);native.verify();return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--aw',type=int,choices=(5,8),required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=Path,required=True)
    args=parser.parse_args();r=prepare(args.output,args.aw,args.budget)
    print(json.dumps(dict(aw=r['aw'],source_files=r['source_files'],variants=r['variants']),indent=2))

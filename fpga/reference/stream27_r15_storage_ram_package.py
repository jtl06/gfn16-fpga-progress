"""Existing ordinary Azure-only packages for already-frozen storage roles."""
from datetime import datetime,timezone
import json
from pathlib import Path
from fpga.reference import stream27_r15_storage_ram_bind as b

ROOT=b.ROOT
BASE=ROOT/'results/throughput-20261003/trackS-r15-storage-ram-v1'
INPUT='queue/provider-cost-status/azure-inputs-60581bfa5349c90a15179e93baa18fa7bbc2914b850b6b74d206cd92dc8faf89.json'
INPUT_PIN='60581bfa5349c90a15179e93baa18fa7bbc2914b850b6b74d206cd92dc8faf89'
PROFILE_PIN='c6d0dd6cc08f305492f7569eb0dfd08a855e1c75373917c3c971efae8fc871eb'
PACKAGE_PIN='c2eb7148d89db89caec767ae876d399ef3f367562f1f1e177a100acf753d6e8c'
STAGER_PIN='878138db412a83482b7959ae48fbd4e3199aad4a5edae77e79cd08c6a4bc8209'
ROLES={
 'crt-pair-normal':('s4-p16-r15-crt-numeric-pair-normal-q1-v1',None),
 'aw8-normal-v2':('s4-p16-r15-storage-crt-aw8-normal-q1-v2',None),
 'full-normal-v2':('s4-p16-r15-storage-crt-full-normal-q1-v2','s4-p16-r15-storage-crt-aw8-normal-q1-v2'),
 'crt-pair-reset':('s4-p16-r15-crt-numeric-pair-reset-q1-v1','s4-p16-r15-crt-numeric-pair-normal-q1-v1')}


def dump(path,value):
    with Path(path).open('x') as out:json.dump(value,out,indent=2);out.write('\n')


def prepare(role_name):
    from fpga.tools import native_class_package_v4 as package
    b.need(role_name in ROLES,'KNOWN_FROZEN_ROLE')
    b.need(b.sha((ROOT/'tools/native_class_package_v4.py').read_bytes())==PACKAGE_PIN and
           b.sha((ROOT/'tools/native_package_v6.py').read_bytes())==STAGER_PIN,'ADOPTED_ORDINARY_PIN')
    directory=BASE/role_name;mr=(directory/'manifest.json').read_bytes();m=json.loads(mr)
    source=Path(m['source_root']);b.need(source==directory/'source/fpga','EXACT_OWN_SOURCE')
    for name,pin in m['sources'].items():
        b.need(b.sha((source/name).read_bytes())==pin,'FROZEN_ROLE_SOURCE:'+name)
    budget=package.meter().make_budget('gfn16-azure-f16',3715,INPUT,INPUT_PIN,
        package.source_identity(m),PROFILE_PIN)
    dump(directory/'azure-host-hours.json',budget)
    variants=[];identifier,dependency=ROLES[role_name]
    for pair in ('1213','1415'):
        profile='azure-f16-static'+pair+'-v1'
        worker=identifier.replace('-q1-','-'+pair+'-')
        packet=directory/('packet-'+pair)
        r=package.prepare(directory/'manifest.json',source,profile,worker,'run',packet,directory/'azure-host-hours.json')
        ticket=json.loads((packet/'ticket.json').read_text())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],
            ticket_sha256=r['ticket_sha256'],manifest_sha256=b.sha((packet/'manifest.json').read_bytes()),
            worker_id=worker,profile=profile,native_root=ticket['native_root'],
            runner='tools/native_class_package_v4.py',runner_sha256=PACKAGE_PIN,
            stager=str(ROOT/'tools/native_package_v6.py'),stager_sha256=STAGER_PIN,
            stager_dependencies=[dict(path=str(ROOT/n),sha256=b.sha((ROOT/n).read_bytes()))
                for n in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    logical=dict(schema='gfn16-global-ticket-v1',id=identifier,owner='p16-mlab',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',
        kind='sim',needs='verilator',tool_identity='azure-f16-verilator5032-gcc13-python312-v1',
        allowed_hosts=['gfn16-azure-f16'],resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=8,minimum_ram_rationale='Actual existing Azure ordinary2physical/model1/8GiB/j2 profile; no alternate-host/runtime forecast.',
        est_minutes=5 if role_name.startswith('crt') else 25,promotion_bound=False,
        test_role=m['test_role'],rtl_readiness=m['rtl_readiness'],packages=variants)
    if dependency:logical.update(after=[dependency],on='PASS_expected_contracts')
    dump(directory/'global-ticket.json',logical)
    b.need((directory/'manifest.json').read_bytes()==mr,'ROLE_NOT_MUTATED_BY_PACKAGING')
    return dict(id=identifier,ticket=str(directory/'global-ticket.json'),status='PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--role',choices=tuple(ROLES),required=True);a=p.parse_args()
    print(json.dumps(prepare(a.role),indent=2))

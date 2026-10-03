"""Mechanical existing-queue packets for the frozen application/GMP fixture."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from .stream27_r15_host_window_gmp_packet import ROOT,RUNNER,STAGER,sha,need,dump

BASE=ROOT/'results/throughput-20261003/r15-host-window-application-gmp-native-v1'
ROLES={
 'normal':('s4-r15-host-window-application-gmp-aw8-normal-q1-v1',
   '6711eeeeb72450dc8ade1b847f4e6ff5da8bfb36a66ceae9693e6c9eae2e33ff',
   'db7d831564bcd92144b261c10f354175e652c9ebe9dc0052a6e25263aec5c4f8'),
 'faults':('s4-r15-host-window-application-gmp-aw8-faults-q1-v1',
   '58a35e88a3a1b1fc37730e2990f2992ede2ed5e06d5fef1d6b4313cc87d41e1a',
   '245f4ab50d48b298b9d8eda3034599e5c4c3c8f43d58161a407e22883fe4ff2b'),
}


def prepare(mode,runner_pin,stager_pin):
    from fpga.tools import global_queue_v1 as queue,native_class_package_v4 as package
    need(mode in ROLES,'APP_MODE')
    need(sha(ROOT/RUNNER)==runner_pin and sha(ROOT/STAGER)==stager_pin,'APP_FINAL_OPERATOR_PINS')
    logical_id,manifest_pin,identity=ROLES[mode];role=BASE/mode
    manifest_path=role/'manifest.json';need(sha(manifest_path)==manifest_pin,'APP_FROZEN_ROLE')
    manifest=json.loads(manifest_path.read_bytes());source=Path(manifest['source_root'])
    need(source==role/'source/fpga' and package.source_identity(manifest)==identity,'APP_EXACT_ROLE_IDENTITY')
    need(all(sha(source/name)==pin for name,pin in manifest['sources'].items()),'APP_FROZEN_ALL_SOURCES')
    out=role/'azure-packets-v1';need(not out.exists(),'APP_FRESH_OUTPUT');out.mkdir()
    provider=queue.provider_capture_ref()
    budget=package.meter().make_budget('gfn16-azure-f16',3715,
        str(Path(provider['path']).relative_to(ROOT)),provider['sha256'],identity,package.F16_PROFILE_SHA)
    dump(out/'budget.json',budget);variants=[]
    for pair in ('1213','1415'):
        profile='azure-f16-static'+pair+'-v1';worker=logical_id.replace('-q1-','-'+pair+'-')
        packet=out/('packet-'+pair)
        result=package.prepare(manifest_path,source,profile,worker,'run',packet,out/'budget.json')
        native=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'],manifest_sha256=sha(packet/'manifest.json'),
            worker_id=worker,profile=profile,native_root=native['native_root'],runner=RUNNER,
            runner_sha256=runner_pin,stager=str(ROOT/STAGER),stager_sha256=stager_pin,
            stager_dependencies=[dict(path=str(ROOT/name),sha256=sha(ROOT/name)) for name in
                ('tools/native_package_v5.py','tools/native_package_v3.py','tools/native_package_v2.py')],
            max_seconds=3700))
    predecessor='s4-p16-c2-r15-shell-application-aw8-normal-q1-v5' if mode=='normal' else ROLES['normal'][0]
    ticket=dict(schema='gfn16-global-ticket-v1',id=logical_id,owner='independent-review',
        created=datetime.now(timezone.utc).isoformat(),priority='P0' if mode=='normal' else 'P2',
        kind='sim',needs='verilator',tool_identity='azure-f16-verilator5032-gcc13-python312-v1',
        allowed_hosts=['gfn16-azure-f16'],resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=8,est_minutes=10,promotion_bound=False,test_role=manifest['test_role'],
        rtl_readiness=manifest['rtl_readiness'],after=[predecessor],on='PASS_expected_contracts',packages=variants)
    dump(out/'global-ticket.json',ticket)
    need(sha(ROOT/RUNNER)==runner_pin and sha(ROOT/STAGER)==stager_pin,'APP_STABLE_OPERATOR_PINS')
    return dict(id=logical_id,ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=tuple(ROLES),required=True)
    p.add_argument('--runner-pin',required=True);p.add_argument('--stager-pin',required=True)
    a=p.parse_args();print(json.dumps(prepare(a.mode,a.runner_pin,a.stager_pin),indent=2))

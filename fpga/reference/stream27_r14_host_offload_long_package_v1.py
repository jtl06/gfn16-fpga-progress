"""One measured R14 ON-only1000 package through the existing long interface."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-r14-host-offload-ownlong-v1'
PILOT_ID='s4-r14-host-offload-own100-q1-v1'
ID='s4-r14-host-offload-continuous1000-q1-v1'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def prepare(package_pin,stager_pin):
    if any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('PAUSE')
    for pin in (package_pin,stager_pin):
        if type(pin)is not str or len(pin)!=64 or any(c not in '0123456789abcdef' for c in pin):raise ValueError('exact tested long tool pins')
    if sha(ROOT/'tools/native_long_package_v3.py')!=package_pin or sha(ROOT/'tools/native_long_stage_v3.py')!=stager_pin:raise ValueError('long shared source drift')
    from fpga.tools import native_long_package_v3 as package,candidate_ladder
    raw=BASE/'continuous1000-source-v1';bound=BASE/'continuous1000-bound-v1';out=BASE/'continuous1000-packet-v1'
    if bound.exists() or out.exists():raise ValueError('fresh single logical package')
    evidence=ROOT/'queue/evidence'/PILOT_ID/'attempt-0/collected/output/native'
    paths=dict(forecast=raw/'own-pilot-forecast.json',pilot_manifest=evidence/'approved-manifest.json',
        pilot_report=evidence/'report.json',pilot_gate=ROOT/'queue/evidence'/PILOT_ID/'gate-receipt.json')
    package.bind_role(raw/'manifest.json',raw/'source/fpga',paths,bound)
    manifest=bound/'manifest.json';source=bound/'source/fpga';m=json.loads(manifest.read_bytes())
    if len(m['build']['sv_sources'])!=66 or m['build']['parameters'].get('HOST_OFFLOAD')!=1:raise ValueError('actual ON66 source')
    out.mkdir();budget=out/'host-hours.json';dump(budget,candidate_ladder.budget_from_hourly());variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-r14-continuous1000-'+pair+'-v1';packet=out/('packet-'+pair)
        result=package.prepare(manifest,source,profile,worker,'run',packet,budget);ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'],manifest_sha256=sha(packet/'manifest.json'),worker_id=worker,
            profile=profile,native_root=ticket['native_root'],runner='tools/native_long_package_v3.py',runner_sha256=package_pin,
            stager=str(ROOT/'tools/native_long_stage_v3.py'),stager_sha256=stager_pin,
            stager_dependencies=[dict(path=str(ROOT/p),sha256=sha(ROOT/p)) for p in
                ('tools/native_long_stage_v1.py','tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=10800))
    logical=dict(schema='gfn16-global-ticket-v1',id=ID,owner='stream-interface',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,
        minimum_ram_rationale='Own measured ON-only100 source/allocation; identical66RTL/CPP/C/reference, COUNT/BITS-only extension; no parent forecast.',
        allowed_hosts=['gfn16-pilot-c4d'],est_minutes=70,promotion_bound=False,test_role='normal',rtl_readiness=m['rtl_readiness'],packages=variants,
        after=[PILOT_ID],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',logical)
    return dict(id=ID,ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_SUBMITTED')
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--package-pin',required=True);p.add_argument('--stager-pin',required=True);a=p.parse_args()
    print(json.dumps(prepare(a.package_pin,a.stager_pin),indent=2))

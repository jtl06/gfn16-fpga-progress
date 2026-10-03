"""ONE R12 LEAN long envelope using existing source-bound serial package/stager."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))
BASE=ROOT/'results/throughput-20260929/trackS-c2-feedback12-ownlong-v1'
BOUND=BASE/'continuous1000-bound-v1'
OUT=BASE/'continuous1000-packet-v1'
ID='s4-p16-c2-combo-r12-continuous1000-q1-v1'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
def prepare(package_pin,stager_pin):
    from fpga.tools import native_long_package_v3 as package,candidate_ladder
    if any(type(p) is not str or len(p)!=64 or any(c not in '0123456789abcdef' for c in p) for p in (package_pin,stager_pin)):raise ValueError('explicit tested final R12 long pins')
    if OUT.exists() or any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('fresh unpaused R12 LEAN long envelope')
    if sha(ROOT/'tools/native_long_package_v3.py')!=package_pin or sha(ROOT/'tools/native_long_stage_v3.py')!=stager_pin:raise ValueError('stable admitted R12 LEAN envelope')
    manifest=BOUND/'manifest.json';source=BOUND/'source/fpga';m=json.loads(manifest.read_bytes())
    if any(m['build']['parameters'].get(k)!=1 for k in ('CRT_TRANSPORT_REG','INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG','LEAN_PROGRESS_WATCHDOG','FEEDBACK_INGRESS_REG','AUTO_CORRECTION_INGRESS_REG','C0_ADMISSION_DIRECT')) or len(m['build']['sv_sources'])!=59 or m['build']['parameters']['COLD_SECOND_ONESHOT']!=1 or m['build']['parameters']['COMM_OWNER_COMPARE_LOCAL']!=1 or m['build']['parameters']['CANONICAL_C0_DIRECT']!=1 or m['build']['parameters']['ERROR_AGGREGATION_REGISTERED']!=1 or m['build']['parameters']['LEAN_PRODUCTION']!=1 or m['build']['parameters']['FINAL_GS_INPUTREG']!=1:raise ValueError('own R12 LEAN production and observer')
    OUT.mkdir();budget=OUT/'host-hours.json';dump(budget,candidate_ladder.budget_from_hourly())
    variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-p16-c2-combo-r12-continuous1000-'+pair+'-v1';packet=OUT/('packet-'+pair)
        result=package.prepare(manifest,source,profile,worker,'run',packet,budget)
        ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'],manifest_sha256=sha(packet/'manifest.json'),worker_id=worker,
            profile=profile,native_root=ticket['native_root'],runner='tools/native_long_package_v3.py',runner_sha256=package_pin,
            stager=str(ROOT/'tools/native_long_stage_v3.py'),stager_sha256=stager_pin,
            stager_dependencies=[dict(path=str(ROOT/p),sha256=sha(ROOT/p)) for p in
                ('tools/native_long_stage_v1.py','tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=10800))
    logical=dict(schema='gfn16-global-ticket-v1',id=ID,owner='merged-ntt-model',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,
        minimum_ram_rationale='Own fixedR12 LEAN source-bound GCP serial100 pilot; COUNT/BITS-only compiled delta and identical2physical/8GiB/j2. Host GL assumed/unimplemented; no protected fault/rollback or parent runtime/clock inherited.',
        allowed_hosts=['gfn16-pilot-c4d'],est_minutes=90,promotion_bound=False,test_role='normal',rtl_readiness=m['rtl_readiness'],
        packages=variants,after=['s4-p16-c2-combo-r12-own100-serial-q1-v1'],on='PASS_expected_contracts')
    dump(OUT/'global-ticket.json',logical)
    return dict(id=ID,ticket=str(OUT/'global-ticket.json'),status='PREPARED_NOT_NATIVE_NOT_SUBMITTED')
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-pin',required=True);parser.add_argument('--stager-pin',required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.package_pin,args.stager_pin),indent=2))



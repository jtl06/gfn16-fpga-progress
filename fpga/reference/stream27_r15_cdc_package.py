"""Capture ONE ordinary AzureFIT CDC job with the existing shared package API."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from fpga.tools import native_class_package_v4 as package

ROOT=Path(__file__).resolve().parents[1]
ROLE=ROOT/'results/throughput-20260929/trackS-r15-cdc-native-v1/normal-v1'
RUNNER='tools/native_class_package_v4.py'
STAGER='tools/native_package_v6.py'
PINS={RUNNER:'4e44c36d74d1fa11b0ebf3d256e64b9cd0704a82d0f01c036f7669c3c92ae0d5',
      STAGER:'07d6c526e36f26c6fae6536af66ca67d86bcf1191ef7d25965bd9e6d3f243747'}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2);f.write('\n')

def prepare_role(role=ROLE, identifier='s4-r15-cdc-normal-q1-v1', owner='stream-interface'):
    role=Path(role).resolve()
    allowed=(ROOT/'results/throughput-20260929/trackS-r15-cdc-native-v1',
             ROOT/'results/throughput-20260929/trackS-r15-pcie-avmm-native-v1',
             ROOT/'results/throughput-20260929/trackS-r15-pcie-avmm-native-v4',
             ROOT/'results/throughput-20260929/trackS-r15-pcie-avmm-native-v5',
             ROOT/'results/throughput-20260929/trackS-r15-pcie-avmm-native-v6',
             ROOT/'results/throughput-20260929/trackS-r15-link-reset-native-v1')
    if not any(role.is_relative_to(p) for p in allowed):raise ValueError('R15_INTERFACE_OWN_ROLE')
    for p,h in PINS.items():
        if sha(ROOT/p)!=h:raise ValueError('R15_CDC_ADOPTED_TOOL_DRIFT')
    mr=(role/'manifest.json').read_bytes();m=json.loads(mr);source=role/'source/fpga'
    if m['source_root']!=str(source):raise ValueError('R15_CDC_SOURCE_ROOT')
    for p,h in m['sources'].items():
        if sha(source/p)!=h:raise ValueError('R15_CDC_SOURCE_DRIFT')
    pin='60581bfa5349c90a15179e93baa18fa7bbc2914b850b6b74d206cd92dc8faf89'
    provider='queue/provider-cost-status/azure-inputs-'+pin+'.json'
    budget=package.meter().make_budget('gfn16-azure-f16',3715,provider,pin,package.source_identity(m),package.F16_PROFILE_SHA)
    bp=role/'azure-host-hours.json';dump(bp,budget)
    profile='azure-f16-static1213-v1';worker=identifier.replace('-q1-','-1213-');out=role/'packet-1213'
    r=package.prepare(role/'manifest.json',source,profile,worker,'run',out,bp)
    ticket=json.loads((out/'ticket.json').read_bytes())
    variant=dict(archive=str(out/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
      manifest_sha256=sha(out/'manifest.json'),worker_id=worker,profile=profile,native_root=ticket['native_root'],
      runner=RUNNER,runner_sha256=PINS[RUNNER],stager=str(ROOT/STAGER),stager_sha256=PINS[STAGER],
      stager_dependencies=[dict(path=str(ROOT/p),sha256=sha(ROOT/p)) for p in
         ('tools/native_package_v5.py','tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700)
    logical=dict(schema='gfn16-global-ticket-v1',id=identifier,owner=owner,
      created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
      tool_identity='azure-f16-verilator5032-gcc13-python312-v1',allowed_hosts=['gfn16-azure-f16'],
      resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,est_minutes=5,
      promotion_bound=False,test_role=m['test_role'],rtl_readiness=m['rtl_readiness'],packages=[variant])
    dump(role/'global-ticket.json',logical)
    if (role/'manifest.json').read_bytes()!=mr:raise ValueError('R15_CDC_CAPTURE_CHANGED')
    return {'ticket':str(role/'global-ticket.json'),'id':logical['id'],'status':'PREPARED_NOT_SUBMITTED'}

if __name__=='__main__':print(json.dumps(prepare_role(),indent=2))

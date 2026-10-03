"""Mechanical two-static-lane packaging for the same R15 interface roles.

No scheduler, provider polling, launch or mutable policy. The shared queue
chooses ONE of its two already-adopted Azure variants under ordinary guards.
"""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from fpga.tools import native_class_package_v4 as package
from fpga.tools import global_queue_v1 as queue

ROOT=Path(__file__).resolve().parents[1]
RUNNER='tools/native_class_package_v4.py'
STAGER='tools/native_package_v6.py'
PINS={RUNNER:'03ff2d89cb40d36a170ddb239500f611b76b069aa31cf1ae18ac65caf1c6c2c6',
      STAGER:'a2bdc7413484a8a8f4ab562870571b72cc644818ae29362bd5723a7f036bc82b'}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,value):
    with Path(p).open('x') as f:json.dump(value,f,indent=2);f.write('\n')


def prepare_role(role,identifier,owner='stream-interface',after=()):
    role=Path(role).resolve()
    allowed=[ROOT/'results/throughput-20260929'/name for name in
      ('trackS-r15-pcie-avmm-native-v8','trackS-r15-dma-aperture-native-v2')]
    if not any(role.is_relative_to(p) for p in allowed):raise ValueError('R15_INTERFACE_OWN_ROLE')
    if (role/'global-ticket.json').exists():raise ValueError('R15_INTERFACE_FRESH_LOGICAL_INPUT')
    for p,h in PINS.items():
        if sha(ROOT/p)!=h:raise ValueError('R15_INTERFACE_ADOPTED_TOOL_DRIFT')
    raw=(role/'manifest.json').read_bytes();m=json.loads(raw);source=role/'source/fpga'
    if m['test_role'] not in ('normal','bounded-fault','deliberate_fault'):
        raise ValueError('R15_INTERFACE_ROLE_KIND')
    logical_role='normal' if m['test_role']=='normal' else 'deliberate_fault'
    if m['source_root']!=str(source):raise ValueError('R15_INTERFACE_SOURCE_ROOT')
    for p,h in m['sources'].items():
        if sha(source/p)!=h:raise ValueError('R15_INTERFACE_SOURCE_DRIFT')
    provider=queue.provider_capture_ref()
    relative=str(Path(provider['path']).relative_to(ROOT))
    budget=package.meter().make_budget('gfn16-azure-f16',3715,relative,provider['sha256'],
                                      package.source_identity(m),package.F16_PROFILE_SHA)
    bp=role/'azure-host-hours.json';dump(bp,budget)
    variants=[]
    for suffix in ('1213','1415'):
        profile='azure-f16-static'+suffix+'-v1'
        worker=identifier.replace('-q1-','-'+suffix+'-');out=role/('packet-'+suffix)
        r=package.prepare(role/'manifest.json',source,profile,worker,'run',out,bp)
        ticket=json.loads((out/'ticket.json').read_bytes())
        variants.append(dict(archive=str(out/'package.tar.gz'),sha256=r['archive_sha256'],
          ticket_sha256=r['ticket_sha256'],manifest_sha256=sha(out/'manifest.json'),worker_id=worker,
          profile=profile,native_root=ticket['native_root'],runner=RUNNER,runner_sha256=PINS[RUNNER],
          stager=str(ROOT/STAGER),stager_sha256=PINS[STAGER],
          stager_dependencies=[dict(path=str(ROOT/p),sha256=sha(ROOT/p)) for p in
            ('tools/native_package_v5.py','tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    logical=dict(schema='gfn16-global-ticket-v1',id=identifier,owner=owner,
      created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
      tool_identity='azure-f16-verilator5032-gcc13-python312-v1',allowed_hosts=['gfn16-azure-f16'],
      resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,est_minutes=5,
      promotion_bound=False,test_role=logical_role,rtl_readiness=m['rtl_readiness'],packages=variants)
    if after:logical['after']=list(after)
    dump(role/'global-ticket.json',logical)
    if (role/'manifest.json').read_bytes()!=raw:raise ValueError('R15_INTERFACE_CAPTURE_CHANGED')
    return dict(id=identifier,ticket=str(role/'global-ticket.json'),status='PREPARED_NOT_SUBMITTED')

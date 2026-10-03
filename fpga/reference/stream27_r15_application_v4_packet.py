"""Existing Azure native API for exactly the new application-v4 normal pair."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump
from fpga.reference import stream27_r15_application_packet_v3 as operator
from fpga.reference import stream27_r15_shell_application_v4_native as own

ROOT=Path(__file__).resolve().parents[1]


def prepare(stage):
    from fpga.tools import native_class_package_v4 as package
    from fpga.cloud import host_hours_azure_signed_v1 as meter
    need(stage in own.ROLES and sha((ROOT/operator.RUNNER).read_bytes())==operator.RUNNER_PIN and
         sha((ROOT/operator.STAGER).read_bytes())==operator.STAGER_PIN and
         package.ACTIVE_PROFILES==operator.PROFILES,'R15_APP_V4_CURRENT_OPERATOR_LITERAL_ROLE')
    role=own.BASE/'trackS-r15-shell-application-native-v4'/(stage+'-normal')
    manifest=role/'manifest.json';m=json.loads(manifest.read_bytes());source=role/'source/fpga'
    need(len(m['build']['sv_sources'])==71 and m['build']['runtime_threads']==1 and
         m['r15_shell_application_native']['application_entry_sha256']==own.BINDER_PIN and
         m['sources'][own.SELF]==sha((ROOT/own.SELF).read_bytes()) and
         all(sha((source/n).read_bytes())==h for n,h in m['sources'].items()),'R15_APP_V4_OWN_CLOSED_SOURCE')
    out=role/'azure-packet-v1';need(not out.exists(),'R15_APP_V4_FRESH_PACKAGE');out.mkdir()
    budget=out/'budget.json';dump(budget,meter.make_budget('gfn16-azure-f16',3715,operator.PROVIDER,
      operator.PROVIDER_PIN,package.source_identity(m),profile_sha256=package.F16_PROFILE_SHA))
    id=own.ROLES[stage]['id'];variants=[]
    for profile in operator.PROFILES:
        pair=profile.split('static',1)[1].split('-',1)[0];worker=id.rsplit('-q1-',1)[0]+'-'+pair+'-'+id.rsplit('-',1)[-1]
        packet=out/('packet-'+pair);result=package.prepare(manifest,source,profile,worker,'run',packet,budget)
        native=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
          ticket_sha256=result['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
          worker_id=worker,profile=profile,native_root=native['native_root'],runner=operator.RUNNER,
          runner_sha256=operator.RUNNER_PIN,stager=str(ROOT/operator.STAGER),stager_sha256=operator.STAGER_PIN,
          stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes())) for p in
            ('tools/native_package_v5.py','tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    need(sha((ROOT/operator.RUNNER).read_bytes())==operator.RUNNER_PIN and
         sha((ROOT/operator.STAGER).read_bytes())==operator.STAGER_PIN,'R15_APP_V4_OPERATOR_PINS_STABLE')
    ticket=dict(schema='gfn16-global-ticket-v1',id=id,owner='merged-ntt-model',
      created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P0',kind='sim',needs='verilator',
      tool_identity='azure-f16-verilator5032-gcc13-python312-v1',allowed_hosts=['gfn16-azure-f16'],
      resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,est_minutes=25,
      promotion_bound=False,test_role='normal',rtl_readiness=m['rtl_readiness'],packages=variants)
    if stage=='full':ticket.update(after=[own.ROLES['aw8']['id']],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',ticket)
    return dict(id=id,ticket=str(out/'global-ticket.json'),variants=2,status='PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=tuple(own.ROLES),required=True);a=p.parse_args()
    print(json.dumps(prepare(a.stage),indent=2))
